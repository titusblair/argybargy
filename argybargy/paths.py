"""Shared on-disk locations.

Runtime state lives in ~/.argybargy by default so that the `serve` process and
the `invite` CLI agree no matter which directory they're launched from. Override with
the ARGYBARGY_DATA environment variable.
"""
from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("ARGYBARGY_DATA") or (Path.home() / ".argybargy"))
URL_PATH = DATA_DIR / "url.txt"
DB_PATH = DATA_DIR / "argybargy.db"
ADMIN_TOKEN_PATH = DATA_DIR / "admin.token"
