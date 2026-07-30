"""Live delivery layer: presence, long-poll wakeups, per-agent rate limiting, and
atomic claims — on top of a durable MessageStore.

Messages live in the store (SQLite); the hub keeps only ephemeral, live state. SQLite
calls are offloaded with ``asyncio.to_thread`` so a slow/contended query never blocks the
event loop; the in-memory presence/waiter/rate-limit state is touched only on the loop
thread (and ``asyncio.Event.set`` is called there, after the await). Single-process by
design — for multi-process scale, front it with a shared backend (see ROADMAP.md).
"""
from __future__ import annotations

import asyncio
import time

from .settings import settings

ONLINE_WINDOW_SECONDS = settings.online_window


def build_roster(peers_by_room: dict, code_rows: list, members_by_room: dict) -> dict:
    """Who belongs to each room, from durable data, with presence attached as status.

    Presence alone cannot answer this. ``Hub._last_seen`` is in-memory, so it empties
    on restart, and a peer ages out of ``online`` after ONLINE_WINDOW_SECONDS anyway.
    Membership is durable: an agent holds a code for the room, or it has posted into
    the room, or both. Either fact outlives the process.

    So the union is codes plus senders plus anyone live right now, and ``online`` is
    only a flag on the row. It never decides whether the row exists. Pure function:
    no clock, no I/O, so the caller supplies all three views and the tests can too.

    Each row is ``{name, online, seconds_since_seen, last_message_seconds, sources}``.
    ``seconds_since_seen`` is null when this process has never seen the agent connect,
    and ``last_message_seconds`` is null when it has never posted here. ``sources``
    lists which evidence put the row in the roster: presence, code, messages.
    """
    rooms = set(peers_by_room) | set(members_by_room) | {c.get("room", "") for c in code_rows}
    rooms.discard("")

    codes_by_room: dict = {}
    for c in code_rows:
        codes_by_room.setdefault(c.get("room", ""), {})[c.get("name", "")] = c.get("capabilities", "") or ""

    out: dict = {}
    for room in sorted(rooms):
        live = {p["name"]: p for p in peers_by_room.get(room, [])}
        posted = {m["name"]: m for m in members_by_room.get(room, [])}
        invited = codes_by_room.get(room, {})
        rows = []
        for name in sorted(set(live) | set(posted) | set(invited)):
            sources = []
            if name in live:
                sources.append("presence")
            if name in invited:
                sources.append("code")
            if name in posted:
                sources.append("messages")
            rows.append({
                "name": name,
                "online": bool(live.get(name, {}).get("online", False)),
                "seconds_since_seen": live[name]["seconds_since_seen"] if name in live else None,
                "last_message_seconds": posted[name]["seconds_since_last"] if name in posted else None,
                "capabilities": invited.get(name, ""),
                "sources": sources,
            })
        out[room] = rows
    return out


class Hub:
    def __init__(self, store) -> None:
        self.store = store
        self._last_seen: dict = {}    # room -> {peer: monotonic ts}
        self._waiters: dict = {}      # room -> list[asyncio.Event]
        self._post_times: dict = {}   # rate-limit key -> list[monotonic ts]

    # ----- in-memory, loop-thread only -----

    def touch(self, room: str, peer: str) -> bool:
        """Mark a peer present; returns True the first time we ever see this peer."""
        seen = self._last_seen.setdefault(room, {})
        is_new = peer not in seen
        seen[peer] = time.monotonic()
        return is_new

    def peers(self, room: str) -> list:
        now = time.monotonic()
        out = []
        for name, seen in sorted(self._last_seen.get(room, {}).items()):
            ago = now - seen
            out.append({"name": name, "online": ago <= ONLINE_WINDOW_SECONDS, "seconds_since_seen": round(ago, 1)})
        return out

    def all_peers(self) -> dict:
        return {room: self.peers(room) for room in sorted(self._last_seen)}

    def allow(self, key: str, max_n: int, window: float) -> bool:
        """Sliding-window rate limit; only counts allowed posts so a block doesn't extend the window."""
        now = time.monotonic()
        times = self._post_times.setdefault(key, [])
        cutoff = now - window
        while times and times[0] < cutoff:
            times.pop(0)
        if len(times) >= max_n:
            return False
        times.append(now)
        return True

    def _wake(self, room: str) -> None:
        for ev in list(self._waiters.get(room, [])):
            ev.set()

    # ----- durable store access (offloaded to a threadpool) -----

    async def post(self, room, frm, to, text, expects_reply="none") -> dict:
        msg = await asyncio.to_thread(self.store.add, room, frm, to, text, expects_reply)
        self._wake(room)
        return msg

    async def claim(self, room, seq, peer) -> dict:
        return await asyncio.to_thread(self.store.claim, room, seq, peer)

    async def history(self, room, limit) -> list:
        return await asyncio.to_thread(self.store.history, room, limit)

    async def read(self, room, peer, since, wait):
        deadline = time.monotonic() + max(0.0, wait)
        waiters = self._waiters.setdefault(room, [])
        while True:
            msgs = await asyncio.to_thread(self.store.since, room, peer, since)
            if msgs or wait <= 0:
                return msgs, await asyncio.to_thread(self.store.room_seq, room)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return [], await asyncio.to_thread(self.store.room_seq, room)
            ev = asyncio.Event()
            waiters.append(ev)
            try:
                await asyncio.wait_for(ev.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                return [], await asyncio.to_thread(self.store.room_seq, room)
            finally:
                try:
                    waiters.remove(ev)
                except ValueError:
                    pass
