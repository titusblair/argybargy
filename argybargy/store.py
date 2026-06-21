"""Durable message storage (SQLite): messages, atomic claims, retention.

Survives restarts; the per-room cap (ARGYBARGY_MAX_MESSAGES_PER_ROOM) bounds disk
growth. Each method holds a lock only for the quick query — never across an ``await``.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

from .db import connect
from .settings import settings


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
