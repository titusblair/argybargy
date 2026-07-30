"""Admin surface: gating, key lifecycle, operator messages, audit, token rotation."""
import os
import stat

import pytest

from argybargy.app import VERSION

ADMIN_GETS = ["/admin/state", "/admin/stats", "/admin/audit"]
ADMIN_POSTS = [
    ("/admin/invite", {"name": "x"}),
    ("/admin/revoke", {"target": "x"}),
    ("/admin/say", {"text": "x"}),
    ("/admin/regenerate-token", {}),
]


# ------------------------------------------------------------------- gating
@pytest.mark.parametrize("path", ADMIN_GETS)
def test_admin_get_requires_token(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-Admin-Token": "wrong"}).status_code == 401


@pytest.mark.parametrize("path,body", ADMIN_POSTS)
def test_admin_post_requires_token(client, path, body):
    assert client.post(path, json=body).status_code == 401
    assert client.post(path, json=body, headers={"X-Admin-Token": "wrong"}).status_code == 401


def test_agent_code_is_not_admin_credential(client, make_code):
    """An agent bearer code must never unlock the admin surface."""
    code, _ = make_code("not-an-admin")
    assert client.get("/admin/state", headers={"X-Admin-Token": code}).status_code == 401


# ------------------------------------------------------------- key lifecycle
def test_invite_mints_working_key_with_room_and_capabilities(client, admin_headers):
    r = client.post("/admin/invite", headers=admin_headers,
                    json={"name": "carol", "room": "sales", "capabilities": "researcher"})
    assert r.status_code == 200
    body = r.json()
    code = body["code"]
    me = client.get("/whoami", headers={"Authorization": f"Bearer {code}"}).json()
    assert me == {"name": "carol", "room": "sales", "capabilities": "researcher"}
    client.post("/admin/revoke", headers=admin_headers, json={"target": "carol"})


def test_invite_rejects_bad_expiry(client, admin_headers):
    r = client.post("/admin/invite", headers=admin_headers, json={"name": "bad-exp", "expires": "bogus"})
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "bad_request"


def test_invite_accepts_expiry_presets(client, admin_headers):
    for preset in ("10m", "30m", "60m", "1d", "1w", "1mo", "never"):
        r = client.post("/admin/invite", headers=admin_headers,
                        json={"name": f"exp-{preset}", "expires": preset})
        assert r.status_code == 200, preset
        client.post("/admin/revoke", headers=admin_headers, json={"target": f"exp-{preset}"})


def test_revoke_by_name_then_code_invalidates_access(client, admin_headers):
    code = client.post("/admin/invite", headers=admin_headers, json={"name": "revoke-me"}).json()["code"]
    auth = {"Authorization": f"Bearer {code}"}
    assert client.get("/whoami", headers=auth).status_code == 200
    assert client.post("/admin/revoke", headers=admin_headers, json={"target": "revoke-me"}).json()["revoked"] >= 1
    assert client.get("/whoami", headers=auth).status_code == 401


def test_revoke_by_full_code_works(client, admin_headers):
    code = client.post("/admin/invite", headers=admin_headers, json={"name": "revoke-by-code"}).json()["code"]
    assert client.post("/admin/revoke", headers=admin_headers, json={"target": code}).json()["revoked"] >= 1
    assert client.get("/whoami", headers={"Authorization": f"Bearer {code}"}).status_code == 401


def test_revoke_unknown_target_is_zero_not_error(client, admin_headers):
    r = client.post("/admin/revoke", headers=admin_headers, json={"target": "never-existed"})
    assert r.status_code == 200
    assert r.json()["revoked"] == 0


# ------------------------------------------------------------------- state
def test_admin_state_shape(client, admin_headers):
    body = client.get("/admin/state", headers=admin_headers).json()
    for key in ("version", "public_url", "hash_codes", "peers", "roster", "codes", "messages", "rooms"):
        assert key in body, key
    assert body["version"] == VERSION
    assert isinstance(body["peers"], dict)
    assert isinstance(body["roster"], dict)
    assert isinstance(body["codes"], list)
    assert isinstance(body["rooms"], list)


# ------------------------------------------------------------------- roster
@pytest.fixture
def wipe_presence():
    """Drop the relay's in-memory presence, the way a restart does, then put it back.

    Presence is process state, so the only honest way to test "the roster survives a
    restart" in-process is to empty it. Restored afterwards so test order is free.
    """
    from argybargy import app as appmod
    kept = dict(appmod.hub._last_seen)
    yield lambda: appmod.hub._last_seen.clear()
    appmod.hub._last_seen.clear()
    appmod.hub._last_seen.update(kept)


def _roster_room(client, admin_headers, room):
    body = client.get("/admin/state", headers=admin_headers).json()
    return {r["name"]: r for r in body["roster"].get(room, [])}


def test_roster_still_lists_an_agent_after_presence_is_wiped(client, admin_headers, make_code, wipe_presence):
    """Titus's bug: the relay restarted, everyone had finished, the list went blank."""
    room = "roster-restart"
    _, auth = make_code("finished-worker", room=room)
    client.get("/whoami", headers=auth)
    client.post("/messages", headers=auth, json={"to": "all", "text": "did the work"})

    wipe_presence()
    rows = _roster_room(client, admin_headers, room)
    assert "finished-worker" in rows, "an agent that posted must not vanish with presence"
    row = rows["finished-worker"]
    assert row["online"] is False
    assert row["seconds_since_seen"] is None
    assert row["last_message_seconds"] is not None
    assert set(row["sources"]) == {"code", "messages"}


def test_roster_lists_a_code_holder_that_never_connected(client, admin_headers, make_code):
    room = "roster-invited"
    make_code("never-showed", room=room)
    rows = _roster_room(client, admin_headers, room)
    assert rows["never-showed"]["sources"] == ["code"]
    assert rows["never-showed"]["last_message_seconds"] is None


def test_roster_lists_a_sender_that_holds_no_code(client, admin_headers):
    """The operator posts through /admin/say and holds no code, but it is in the room."""
    room = "roster-operator"
    client.post("/admin/say", headers=admin_headers,
                json={"room": room, "to": "all", "text": "hello", "sender": "operator"})
    rows = _roster_room(client, admin_headers, room)
    assert "messages" in rows["operator"]["sources"]


def test_peers_endpoint_is_unchanged_and_stays_presence_only(client, admin_headers, make_code, wipe_presence):
    """/peers answers "who is live in my room". The roster must not have redefined it."""
    room = "roster-peers-contract"
    _, live = make_code("live-one", room=room)
    _, gone = make_code("gone-one", room=room)
    client.post("/messages", headers=gone, json={"to": "all", "text": "then left"})

    wipe_presence()
    client.get("/whoami", headers=live)     # only this one is present again
    body = client.get("/peers", headers=live).json()

    assert set(body) == {"room", "peers"}
    assert [p["name"] for p in body["peers"]] == ["live-one"], "/peers stays live-only"
    assert set(body["peers"][0]) == {"name", "online", "seconds_since_seen", "capabilities"}
    assert body["peers"][0]["online"] is True

    rows = _roster_room(client, admin_headers, room)
    assert sorted(rows) == ["gone-one", "live-one"], "the roster is the wider view, not /peers"


def test_admin_state_filters_messages_to_one_room(client, admin_headers, make_code):
    """?room=<name> scopes the feed, so a chatty room cannot bury a quiet one."""
    _, quiet = make_code("perroom-quiet", room="perroom-a")
    _, busy = make_code("perroom-busy", room="perroom-b")
    client.post("/messages", headers=quiet, json={"to": "all", "text": "quiet-line"})
    for i in range(20):
        client.post("/messages", headers=busy, json={"to": "all", "text": f"busy-line-{i}"})

    scoped = client.get("/admin/state?room=perroom-a", headers=admin_headers).json()
    assert scoped["room"] == "perroom-a"
    assert {m["room"] for m in scoped["messages"]} == {"perroom-a"}
    assert [m["text"] for m in scoped["messages"]] == ["quiet-line"]

    unscoped = client.get("/admin/state", headers=admin_headers).json()
    assert unscoped["room"] is None
    assert len({m["room"] for m in unscoped["messages"]}) > 1, "unscoped stays global"


def test_admin_state_summarises_every_room_with_messages(client, admin_headers, make_code):
    _, auth = make_code("summary-agent", room="summary-room")
    client.post("/messages", headers=auth, json={"to": "all", "text": "hello"})
    rooms = client.get("/admin/state", headers=admin_headers).json()["rooms"]
    mine = [r for r in rooms if r["room"] == "summary-room"]
    assert mine, "a room with messages must appear in the summary"
    assert mine[0]["messages"] >= 1
    assert mine[0]["last_seq"] >= 1
    assert mine[0]["seconds_since_last"] < 60


def test_admin_state_room_filter_still_requires_the_admin_token(client):
    assert client.get("/admin/state?room=anything").status_code == 401


def test_admin_stats_counts(client, admin_headers):
    body = client.get("/admin/stats", headers=admin_headers).json()
    assert body["version"] == VERSION
    assert body["codes"] >= 0
    assert body["uptime_seconds"] >= 0
    assert "messages" in body


# --------------------------------------------------------------- operator say
def test_admin_say_delivers_to_room(client, admin_headers, make_code):
    _, b = make_code("say-target", room="sayroom")
    client.post("/admin/say", headers=admin_headers,
                json={"room": "sayroom", "to": "all", "text": "from the operator"})
    texts = [m["text"] for m in client.get("/messages?since=0&wait=0", headers=b).json()["messages"]]
    assert "from the operator" in texts


def test_admin_say_supports_sender_and_expects_reply(client, admin_headers, make_code):
    _, b = make_code("say-b", room="sayroom2")
    client.post("/admin/say", headers=admin_headers,
                json={"room": "sayroom2", "to": "say-b", "text": "your turn",
                      "sender": "titus", "expects_reply": "say-b"})
    msgs = client.get("/messages?since=0&wait=0", headers=b).json()["messages"]
    got = next(m for m in msgs if m["text"] == "your turn")
    assert got["from"] == "titus"
    assert got["expects_reply"] == "say-b"


# -------------------------------------------------------------------- audit
def test_audit_records_invite_and_revoke(client, admin_headers):
    client.post("/admin/invite", headers=admin_headers, json={"name": "auditee"})
    client.post("/admin/revoke", headers=admin_headers, json={"target": "auditee"})
    events = client.get("/admin/audit", headers=admin_headers).json()["events"]
    actions = {e["action"] for e in events}
    assert "invite" in actions
    assert "revoke" in actions
    assert all({"ts", "action"} <= set(e) for e in events)


def test_audit_records_failed_admin_auth(client, admin_headers):
    client.get("/admin/state", headers={"X-Admin-Token": "definitely-wrong"})
    events = client.get("/admin/audit", headers=admin_headers).json()["events"]
    assert any("admin" in e["action"] and "fail" in e["action"] for e in events), \
        f"expected a failed-admin-auth event, saw {sorted({e['action'] for e in events})}"


def test_audit_limit_is_honoured(client, admin_headers):
    events = client.get("/admin/audit?limit=1", headers=admin_headers).json()["events"]
    assert len(events) <= 1


# ------------------------------------------------------- admin token on disk
def test_admin_token_file_is_owner_only():
    from argybargy.paths import ADMIN_TOKEN_PATH
    mode = stat.S_IMODE(os.stat(ADMIN_TOKEN_PATH).st_mode)
    assert mode == 0o600, f"admin token file is {oct(mode)}, expected 0o600"


def test_regenerate_rotates_token_and_invalidates_the_old_one(client, admin_headers):
    """Runs last-ish: mutates the shared header dict so later tests keep working."""
    old = admin_headers["X-Admin-Token"]
    new = client.post("/admin/regenerate-token", headers=admin_headers).json()["admin_token"]
    assert new and new != old
    admin_headers["X-Admin-Token"] = new          # keep the session fixture valid
    assert client.get("/admin/state", headers={"X-Admin-Token": old}).status_code == 401
    assert client.get("/admin/state", headers=admin_headers).status_code == 200
