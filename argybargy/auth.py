"""Access codes ("the code you give an agent"), stored in SQLite.

SQLite makes issue/revoke atomic, fixing a data-loss race the old JSON read-modify-write
had under concurrency. With ARGYBARGY_HASH_CODES=1 the code is hashed at rest, so a
leaked database exposes no usable credentials — in that mode a code is shown only once,
at creation, and the keys list shows a masked prefix.
"""
from __future__ import annotations

import hashlib
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .db import connect
from .settings import settings


@dataclass
class Peer:
    name: str
    room: str
    code: str
    capabilities: str = ""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _mask(code: str) -> str:
    return f"{code[:6]}…{code[-4:]}" if len(code) > 12 else "•••"


class CodeStore:
    def __init__(self, path: Path) -> None:
        self._lock = threading.Lock()
        self._db = connect(path)
        with self._lock:
            self._db.execute(
                """CREATE TABLE IF NOT EXISTS codes (
                    code TEXT PRIMARY KEY,
                    display TEXT NOT NULL,
                    name TEXT NOT NULL,
                    room TEXT NOT NULL DEFAULT 'default',
                    capabilities TEXT NOT NULL DEFAULT '',
                    created TEXT NOT NULL,
                    expires TEXT
                )"""
            )
            self._db.commit()

    def count(self) -> int:
        with self._lock:
            return int(self._db.execute("SELECT COUNT(*) AS n FROM codes").fetchone()["n"])

    def issue(self, name, room="default", expires_at=None, capabilities="") -> str:
        """Create a code and return the plaintext (shown once when hashing is enabled)."""
        plaintext = secrets.token_urlsafe(24)
        key = _hash(plaintext) if settings.hash_codes else plaintext
        display = _mask(plaintext) if settings.hash_codes else plaintext
        with self._lock:
            self._db.execute(
                "INSERT INTO codes (code, display, name, room, capabilities, created, expires) VALUES (?,?,?,?,?,?,?)",
                (key, display, name, room, capabilities or "",
                 _now().isoformat(timespec="seconds"),
                 expires_at.isoformat(timespec="seconds") if expires_at else None),
            )
            self._db.commit()
        return plaintext

    def resolve(self, code) -> Peer | None:
        if not code:
            return None
        with self._lock:  # match plaintext rows or hashed rows, so mode changes don't lock anyone out
            row = self._db.execute(
                "SELECT * FROM codes WHERE code = ? OR code = ?", (code, _hash(code))
            ).fetchone()
        if not row:
            return None
        exp = _parse_iso(row["expires"])
        if exp and _now() > exp:
            return None
        return Peer(name=row["name"], room=row["room"], code=code, capabilities=row["capabilities"] or "")

    def list(self) -> list:
        with self._lock:
            rows = self._db.execute(
                "SELECT display, name, room, capabilities, created, expires FROM codes ORDER BY created"
            ).fetchall()
        # 'code' carries the display value: full plaintext normally, or a masked prefix when hashing is on.
        return [{"code": r["display"], "name": r["name"], "room": r["room"],
                 "capabilities": r["capabilities"] or "", "created": r["created"],
                 "expires": r["expires"]} for r in rows]

    def capabilities_by_name(self, room: str) -> dict:
        with self._lock:
            rows = self._db.execute("SELECT name, capabilities FROM codes WHERE room = ?", (room,)).fetchall()
        return {r["name"]: (r["capabilities"] or "") for r in rows}

    def revoke(self, name_or_code: str) -> int:
        with self._lock:
            cur = self._db.execute(
                "DELETE FROM codes WHERE name = ? OR code = ? OR code = ?",
                (name_or_code, name_or_code, _hash(name_or_code)),
            )
            self._db.commit()
            return cur.rowcount
