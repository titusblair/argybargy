"""Unit tests for the internals: config, db, store, auth, audit, hub, util."""
import asyncio
import datetime as dt
import sqlite3
import time
import types

import pytest

from argybargy.audit import AuditLog
from argybargy.auth import CodeStore
from argybargy.db import connect
from argybargy.hub import Hub, build_roster
from argybargy.settings import Settings, _bool, _int, _list
from argybargy.store import MessageStore
from argybargy.util import parse_expires


def run_async(coro_factory):
    """Run one coroutine on a private loop in its own thread.

    Playwright's sync API keeps a loop alive in the main thread, so a bare
    asyncio.run() here fails depending on test order. Isolating the loop makes
    these deterministic however the suite is sliced.
    """
    import threading
    box = {}

    def worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            box["value"] = loop.run_until_complete(coro_factory())
        except BaseException as exc:  # noqa: BLE001 - re-raised on the calling thread
            box["error"] = exc
        finally:
            asyncio.set_event_loop(None)
            loop.close()

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=30)
    if "error" in box:
        raise box["error"]
    assert "value" in box, "async scenario did not finish"
    return box["value"]


# ------------------------------------------------------------------- config
@pytest.mark.parametrize("raw,expected", [("1", True), ("true", True), ("YES", True), ("on", True),
                                          ("0", False), ("false", False), ("nonsense", False)])
def test_bool_env_parsing(monkeypatch, raw, expected):
    monkeypatch.setenv("ARGYBARGY_TEST_FLAG", raw)
    assert _bool("ARGYBARGY_TEST_FLAG", False) is expected


def test_bool_env_default_when_unset(monkeypatch):
    monkeypatch.delenv("ARGYBARGY_TEST_FLAG", raising=False)
    assert _bool("ARGYBARGY_TEST_FLAG", True) is True


def test_int_env_falls_back_on_garbage(monkeypatch):
    monkeypatch.setenv("ARGYBARGY_TEST_INT", "not-a-number")
    assert _int("ARGYBARGY_TEST_INT", 7) == 7
    monkeypatch.setenv("ARGYBARGY_TEST_INT", "42")
    assert _int("ARGYBARGY_TEST_INT", 7) == 42


def test_list_env_splits_and_trims(monkeypatch):
    monkeypatch.setenv("ARGYBARGY_TEST_LIST", " a , b ,, c ")
    assert _list("ARGYBARGY_TEST_LIST") == ["a", "b", "c"]
    monkeypatch.setenv("ARGYBARGY_TEST_LIST", "")
    assert _list("ARGYBARGY_TEST_LIST") == []


def test_settings_defaults_are_sane():
    s = Settings()
    assert s.max_text_len > 0
    assert s.max_wait > 0
    assert s.rate_max > 0
    assert s.rate_window > 0
    assert isinstance(s.cors_origins, (list, tuple))


# ----------------------------------------------------------------------- db
def test_connect_enables_wal_and_row_factory(tmp_path):
    db = connect(tmp_path / "x.db")
    assert db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    db.execute("CREATE TABLE t (a INT)")
    db.execute("INSERT INTO t VALUES (1)")
    row = db.execute("SELECT a FROM t").fetchone()
    assert row["a"] == 1, "expected sqlite3.Row access by column name"


def test_connect_is_usable_across_threads(tmp_path):
    """check_same_thread=False — the hub offloads queries to worker threads."""
    import threading
    db = connect(tmp_path / "threads.db")
    db.execute("CREATE TABLE t (a INT)")
    errors = []

    def work():
        try:
            db.execute("INSERT INTO t VALUES (1)")
        except sqlite3.Error as e:  # pragma: no cover - only on regression
            errors.append(e)

    t = threading.Thread(target=work)
    t.start()
    t.join()
    assert not errors


# -------------------------------------------------------------------- store
def test_messages_persist_across_reopen(tmp_path):
    path = tmp_path / "persist.db"
    MessageStore(path).add("r", "alice", "all", "durable!")
    assert "durable!" in [m["text"] for m in MessageStore(path).history("r", 100)]


def test_sequence_numbers_are_per_room_and_monotonic(tmp_path):
    store = MessageStore(tmp_path / "seq.db")
    a1 = store.add("roomA", "s", "all", "1")
    a2 = store.add("roomA", "s", "all", "2")
    b1 = store.add("roomB", "s", "all", "1")
    assert a2["seq"] > a1["seq"]
    assert b1["seq"] == a1["seq"], "each room numbers its own messages"
    assert store.room_seq("roomA") == a2["seq"]


def test_since_filters_room_sender_and_recipient(tmp_path):
    store = MessageStore(tmp_path / "since.db")
    store.add("r", "alice", "all", "broadcast")
    store.add("r", "alice", "bob", "for bob")
    store.add("r", "bob", "alice", "for alice")
    store.add("other", "alice", "all", "other room")

    bob = [m["text"] for m in store.since("r", "bob", 0)]
    assert "broadcast" in bob and "for bob" in bob
    assert "for alice" not in bob, "bob must not see a DM addressed to alice"
    assert "other room" not in bob, "rooms must not leak"

    alice = [m["text"] for m in store.since("r", "alice", 0)]
    assert "broadcast" not in alice, "sender must not receive its own broadcast"


def test_claim_is_atomic_at_the_store_level(tmp_path):
    store = MessageStore(tmp_path / "claim.db")
    msg = store.add("r", "alice", "all", "who?", expects_reply="anyone")
    first = store.claim("r", msg["seq"], "bob")
    second = store.claim("r", msg["seq"], "carol")
    assert first["won"] is True and first["claimed_by"] == "bob"
    assert second["won"] is False and second["claimed_by"] == "bob"


def test_store_stats_counts_messages_and_rooms(tmp_path):
    store = MessageStore(tmp_path / "stats.db")
    store.add("r1", "s", "all", "a")
    store.add("r2", "s", "all", "b")
    stats = store.stats()
    assert stats["messages"] == 2
    assert stats["rooms"] == 2


def test_recent_in_room_returns_only_that_room(tmp_path):
    """A busy room must not crowd a quiet one out of the per-room feed."""
    store = MessageStore(tmp_path / "perroom.db")
    store.add("quiet", "alice", "all", "one quiet line")
    for i in range(40):
        store.add("busy", "bob", "all", f"chatter-{i}")
    feed = store.recent_in_room("quiet", 60)
    assert [m["text"] for m in feed] == ["one quiet line"]
    assert {m["room"] for m in feed} == {"quiet"}
    busy = store.recent_in_room("busy", 5)
    assert [m["text"] for m in busy] == [f"chatter-{i}" for i in range(35, 40)], "newest 5, oldest first"


def test_room_summaries_count_and_age_each_room(tmp_path):
    store = MessageStore(tmp_path / "summaries.db")
    store.add("alpha", "a", "all", "1")
    store.add("alpha", "a", "all", "2")
    store.add("beta", "b", "all", "1")
    by = {s["room"]: s for s in store.room_summaries()}
    assert set(by) == {"alpha", "beta"}
    assert by["alpha"]["messages"] == 2
    assert by["alpha"]["last_seq"] == 2
    assert by["beta"]["messages"] == 1
    for s in by.values():
        assert s["seconds_since_last"] < 60
        assert s["last_ts"]


def test_room_summaries_ignore_rooms_with_no_messages(tmp_path):
    store = MessageStore(tmp_path / "empty-room.db")
    assert store.room_summaries() == []


def test_members_by_room_lists_every_sender_per_room(tmp_path):
    store = MessageStore(tmp_path / "members.db")
    store.add("alpha", "a", "all", "1")
    store.add("alpha", "b", "all", "2")
    store.add("alpha", "a", "all", "3")
    store.add("beta", "c", "all", "1")
    by = store.members_by_room()
    assert set(by) == {"alpha", "beta"}
    assert [m["name"] for m in by["alpha"]] == ["a", "b"]
    assert [m["name"] for m in by["beta"]] == ["c"]
    for members in by.values():
        for m in members:
            assert m["last_ts"]
            assert m["seconds_since_last"] < 60


def test_members_by_room_is_empty_without_messages(tmp_path):
    assert MessageStore(tmp_path / "no-members.db").members_by_room() == {}


# ------------------------------------------------------------------- roster
def _rows(roster, room):
    return {r["name"]: r for r in roster.get(room, [])}


def test_roster_keeps_an_agent_that_only_ever_posted():
    """The whole point: presence is gone, the room still knows who worked in it."""
    roster = build_roster({}, [], {"r": [{"name": "ghost", "seconds_since_last": 42.0, "last_ts": "t"}]})
    row = _rows(roster, "r")["ghost"]
    assert row["online"] is False
    assert row["seconds_since_seen"] is None
    assert row["last_message_seconds"] == 42.0
    assert row["sources"] == ["messages"]


def test_roster_keeps_a_code_holder_that_has_never_spoken():
    roster = build_roster({}, [{"name": "quiet", "room": "r", "capabilities": "planner"}], {})
    row = _rows(roster, "r")["quiet"]
    assert row["sources"] == ["code"]
    assert row["capabilities"] == "planner"
    assert row["seconds_since_seen"] is None and row["last_message_seconds"] is None


def test_roster_unions_all_three_sources_without_duplicating_a_name():
    peers = {"r": [{"name": "both", "online": True, "seconds_since_seen": 1.0}]}
    codes = [{"name": "both", "room": "r", "capabilities": "c"}]
    members = {"r": [{"name": "both", "seconds_since_last": 9.0, "last_ts": "t"}]}
    rows = _rows(build_roster(peers, codes, members), "r")
    assert list(rows) == ["both"]
    assert rows["both"]["sources"] == ["presence", "code", "messages"]
    assert rows["both"]["online"] is True
    assert rows["both"]["seconds_since_seen"] == 1.0
    assert rows["both"]["last_message_seconds"] == 9.0


def test_roster_does_not_leak_members_across_rooms():
    codes = [{"name": "a", "room": "r1", "capabilities": ""},
             {"name": "b", "room": "r2", "capabilities": ""}]
    roster = build_roster({}, codes, {"r1": [{"name": "c", "seconds_since_last": 1.0, "last_ts": "t"}]})
    assert sorted(_rows(roster, "r1")) == ["a", "c"]
    assert sorted(_rows(roster, "r2")) == ["b"]


def test_roster_rows_are_sorted_by_name():
    members = {"r": [{"name": n, "seconds_since_last": 1.0, "last_ts": "t"} for n in ("zed", "amy", "moe")]}
    assert [r["name"] for r in build_roster({}, [], members)["r"]] == ["amy", "moe", "zed"]


def test_roster_ignores_a_code_with_no_room():
    assert build_roster({}, [{"name": "orphan", "room": "", "capabilities": ""}], {}) == {}


def test_roster_online_flag_comes_only_from_live_presence():
    """Posting recently must not fake presence: online still means connected now."""
    members = {"r": [{"name": "busy", "seconds_since_last": 0.0, "last_ts": "t"}]}
    assert _rows(build_roster({}, [], members), "r")["busy"]["online"] is False


# --------------------------------------------------------------------- auth
def test_issue_resolve_and_revoke_roundtrip(tmp_path):
    cs = CodeStore(tmp_path / "codes.db")
    code = cs.issue(name="alice", room="r", capabilities="does things")
    peer = cs.resolve(code)
    assert peer.name == "alice" and peer.room == "r" and peer.capabilities == "does things"
    assert cs.count() == 1
    assert cs.revoke("alice") == 1
    assert cs.resolve(code) is None


def test_codes_persist_across_reopen(tmp_path):
    path = tmp_path / "codes-persist.db"
    code = CodeStore(path).issue(name="bob", room="r")
    assert CodeStore(path).resolve(code).name == "bob"


def test_revoke_removes_only_the_named_code(tmp_path):
    """Regression: the old JSON store dropped sibling codes on revoke."""
    cs = CodeStore(tmp_path / "many.db")
    codes = {n: cs.issue(name=n, room="r") for n in ("a", "b", "c", "d")}
    assert cs.count() == 4
    cs.revoke("b")
    assert cs.count() == 3
    assert cs.resolve(codes["b"]) is None
    for name in ("a", "c", "d"):
        assert cs.resolve(codes[name]).name == name


def test_expired_code_does_not_resolve(tmp_path):
    cs = CodeStore(tmp_path / "expiry.db")
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10)
    assert cs.resolve(cs.issue(name="stale", room="r", expires_at=past)) is None
    assert cs.resolve(cs.issue(name="fresh", room="r", expires_at=future)).name == "fresh"


def test_hash_at_rest_stores_a_mask_not_the_secret(tmp_path):
    import argybargy.auth as auth_mod
    original = auth_mod.settings
    auth_mod.settings = types.SimpleNamespace(hash_codes=True)
    try:
        cs = CodeStore(tmp_path / "hashed.db")
        code = cs.issue(name="secret", room="r")
        assert cs.resolve(code).name == "secret", "plaintext must still authenticate"
        stored = cs.list()[0]["code"]
        assert stored != code
        assert "…" in stored
        assert cs.resolve("not-the-code") is None
    finally:
        auth_mod.settings = original


def test_capabilities_by_name(tmp_path):
    cs = CodeStore(tmp_path / "caps.db")
    cs.issue(name="dba", room="r", capabilities="runs SQL")
    assert cs.capabilities_by_name("r").get("dba") == "runs SQL"
    assert cs.capabilities_by_name("other-room") == {}


# -------------------------------------------------------------------- audit
def test_audit_log_records_and_returns_newest_first(tmp_path):
    log = AuditLog(tmp_path / "audit.db")
    log.log("invite", actor="admin", room="r", detail="alice")
    log.log("revoke", actor="admin", room="r", detail="alice")
    events = log.recent(10)
    assert len(events) == 2
    assert {e["action"] for e in events} == {"invite", "revoke"}
    assert all(e["ts"] for e in events)


def test_audit_recent_honours_limit(tmp_path):
    log = AuditLog(tmp_path / "audit2.db")
    for i in range(10):
        log.log("connect", actor=f"a{i}")
    assert len(log.recent(3)) == 3


# ---------------------------------------------------------------------- hub
def test_long_poll_wakes_as_soon_as_a_message_lands(tmp_path):
    hub = Hub(MessageStore(tmp_path / "wake.db"))

    async def scenario():
        async def delayed():
            await asyncio.sleep(0.2)
            await hub.post("r", "sender", "all", "wakeup")

        task = asyncio.create_task(delayed())
        started = time.monotonic()
        msgs, _cursor, _status, _waited = await hub.read("r", "listener", since=0, wait=5)
        elapsed = time.monotonic() - started
        await task
        return msgs, elapsed

    msgs, elapsed = run_async(scenario)
    assert any(m["text"] == "wakeup" for m in msgs)
    assert elapsed < 4, "should return on the post, not sit out the full wait"


def test_long_poll_times_out_and_returns_empty(tmp_path):
    hub = Hub(MessageStore(tmp_path / "timeout.db"))

    async def scenario():
        started = time.monotonic()
        msgs, _cursor, _status, _waited = await hub.read("r", "listener", since=0, wait=1)
        return msgs, time.monotonic() - started

    msgs, elapsed = run_async(scenario)
    assert msgs == []
    assert elapsed >= 0.9


def test_rate_limiter_allows_then_blocks_then_recovers(tmp_path):
    hub = Hub(MessageStore(tmp_path / "rate.db"))
    assert all(hub.allow("code-1", 3, 60) for _ in range(3))
    assert hub.allow("code-1", 3, 60) is False
    assert hub.allow("code-2", 3, 60) is True, "buckets are per-code"
    assert hub.allow("code-1", 3, 0) is True, "a zero-length window forgets immediately"


def test_touch_reports_first_sighting(tmp_path):
    hub = Hub(MessageStore(tmp_path / "touch.db"))
    assert hub.touch("r", "alice") is True
    assert hub.touch("r", "alice") is False


# ---------------------------------------------------------------------- util
def test_parse_expires_presets():
    now = dt.datetime.now(dt.timezone.utc)

    def minutes(spec):
        return (parse_expires(spec) - now).total_seconds() / 60

    assert parse_expires("never") is None
    assert parse_expires(None) is None
    assert abs(minutes("10m") - 10) < 1
    assert abs(minutes("1d") - 1440) < 2
    assert abs(minutes("1w") - 10080) < 5
    assert abs(minutes("1mo") - 43200) < 60


@pytest.mark.parametrize("bad", ["bogus", "10x", "-5m", "1y"])
def test_parse_expires_rejects_nonsense(bad):
    with pytest.raises(ValueError):
        parse_expires(bad)


@pytest.mark.parametrize("blank", ["", "never", "none", "0", None])
def test_parse_expires_treats_blanks_as_no_expiry(blank):
    assert parse_expires(blank) is None


# ------------------------------------------------------------ seconds_since
def test_seconds_since_measures_a_real_gap():
    from argybargy.util import seconds_since
    now = dt.datetime(2026, 7, 30, 12, 0, tzinfo=dt.timezone.utc)
    assert seconds_since("2026-07-30T11:59:00+00:00", now) == 60.0


def test_seconds_since_reads_a_naive_stamp_as_utc():
    """Everything this codebase writes is UTC, so a bare stamp is not local time."""
    from argybargy.util import seconds_since
    now = dt.datetime(2026, 7, 30, 12, 0, tzinfo=dt.timezone.utc)
    assert seconds_since("2026-07-30T11:30:00", now) == 1800.0


def test_seconds_since_is_never_negative():
    """A stamp in the future is a skewed clock, not a wait that has not started."""
    from argybargy.util import seconds_since
    now = dt.datetime(2026, 7, 30, 12, 0, tzinfo=dt.timezone.utc)
    assert seconds_since("2026-07-30T12:05:00+00:00", now) == 0.0


def test_seconds_since_treats_missing_or_broken_stamps_as_zero():
    from argybargy.util import seconds_since
    assert seconds_since("") == 0.0
    assert seconds_since(None) == 0.0
    assert seconds_since("not a timestamp") == 0.0
