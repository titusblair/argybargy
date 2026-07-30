"""Durable message storage (SQLite): messages, atomic claims, retention, room status.

Survives restarts; the per-room cap (ARGYBARGY_MAX_MESSAGES_PER_ROOM) bounds disk
growth. Each method holds a lock only for the quick query — never across an ``await``.

Room status lives here rather than in memory because "the operator closed this room"
has to outlive a restart. A room with no row is open, so rooms still come into
existence the way they always have: by somebody posting the first message.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

from .db import connect
from .settings import settings
from .util import seconds_since as _seconds_since


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MessageStore:
    def __init__(self, path: Path) -> None:
        self._lock = threading.Lock()
        self._db = connect(path)
        with self._lock:
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    ts TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    text TEXT NOT NULL,
                    expects_reply TEXT NOT NULL DEFAULT 'none',
                    claimed_by TEXT
                )"""
            )
            self._db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_msg_room_seq ON messages(room, seq)")
            cols = [r[1] for r in self._db.execute("PRAGMA table_info(messages)").fetchall()]
            if "expects_reply" not in cols:
                self._db.execute("ALTER TABLE messages ADD COLUMN expects_reply TEXT NOT NULL DEFAULT 'none'")
            if "claimed_by" not in cols:
                self._db.execute("ALTER TABLE messages ADD COLUMN claimed_by TEXT")
            # Partial index: almost every message expects nothing, so this only ever
            # holds the questions. It is what makes the waiting list cheap to build.
            # Created after the ALTER above, so an older database gets the column first.
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_msg_asking ON messages(expects_reply) "
                "WHERE expects_reply != 'none'"
            )
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS rooms (
                    room TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'open',
                    closed_at TEXT,
                    closed_by TEXT
                )"""
            )
            self._db.commit()

    @staticmethod
    def _to_msg(r):
        return {"seq": r["seq"], "ts": r["ts"], "from": r["sender"], "to": r["recipient"],
                "text": r["text"], "expects_reply": r["expects_reply"], "claimed_by": r["claimed_by"]}

    def add(self, room, sender, recipient, text, expects_reply="none") -> dict:
        with self._lock:
            seq = self._db.execute(
                "SELECT COALESCE(MAX(seq),0)+1 AS nxt FROM messages WHERE room=?", (room,)
            ).fetchone()["nxt"]
            ts = _now_iso()
            self._db.execute(
                "INSERT INTO messages (room,seq,ts,sender,recipient,text,expects_reply) VALUES (?,?,?,?,?,?,?)",
                (room, seq, ts, sender, recipient, text, expects_reply),
            )
            keep = settings.max_messages_per_room
            if keep and keep > 0:  # retention: bound disk growth per room
                self._db.execute(
                    "DELETE FROM messages WHERE room=? AND id NOT IN "
                    "(SELECT id FROM messages WHERE room=? ORDER BY id DESC LIMIT ?)",
                    (room, room, keep),
                )
            self._db.commit()
        return {"seq": seq, "ts": ts, "from": sender, "to": recipient, "text": text,
                "expects_reply": expects_reply, "claimed_by": None}

    def since(self, room, peer, since_seq) -> list:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM messages WHERE room=? AND seq>? AND sender!=? AND (recipient=? OR recipient='all') ORDER BY seq",
                (room, since_seq, peer, peer),
            ).fetchall()
        return [self._to_msg(r) for r in rows]

    def room_seq(self, room) -> int:
        with self._lock:
            return int(self._db.execute("SELECT COALESCE(MAX(seq),0) AS m FROM messages WHERE room=?", (room,)).fetchone()["m"])

    def history(self, room, limit) -> list:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM (SELECT * FROM messages WHERE room=? ORDER BY seq DESC LIMIT ?) ORDER BY seq",
                (room, limit),
            ).fetchall()
        return [self._to_msg(r) for r in rows]

    def recent(self, limit) -> list:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM (SELECT * FROM messages ORDER BY id DESC LIMIT ?) ORDER BY id", (limit,)
            ).fetchall()
        return [dict(room=r["room"], **self._to_msg(r)) for r in rows]

    def recent_in_room(self, room, limit) -> list:
        """Newest `limit` messages in one room, oldest first. This is the per-room feed.

        Same shape as ``recent`` (each row carries its room), so a caller can swap
        one for the other. Served straight off idx_msg_room_seq(room, seq).
        """
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM (SELECT * FROM messages WHERE room=? ORDER BY seq DESC LIMIT ?) ORDER BY seq",
                (room, limit),
            ).fetchall()
        return [dict(room=r["room"], **self._to_msg(r)) for r in rows]

    def room_summaries(self) -> list:
        """One row per room that has messages: volume, how long it has been quiet, status.

        Busiest-most-recent first. The GROUP BY rides the existing
        idx_msg_room_seq(room, seq) index, so no extra index is needed.
        """
        with self._lock:
            rows = self._db.execute(
                "SELECT room, COUNT(*) AS n, MAX(seq) AS last_seq, MAX(ts) AS last_ts "
                "FROM messages GROUP BY room"
            ).fetchall()
            status_rows = self._db.execute("SELECT room, status, closed_at, closed_by FROM rooms").fetchall()
        by_room = {r["room"]: r for r in status_rows}
        now = datetime.now(timezone.utc)
        out = []
        for r in rows:
            st = by_room.get(r["room"])
            closed = bool(st) and st["status"] == "closed"
            out.append({"room": r["room"], "messages": int(r["n"]), "last_seq": int(r["last_seq"]),
                        "last_ts": r["last_ts"], "seconds_since_last": _seconds_since(r["last_ts"], now),
                        "status": "closed" if closed else "open",
                        "closed_at": st["closed_at"] if closed else None,
                        "closed_by": st["closed_by"] if closed else None})
        out.sort(key=lambda s: (s["seconds_since_last"], s["room"]))
        return out

    # ----- room lifecycle -----

    def room_status(self, room) -> dict:
        """Is this room open or closed? A room with no row has never been closed.

        Returned shape is what ``GET /messages`` hands an agent, so the caller can
        pass it straight through: ``{name, status, closed_at, closed_by}``.
        """
        with self._lock:
            row = self._db.execute(
                "SELECT status, closed_at, closed_by FROM rooms WHERE room=?", (room,)
            ).fetchone()
        if row is None or row["status"] != "closed":
            return {"name": room, "status": "open", "closed_at": None, "closed_by": None}
        return {"name": room, "status": "closed", "closed_at": row["closed_at"], "closed_by": row["closed_by"]}

    def set_room_status(self, room, status, actor="") -> dict:
        """Close or reopen a room. Reopening clears who closed it and when."""
        closed = status == "closed"
        closed_at = _now_iso() if closed else None
        closed_by = (actor or "operator") if closed else None
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO rooms (room, status, closed_at, closed_by) VALUES (?,?,?,?)",
                (room, "closed" if closed else "open", closed_at, closed_by),
            )
            self._db.commit()
        return {"name": room, "status": "closed" if closed else "open",
                "closed_at": closed_at, "closed_by": closed_by}

    def room_statuses(self) -> dict:
        """Every room that has a status record, keyed by name. For the dashboard."""
        with self._lock:
            rows = self._db.execute("SELECT room, status, closed_at, closed_by FROM rooms").fetchall()
        out = {}
        for r in rows:
            closed = r["status"] == "closed"
            out[r["room"]] = {"name": r["room"], "status": "closed" if closed else "open",
                              "closed_at": r["closed_at"] if closed else None,
                              "closed_by": r["closed_by"] if closed else None}
        return out

    def room_quiet_seconds(self, room) -> float | None:
        """How long since anyone last posted here. None when the room has no messages.

        This is the durable half of the poll budget: it is the same number for every
        agent in the room, it survives a restart, and any message resets it.
        """
        with self._lock:
            row = self._db.execute("SELECT MAX(ts) AS ts FROM messages WHERE room=?", (room,)).fetchone()
        if not row or not row["ts"]:
            return None
        return _seconds_since(row["ts"], datetime.now(timezone.utc))

    def senders(self, room) -> list:
        """Everyone who has ever posted in one room. Durable membership, one room."""
        with self._lock:
            rows = self._db.execute("SELECT DISTINCT sender FROM messages WHERE room=?", (room,)).fetchall()
        return sorted(r["sender"] for r in rows)

    def members_by_room(self) -> dict:
        """Everyone who has ever posted, per room, with the age of their last message.

        This is the durable half of "who belongs to this room". Presence lives in
        memory and empties on restart; a sender row does not, so an agent that did
        its work and stopped is still a member of the room it worked in. Rides the
        existing idx_msg_room_seq(room, seq) index for the grouping.
        """
        with self._lock:
            rows = self._db.execute(
                "SELECT room, sender, MAX(ts) AS last_ts FROM messages GROUP BY room, sender"
            ).fetchall()
        now = datetime.now(timezone.utc)
        out: dict = {}
        for r in rows:
            out.setdefault(r["room"], []).append(
                {"name": r["sender"], "last_ts": r["last_ts"],
                 "seconds_since_last": _seconds_since(r["last_ts"], now)}
            )
        for members in out.values():
            members.sort(key=lambda m: m["name"])
        return out

    # ----- who is owed a reply -----

    def questions(self) -> list:
        """Every message that asked somebody to reply, oldest first, across all rooms.

        Half of the waiting list. Deliberately returns questions rather than
        *unanswered* questions: deciding what counts as an answer needs membership
        and is a rule, not a query, so it lives in ``hub.open_questions`` where the
        tests can drive it without a database. Served off idx_msg_asking.
        """
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM messages WHERE expects_reply != 'none' ORDER BY id"
            ).fetchall()
        return [dict(room=r["room"], **self._to_msg(r)) for r in rows]

    def last_seq_by_sender(self) -> dict:
        """Per room, the highest seq each sender has reached: {room: {sender: seq}}.

        The other half. "Has X replied to the question at seq N" is exactly
        "is X's highest seq in this room greater than N", which is one grouped
        query rather than a scan per question.
        """
        with self._lock:
            rows = self._db.execute(
                "SELECT room, sender, MAX(seq) AS last_seq FROM messages GROUP BY room, sender"
            ).fetchall()
        out: dict = {}
        for r in rows:
            out.setdefault(r["room"], {})[r["sender"]] = int(r["last_seq"])
        return out

    def claim(self, room, seq, peer) -> dict:
        """Atomically assign the responder for a message. First caller wins."""
        with self._lock:
            cur = self._db.execute(
                "UPDATE messages SET claimed_by=? WHERE room=? AND seq=? AND claimed_by IS NULL",
                (peer, room, seq),
            )
            self._db.commit()
            if cur.rowcount == 1:
                return {"won": True, "claimed_by": peer, "found": True}
            row = self._db.execute(
                "SELECT claimed_by FROM messages WHERE room=? AND seq=?", (room, seq)
            ).fetchone()
        if row is None:
            return {"won": False, "claimed_by": None, "found": False}
        return {"won": False, "claimed_by": row["claimed_by"], "found": True}

    def room_count(self) -> int:
        with self._lock:
            return int(self._db.execute("SELECT COUNT(DISTINCT room) AS n FROM messages").fetchone()["n"])

    def stats(self) -> dict:
        with self._lock:
            total = int(self._db.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"])
            rooms = int(self._db.execute("SELECT COUNT(DISTINCT room) AS n FROM messages").fetchone()["n"])
        return {"messages": total, "rooms": rooms}
