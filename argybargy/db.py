"""Shared SQLite connection factory.

All stores (messages, codes, audit) use the same WAL-mode database file. WAL lets the
server process and the CLI process read/write concurrently, and each store guards its
own connection with a lock. Opened with check_same_thread=False because FastAPI may call
from the event loop thread or a threadpool worker.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), check_same_thread=False, timeout=5.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("PRAGMA synchronous=NORMAL")
    return con
