"""Operator-controlled room lifecycle: close/reopen, the exit signal, the safety valve.

The behaviour under test is the whole point of the feature: an agent stays in a room
and keeps polling until the operator closes it, and it never polls forever if the
operator forgets. So these tests park a real long-poll and close the room underneath
it, rather than only asserting on the shape of a JSON body.
"""
import asyncio
import dataclasses
import threading
import time

import pytest

from argybargy.hub import Hub, resolve_expects
from argybargy.store import MessageStore
from argybargy.util import poll_budget

OPEN = {"status": "open", "closed_at": None, "closed_by": None}


def _idle_bound(monkeypatch, seconds: int) -> None:
    """Retune the idle bound for one test. Settings is frozen, so swap the whole object."""
    from argybargy import app as appmod
    monkeypatch.setattr(appmod, "settings",
                        dataclasses.replace(appmod.settings, max_idle_seconds=seconds))


def _status(client, auth):
    return client.get("/messages?since=0&wait=0", headers=auth).json()


@pytest.fixture
def room(client, admin_headers, make_code):
    """A fresh room with one agent in it, left open again afterwards."""
    name = f"lifecycle-{time.monotonic_ns()}"
    _, auth = make_code("lifer", room=name)
    client.post("/messages", headers=auth, json={"to": "all", "text": "here"})
    yield name, auth
    client.post(f"/admin/rooms/{name}/reopen", headers=admin_headers)


# ------------------------------------------------------------------- defaults
def test_a_room_nobody_closed_is_open(room, client):
    """Rooms are not created before use, so "no record" has to mean open."""
    name, auth = room
    body = _status(client, auth)
    assert body["room"] == {"name": name, **OPEN}
    assert body["room_closed"] is False
    assert body["should_exit"] is False
    assert body["exit_reason"] is None


def test_poll_response_stays_backward_compatible(room, client):
    """A caller that only knows messages+cursor must be unaffected."""
    name, auth = room
    body = _status(client, auth)
    assert set(body) >= {"messages", "cursor"}
    assert isinstance(body["messages"], list)
    assert isinstance(body["cursor"], int)


def test_peers_is_untouched_by_the_lifecycle(room, client, admin_headers):
    name, auth = room
    client.post(f"/admin/rooms/{name}/close", headers=admin_headers)
    body = client.get("/peers", headers=auth).json()
    assert set(body) == {"room", "peers"}


# ---------------------------------------------------------------- admin gating
@pytest.mark.parametrize("action", ["close", "reopen"])
def test_close_and_reopen_need_the_admin_token(client, action):
    assert client.post(f"/admin/rooms/anyroom/{action}").status_code == 401
    assert client.post(f"/admin/rooms/anyroom/{action}",
                       headers={"X-Admin-Token": "wrong"}).status_code == 401


@pytest.mark.parametrize("action", ["close", "reopen"])
def test_an_agent_code_cannot_close_a_room(client, make_code, action):
    code, _ = make_code("sneaky")
    assert client.post(f"/admin/rooms/anyroom/{action}",
                       headers={"X-Admin-Token": code}).status_code == 401


# ------------------------------------------------------------ close and reopen
def test_closing_tells_the_next_poll_to_leave(room, client, admin_headers):
    name, auth = room
    r = client.post(f"/admin/rooms/{name}/close", headers=admin_headers, json={"by": "titus"})
    assert r.status_code == 200
    assert r.json()["room"]["status"] == "closed"

    body = _status(client, auth)
    assert body["room_closed"] is True
    assert body["should_exit"] is True
    assert body["exit_reason"] == "room_closed"
    assert body["room"]["closed_by"] == "titus"
    assert body["room"]["closed_at"]
    assert body["poll_budget"]["reason"] == "room_closed"


def test_reopening_puts_the_room_back(room, client, admin_headers):
    name, auth = room
    client.post(f"/admin/rooms/{name}/close", headers=admin_headers)
    client.post(f"/admin/rooms/{name}/reopen", headers=admin_headers)
    body = _status(client, auth)
    assert body["room"] == {"name": name, **OPEN}
    assert body["should_exit"] is False
    assert client.post("/messages", headers=auth,
                       json={"to": "all", "text": "back"}).status_code == 200


def test_close_and_reopen_are_audited(room, client, admin_headers):
    name, _ = room
    client.post(f"/admin/rooms/{name}/close", headers=admin_headers, json={"by": "titus"})
    client.post(f"/admin/rooms/{name}/reopen", headers=admin_headers)
    events = client.get("/admin/audit?limit=200", headers=admin_headers).json()["events"]
    mine = {e["action"]: e for e in events if e["room"] == name}
    assert "room_close" in mine and "room_reopen" in mine
    assert mine["room_close"]["actor"] == "titus"
    assert mine["room_close"]["detail"], "the close records when it happened"


def test_admin_state_carries_status_per_room(room, client, admin_headers):
    name, _ = room
    client.post(f"/admin/rooms/{name}/close", headers=admin_headers)
    state = client.get("/admin/state", headers=admin_headers).json()
    assert state["room_status"][name]["status"] == "closed"
    summary = [r for r in state["rooms"] if r["room"] == name][0]
    assert summary["status"] == "closed"
    assert summary["closed_by"]


# -------------------------------------------------- posting to a closed room
def test_an_agent_posting_into_a_closed_room_is_told_so(room, client, admin_headers):
    """409, not a silent accept and not a silent drop. A late post is a mistake."""
    name, auth = room
    client.post(f"/admin/rooms/{name}/close", headers=admin_headers, json={"by": "titus"})
    r = client.post("/messages", headers=auth, json={"to": "all", "text": "one more thing"})
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["error"] == "room_closed"
    assert detail["closed_by"] == "titus"
    assert "titus" in detail["detail"]


def test_a_rejected_post_never_reaches_the_room(room, client, admin_headers):
    name, auth = room
    before = client.get("/history", headers=auth).json()["messages"]
    client.post(f"/admin/rooms/{name}/close", headers=admin_headers)
    client.post("/messages", headers=auth, json={"to": "all", "text": "should not land"})
    after = client.get("/history", headers=auth).json()["messages"]
    assert len(after) == len(before)
    assert not any(m["text"] == "should not land" for m in after)


def test_the_operator_can_still_speak_into_a_room_they_closed(room, client, admin_headers):
    name, auth = room
    client.post(f"/admin/rooms/{name}/close", headers=admin_headers)
    r = client.post("/admin/say", headers=admin_headers,
                    json={"room": name, "text": "closing this out, thanks all"})
    assert r.status_code == 200
    assert any(m["text"].startswith("closing this out")
               for m in client.get("/history", headers=auth).json()["messages"])


# ----------------------------------------------------------- the safety valve
def test_poll_budget_counts_down_and_then_says_leave():
    assert poll_budget(10, 20, 1800, closed=False)["should_exit"] is False
    assert poll_budget(10, 20, 1800, closed=False)["idle_seconds"] == 20
    assert poll_budget(10, 20, 1800, closed=False)["seconds_left"] == 1780
    tripped = poll_budget(10, 1800, 1800, closed=False)
    assert tripped["should_exit"] is True
    assert tripped["reason"] == "idle_timeout"
    assert tripped["seconds_left"] == 0


def test_poll_budget_takes_the_larger_of_the_two_clocks():
    """An empty room has no message clock, so the per-poller one has to carry it."""
    assert poll_budget(900, None, 600, closed=False)["should_exit"] is True
    assert poll_budget(0, 900, 600, closed=False)["should_exit"] is True
    assert poll_budget(100, 200, 600, closed=False)["idle_seconds"] == 200


def test_a_closed_room_always_exits_even_with_the_idle_bound_disabled():
    b = poll_budget(0, 0, 0, closed=True)
    assert b["should_exit"] is True
    assert b["reason"] == "room_closed"
    assert b["seconds_left"] is None


def test_zero_disables_the_idle_bound_but_not_closing():
    assert poll_budget(99999, 99999, 0, closed=False)["should_exit"] is False


def test_the_idle_bound_trips_over_http(room, client, admin_headers, monkeypatch):
    """End to end: the server, not the agent, decides the wait has gone on too long."""
    name, auth = room
    _idle_bound(monkeypatch, 1)
    time.sleep(1.1)
    body = _status(client, auth)
    assert body["should_exit"] is True
    assert body["exit_reason"] == "idle_timeout"
    assert body["room_closed"] is False, "left because it went quiet, not because it closed"


def test_a_message_resets_the_idle_clock(room, client, admin_headers, monkeypatch):
    name, auth = room
    _idle_bound(monkeypatch, 5)
    client.post("/admin/say", headers=admin_headers, json={"room": name, "text": "still here"})
    body = _status(client, auth)
    assert body["poll_budget"]["room_quiet_seconds"] < 5
    assert body["should_exit"] is False


def test_the_poll_reports_how_long_this_agent_has_waited(room, client):
    name, auth = room
    first = _status(client, auth)["poll_budget"]["waited_seconds"]
    time.sleep(1.1)
    second = _status(client, auth)["poll_budget"]["waited_seconds"]
    assert second > first, "the wait accumulates across polls, not within one"


# --------------------------------------------------- parked polls wake on close
def _run(coro_factory):
    """Run one coroutine on a private loop in its own thread.

    Playwright's sync API keeps a loop alive in the main thread, so a loop created
    here fails depending on test order. Same isolation trick as test_units.py.
    """
    box = {}

    def worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            box["out"] = loop.run_until_complete(coro_factory())
        except BaseException as e:      # noqa: BLE001 - re-raised on the calling thread
            box["err"] = e
        finally:
            loop.close()

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=60)
    if "err" in box:
        raise box["err"]
    return box["out"]


def test_a_parked_long_poll_wakes_the_moment_the_room_closes(tmp_path):
    hub = Hub(MessageStore(tmp_path / "close.db"))

    async def scenario():
        async def closer():
            await asyncio.sleep(0.2)
            await hub.set_room_status("r", "closed", "titus")

        task = asyncio.create_task(closer())
        started = time.monotonic()
        msgs, _cursor, status, _waited = await hub.read("r", "listener", since=0, wait=10)
        elapsed = time.monotonic() - started
        await task
        return msgs, status, elapsed

    msgs, status, elapsed = _run(scenario)
    assert msgs == []
    assert status["status"] == "closed"
    assert elapsed < 3, "must not sit out the rest of the timer after a close"


def test_a_poll_on_an_already_closed_room_returns_at_once(tmp_path):
    store = MessageStore(tmp_path / "shut.db")
    store.set_room_status("r", "closed", "titus")
    hub = Hub(store)

    async def scenario():
        started = time.monotonic()
        out = await hub.read("r", "listener", since=0, wait=10)
        return out, time.monotonic() - started

    (msgs, _cursor, status, _waited), elapsed = _run(scenario)
    assert msgs == [] and status["status"] == "closed"
    assert elapsed < 2


def test_waited_seconds_resets_when_a_message_arrives(tmp_path):
    hub = Hub(MessageStore(tmp_path / "reset.db"))

    async def scenario():
        _, _, _, first = await hub.read("r", "listener", since=0, wait=0)
        await asyncio.sleep(0.4)
        _, _, _, second = await hub.read("r", "listener", since=0, wait=0)
        await hub.post("r", "someone", "all", "hello")
        msgs, _, _, after = await hub.read("r", "listener", since=0, wait=0)
        _, _, _, fresh = await hub.read("r", "listener", since=1, wait=0)
        return first, second, msgs, after, fresh

    first, second, msgs, after, fresh = _run(scenario)
    assert second > first
    assert msgs and after == 0.0
    assert fresh < second, "the clock restarted from the delivery, it did not carry on"


def test_the_real_server_hands_a_parked_agent_its_exit(live_server, admin_headers, make_code):
    """The scenario from the brief, over HTTP: park, close, agent leaves.

    Threads rather than the test client, because the point is that one request is
    genuinely blocked while another closes the room out from under it.
    """
    import httpx

    name = f"parked-{time.monotonic_ns()}"
    _, auth = make_code("parker", room=name)
    httpx.post(f"{live_server}/messages", headers=auth, json={"to": "all", "text": "waiting"})

    out = {}

    def poller():
        started = time.monotonic()
        r = httpx.get(f"{live_server}/messages?since=99&wait=25", headers=auth, timeout=40)
        out["elapsed"] = time.monotonic() - started
        out["body"] = r.json()

    t = threading.Thread(target=poller)
    t.start()
    time.sleep(1.0)
    httpx.post(f"{live_server}/admin/rooms/{name}/close", headers=admin_headers, json={"by": "titus"})
    t.join(timeout=40)

    assert out["elapsed"] < 10, f"parked poll should wake on the close, took {out['elapsed']}s"
    assert out["body"]["should_exit"] is True
    assert out["body"]["exit_reason"] == "room_closed"
    assert out["body"]["room"]["closed_by"] == "titus"
    # and the agent that tries one last word is told, not ignored
    late = httpx.post(f"{live_server}/messages", headers=auth, json={"to": "all", "text": "wait!"})
    assert late.status_code == 409


# ------------------------------------------------------ expects_reply resolution
@pytest.mark.parametrize("expects,members,expected", [
    ("anyone", {"asker", "solo"}, "solo"),
    ("anyone", {"asker", "one", "two"}, "anyone"),
    ("anyone", {"asker"}, "anyone"),
    ("anyone", set(), "anyone"),
    ("none", {"asker", "solo"}, "none"),
    ("named", {"asker", "solo"}, "named"),
])
def test_resolve_expects(expects, members, expected):
    assert resolve_expects(expects, "asker", members) == expected


def test_anyone_resolves_to_the_only_other_agent_in_the_room(client, make_code, admin_headers):
    name = f"pair-{time.monotonic_ns()}"
    _, a = make_code("asker", room=name)
    _, b = make_code("answerer", room=name)
    client.post("/messages", headers=a, json={"to": "all", "text": "who can take this?",
                                              "expects_reply": "anyone"})
    body = client.get("/messages?since=0&wait=0", headers=b).json()
    msg = body["messages"][-1]
    assert msg["expects_reply"] == "anyone", "the stored value is untouched"
    assert msg["expects_reply_resolved"] == "answerer"


def test_anyone_stays_anyone_once_the_room_has_a_crowd(client, make_code):
    name = f"crowd-{time.monotonic_ns()}"
    _, a = make_code("asker", room=name)
    _, b = make_code("answerer", room=name)
    make_code("third", room=name)
    client.post("/messages", headers=a, json={"to": "all", "text": "anyone?",
                                              "expects_reply": "anyone"})
    msg = client.get("/messages?since=0&wait=0", headers=b).json()["messages"][-1]
    assert msg["expects_reply_resolved"] == "anyone"


def test_a_quiet_agent_still_counts_as_the_one_participant(client, make_code, admin_headers):
    """Membership is durable, so an agent that finished and went quiet still counts."""
    from argybargy import app as appmod
    name = f"quiet-{time.monotonic_ns()}"
    _, a = make_code("asker", room=name)
    _, b = make_code("answerer", room=name)
    client.get("/whoami", headers=b)
    appmod.hub._last_seen.pop(name, None)          # presence gone, membership is not
    client.post("/messages", headers=a, json={"to": "all", "text": "still there?",
                                              "expects_reply": "anyone"})
    msg = client.get("/messages?since=0&wait=0", headers=b).json()["messages"][-1]
    assert msg["expects_reply_resolved"] == "answerer"


def test_history_and_admin_state_resolve_it_too(client, make_code, admin_headers):
    name = f"hist-{time.monotonic_ns()}"
    _, a = make_code("asker", room=name)
    make_code("answerer", room=name)
    client.post("/messages", headers=a, json={"to": "all", "text": "hi", "expects_reply": "anyone"})
    hist = client.get("/history", headers=a).json()
    assert hist["messages"][-1]["expects_reply_resolved"] == "answerer"
    assert hist["room_status"]["status"] == "open"
    state = client.get(f"/admin/state?room={name}", headers=admin_headers).json()
    assert state["messages"][-1]["expects_reply_resolved"] == "answerer"


# --------------------------------------------------------------------- store
def test_store_room_status_defaults_to_open(tmp_path):
    store = MessageStore(tmp_path / "s.db")
    assert store.room_status("never-seen") == {"name": "never-seen", **OPEN}
    assert store.room_statuses() == {}


def test_store_close_then_reopen_clears_the_closer(tmp_path):
    store = MessageStore(tmp_path / "s2.db")
    closed = store.set_room_status("r", "closed", "titus")
    assert closed["status"] == "closed" and closed["closed_by"] == "titus" and closed["closed_at"]
    assert store.room_statuses()["r"]["status"] == "closed"
    reopened = store.set_room_status("r", "open", "titus")
    assert reopened == {"name": "r", **OPEN}
    assert store.room_status("r") == {"name": "r", **OPEN}


def test_store_room_status_survives_a_reopen_of_the_database(tmp_path):
    """Durable, not in-memory: a restart must not silently reopen every room."""
    path = tmp_path / "s3.db"
    MessageStore(path).set_room_status("r", "closed", "titus")
    assert MessageStore(path).room_status("r")["status"] == "closed"


def test_store_quiet_seconds_and_senders(tmp_path):
    store = MessageStore(tmp_path / "s4.db")
    assert store.room_quiet_seconds("r") is None, "no messages means no message clock"
    assert store.senders("r") == []
    store.add("r", "alice", "all", "hi")
    store.add("r", "bob", "all", "hello")
    store.add("other", "carol", "all", "elsewhere")
    assert store.room_quiet_seconds("r") is not None
    assert store.senders("r") == ["alice", "bob"]
