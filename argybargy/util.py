"""Small shared helpers."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone


def poll_budget(waited_seconds, room_quiet_seconds, max_idle_seconds: int, closed: bool) -> dict:
    """The safety valve, as one small pure function.

    An agent is meant to stay in a room until the operator closes it. The failure
    mode that creates is obvious: the operator forgets, and the agent polls until
    somebody notices the bill. So every poll comes back carrying how long the room
    has been silent and what the ceiling is, and ``should_exit`` says plainly when
    to stop. The agent is told, rather than being left to invent its own bound.

    Two clocks, and the larger one wins:

    - ``room_quiet_seconds``: since anyone last posted here. Durable, shared by
      everyone in the room, and reset by any message, so an operator can hold a
      room open indefinitely just by saying something.
    - ``waited_seconds``: since *this* agent last received anything. Covers the
      case the room clock cannot see: a room with no messages in it at all.

    A closed room always exits, whatever the clocks say. ``max_idle_seconds`` of 0
    disables the idle bound; closing still works.
    """
    waited = round(max(0.0, waited_seconds or 0.0), 1)
    quiet = round(max(0.0, room_quiet_seconds or 0.0), 1)
    idle = max(waited, quiet)
    should_exit, reason = False, None
    if closed:
        should_exit, reason = True, "room_closed"
    elif max_idle_seconds and idle >= max_idle_seconds:
        should_exit, reason = True, "idle_timeout"
    return {
        "waited_seconds": waited,
        "room_quiet_seconds": quiet,
        "idle_seconds": idle,
        "max_idle_seconds": max_idle_seconds,
        "seconds_left": (None if not max_idle_seconds else round(max(0.0, max_idle_seconds - idle), 1)),
        "should_exit": should_exit,
        "reason": reason,
    }

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
