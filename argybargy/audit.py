"""Append-only audit log (SQLite): who did what, when.

Records security-relevant events — agent connects, key issue/revoke, claims, admin
actions — so an operator can answer "what happened?" after the fact.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path

from .db import connect


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class AuditLog:
    def __init__(self, path: Path) -> None:
        self._lock = threading.Lock()
        self._db = connect(path)
        with self._lock:
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT,
                    room TEXT,
                    detail TEXT
                )"""
            )
            self._db.commit()

    def log(self, action: str, actor: str = "", room: str = "", detail: str = "") -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO audit (ts, action, actor, room, detail) VALUES (?,?,?,?,?)",
                (_now_iso(), action, actor, room, detail),
            )
            self._db.commit()

    def recent(self, limit: int = 100) -> list:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM (SELECT ts, action, actor, room, detail FROM audit ORDER BY id DESC LIMIT ?) ORDER BY ts",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
