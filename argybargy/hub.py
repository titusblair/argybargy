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
from .util import seconds_since

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


def resolve_expects(expects_reply: str, sender: str, members) -> str:
    """Turn a vague "anyone" into a name when only one other agent could answer.

    ``expects_reply='anyone'`` is an open question. In a room of five that is
    exactly right, and the claim endpoint sorts out who takes it. In a room of two
    it is needlessly vague: there is only one agent who can answer, so say which.

    ``members`` is durable membership (code holders plus everyone who has posted),
    never live presence. An agent that finished its work and went quiet is still
    the one participant, and presence would have dropped it and left this vague.

    Anything other than 'anyone' comes back untouched, so a directed message and a
    plain 'none' are unaffected. Pure: no clock, no I/O.
    """
    if expects_reply != "anyone":
        return expects_reply
    others = sorted({m for m in members if m and m != sender})
    return others[0] if len(others) == 1 else "anyone"


def open_questions(questions, last_seq_by_sender, members_by_room, room_statuses,
                   now=None, limit=50, operators=("operator",)) -> list:
    """Which agents asked a question and have not had an answer, longest wait first.

    This exists because of a specific failure. Six agents posted a question on the
    same day, waited, got nothing back because the operator was elsewhere, and each
    decided alone. The information was in six rooms and nothing put it in front of a
    human. Every question is already in the store; the only thing missing was one
    list that says who is blocked and for how long.

    **A question counts as answered when the party it addressed speaks again in that
    room after it was asked.** Not a claim, not any traffic, not the asker's own
    follow-up: a message from whoever was asked. A named ``expects_reply`` is
    answered by that name; ``anyone`` is an open question, so any other participant
    speaking after it closes it. That rule needs nothing new stored, it reads the
    same message log everyone else reads, and it can never mark a question answered
    by a message that came before it.

    A claimed question stays on the list. A claim is a promise to answer, and an
    agent that claimed and then went quiet is exactly the case worth seeing; the row
    carries ``claimed_by`` so the operator can weigh it. A closed room is skipped
    entirely: its agents were dismissed, so nobody there is still waiting.

    ``operators`` names the humans. A question *asked by* a human is left out: this
    list answers "who is waiting on me", and the operator is not waiting on
    themselves. Rename the send-as identity in the composer and your own directed
    messages start showing up here, which is a visible artifact rather than a hidden
    rule, and still a real unanswered question.

    Pure apart from the default clock, so the suite drives it with a fixed ``now``.
    ``limit`` bounds the payload; the longest waits are the ones that survive it.
    """
    out = []
    for q in questions:
        room = q.get("room", "")
        if (room_statuses.get(room) or {}).get("status") == "closed":
            continue
        asker = q.get("from", "")
        if asker in operators:
            continue
        target = resolve_expects(q.get("expects_reply", "none") or "none", asker,
                                 members_by_room.get(room) or set())
        if target in ("", "none"):
            continue
        seq = int(q.get("seq", 0))
        replies = last_seq_by_sender.get(room) or {}
        if target == "anyone":
            answered = any(s > seq for name, s in replies.items() if name != asker)
        else:
            answered = replies.get(target, 0) > seq
        if answered:
            continue
        out.append({**q, "expects_reply_resolved": target,
                    "waiting_seconds": seconds_since(q.get("ts", ""), now)})
    out.sort(key=lambda r: (-r["waiting_seconds"], r["room"], r["seq"]))
    return out[:limit] if limit else out


class Hub:
    def __init__(self, store) -> None:
        self.store = store
        self._last_seen: dict = {}    # room -> {peer: monotonic ts}
        self._waiters: dict = {}      # room -> list[asyncio.Event]
        self._post_times: dict = {}   # rate-limit key -> list[monotonic ts]
        self._wait_started: dict = {}  # (room, peer) -> monotonic ts of the current dry stretch

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

    async def room_status(self, room) -> dict:
        return await asyncio.to_thread(self.store.room_status, room)

    async def set_room_status(self, room, status, actor="") -> dict:
        """Close or reopen a room, then wake every long-poll parked on it.

        The wake is the point. Without it an agent that is 2 seconds into a 25 second
        poll sits there for another 23 seconds after the operator has closed the room,
        which turns a clean exit into a stall.
        """
        row = await asyncio.to_thread(self.store.set_room_status, room, status, actor)
        self._wake(room)
        return row

    async def room_quiet_seconds(self, room):
        return await asyncio.to_thread(self.store.room_quiet_seconds, room)

    async def room_members(self, room) -> set:
        return set(await asyncio.to_thread(self.store.senders, room))

    async def read(self, room, peer, since, wait):
        """Long-poll. Returns ``(messages, cursor, room_status, waited_seconds)``.

        ``waited_seconds`` is how long this peer has gone without receiving anything,
        across polls, not just within this one. It is the per-poller half of the
        safety valve, and it is what bounds an agent parked on a room that has never
        had a message in it. Receiving a message resets it to zero.

        A closed room returns straight away even when ``wait`` is high: there is
        nothing left to wait for.
        """
        key = (room, peer)
        started = self._wait_started.setdefault(key, time.monotonic())
        deadline = time.monotonic() + max(0.0, wait)
        waiters = self._waiters.setdefault(room, [])

        async def _done(msgs):
            if msgs:
                self._wait_started.pop(key, None)
            cursor = await asyncio.to_thread(self.store.room_seq, room)
            status = await asyncio.to_thread(self.store.room_status, room)
            waited = 0.0 if msgs else round(time.monotonic() - started, 1)
            return msgs, cursor, status, waited

        while True:
            msgs = await asyncio.to_thread(self.store.since, room, peer, since)
            if msgs or wait <= 0:
                return await _done(msgs)
            status = await asyncio.to_thread(self.store.room_status, room)
            if status["status"] == "closed":
                return await _done([])
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return await _done([])
            ev = asyncio.Event()
            waiters.append(ev)
            try:
                await asyncio.wait_for(ev.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                return await _done([])
            finally:
                try:
                    waiters.remove(ev)
                except ValueError:
                    pass
