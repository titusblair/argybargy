"""Small shared helpers."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

# Longest unit spellings first so e.g. "month" wins before "m"; bare number => hours.
_EXPIRES_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(months?|mo|weeks?|w|days?|d|hours?|hrs?|h|minutes?|mins?|m)?\s*$"
)


def parse_expires(s) -> datetime | None:
    """Parse a lifetime into a UTC deadline, or None for no expiry.

    Accepts the dashboard presets and free-form: 10m, 30m, 60m, 1d, 1w, 1mo, 'never'
    (also h/hours, plus a bare number = hours). Raises ValueError on anything else.
    """
    if s is None:
        return None
    s = str(s).strip().lower()
    if s in ("", "never", "none", "0"):
        return None
    m = _EXPIRES_RE.match(s)
    if not m:
        raise ValueError(f"Could not parse expires '{s}'. Use e.g. 10m, 30m, 60m, 1d, 1w, 1mo, or 'never'.")
    n = float(m.group(1))
    unit = m.group(2) or "h"  # bare number => hours (back-compat)
    if unit.startswith("mo"):
        delta = timedelta(days=30 * n)
    elif unit.startswith("w"):
        delta = timedelta(weeks=n)
    elif unit.startswith("d"):
        delta = timedelta(days=n)
    elif unit.startswith("h"):
        delta = timedelta(hours=n)
    else:
        delta = timedelta(minutes=n)
    return datetime.now(timezone.utc) + delta
