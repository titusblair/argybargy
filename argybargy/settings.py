"""Central configuration, read once from ARGYBARGY_* environment variables.

Keeping every tunable in one place makes the bridge easy to operate (12-factor style):
override anything with an env var, no code changes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError):
        return default


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _list(name: str) -> list:
    v = os.environ.get(name, "").strip()
    return [x.strip() for x in v.split(",") if x.strip()] if v else []


@dataclass(frozen=True)
class Settings:
    host: str = os.environ.get("ARGYBARGY_HOST", "127.0.0.1")
    port: int = _int("ARGYBARGY_PORT", 8765)
    log_level: str = os.environ.get("ARGYBARGY_LOG_LEVEL", "info")

    # messaging
    max_text_len: int = _int("ARGYBARGY_MAX_TEXT", 8000)
    max_wait: int = _int("ARGYBARGY_MAX_WAIT", 25)
    max_history: int = _int("ARGYBARGY_MAX_HISTORY", 500)
    max_messages_per_room: int = _int("ARGYBARGY_MAX_MESSAGES_PER_ROOM", 2000)  # 0 = unlimited
    online_window: int = _int("ARGYBARGY_ONLINE_WINDOW", 60)

    # rate limiting (per agent)
    rate_max: int = _int("ARGYBARGY_RATE_MAX", 10)
    rate_window: float = _float("ARGYBARGY_RATE_WINDOW", 10.0)

    # quotas (0 = unlimited)
    max_rooms: int = _int("ARGYBARGY_MAX_ROOMS", 0)
    max_codes: int = _int("ARGYBARGY_MAX_CODES", 0)

    # security
    hash_codes: bool = _bool("ARGYBARGY_HASH_CODES", False)
    cors_origins: tuple = tuple(_list("ARGYBARGY_CORS_ORIGINS"))
    docs: bool = _bool("ARGYBARGY_DOCS", True)  # serve /docs + /openapi.json


settings = Settings()
