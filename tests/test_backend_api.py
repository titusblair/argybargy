"""Agent-facing HTTP surface: discovery, auth, addressing, delivery, turn-taking."""
import datetime as dt

from argybargy.app import VERSION


# ----------------------------------------------------------------- discovery
def test_health_reports_ok_and_version(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["version"] == VERSION


def test_manifest_is_self_documenting_and_unauthenticated(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["auth"]["header"].startswith("Authorization: Bearer")
    paths = " ".join(str(v) for v in body["endpoints"])
    for expected in ("/messages", "/peers", "/whoami", "/history"):
        assert expected in paths


def test_openapi_and_docs_served_by_default(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


# ---------------------------------------------------------------------- auth
def test_protected_routes_reject_missing_and_bogus_codes(client):
    for path in ("/whoami", "/peers", "/history", "/messages?wait=0"):
        assert client.get(path).status_code == 401, path
        assert client.get(path, headers={"Authorization": "Bearer nope"}).status_code == 401, path


def test_malformed_authorization_header_rejected(client, make_code):
    code, _ = make_code("malformed")
    for value in (f"Basic {code}", "Bearer", "Bearer  ", "Bearer wrong"):
        assert client.get("/whoami", headers={"Authorization": value}).status_code == 401, value


def test_bare_code_without_bearer_prefix_is_accepted(client, make_code):
    """Documented leniency: agents that forget the 'Bearer ' prefix still work."""
    code, _ = make_code("lenient")
    assert client.get("/whoami", headers={"Authorization": code}).json()["name"] == "lenient"


def test_whoami_returns_identity_and_capabilities(client, make_code):
    _, auth = make_code("cap-agent", capabilities="reads QB; runs SQL")
    assert client.get("/whoami", headers=auth).json() == {
        "name": "cap-agent", "room": "default", "capabilities": "reads QB; runs SQL"
    }


def test_revoked_code_stops_working_immediately(client, make_code):
    code, auth = make_code("short-lived")
    assert client.get("/whoami", headers=auth).status_code == 200
    from argybargy.app import code_store
    code_store.revoke("short-lived")
    assert client.get("/whoami", headers=auth).status_code == 401


def test_expired_code_rejected(client, make_code):
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    _, auth = make_code("ghost", expires_at=past)
    assert client.get("/whoami", headers=auth).status_code == 401


# ------------------------------------------------------------------- peers
def test_peers_lists_roommates_with_presence_and_capabilities(client, make_code):
    _, a = make_code("peers-a", room="peersroom", capabilities="planner")
    _, b = make_code("peers-b", room="peersroom")
    client.get("/whoami", headers=a)
    client.get("/whoami", headers=b)
    peers = client.get("/peers", headers=a).json()["peers"]
    names = {p["name"] for p in peers}
    assert {"peers-a", "peers-b"} <= names
    me = next(p for p in peers if p["name"] == "peers-a")
    assert me["capabilities"] == "planner"
    assert me["online"] is True
    assert isinstance(me["seconds_since_seen"], (int, float))


def test_peers_never_leaks_other_rooms(client, make_code):
    _, inside = make_code("inside", room="roomx")
    make_code("outsider", room="roomy")
    client.get("/whoami", headers=inside)
    names = {p["name"] for p in client.get("/peers", headers=inside).json()["peers"]}
    assert "outsider" not in names


# ---------------------------------------------------------------- messaging
def test_direct_message_reaches_target(client, make_code):
    _, a = make_code("dm-a", room="dmroom")
    _, b = make_code("dm-b", room="dmroom")
    assert client.post("/messages", headers=a, json={"to": "dm-b", "text": "ping"}).json()["ok"]
    got = client.get("/messages?since=0&wait=0", headers=b).json()
    assert "ping" in [m["text"] for m in got["messages"]]


def test_sender_never_receives_its_own_message(client, make_code):
    _, a = make_code("echo-a", room="echoroom")
    make_code("echo-b", room="echoroom")
    client.post("/messages", headers=a, json={"to": "all", "text": "hello"})
    mine = client.get("/messages?since=0&wait=0", headers=a).json()["messages"]
    assert all(m["from"] != "echo-a" for m in mine)


def test_broadcast_reaches_every_other_peer(client, make_code):
    _, a = make_code("bc-a", room="bcroom")
    _, b = make_code("bc-b", room="bcroom")
    _, c = make_code("bc-c", room="bcroom")
    client.post("/messages", headers=a, json={"to": "all", "text": "hear ye"})
    for who in (b, c):
        texts = [m["text"] for m in client.get("/messages?since=0&wait=0", headers=who).json()["messages"]]
        assert "hear ye" in texts


def test_direct_message_is_not_visible_to_third_party(client, make_code):
    """A private DM must not leak to another agent in the same room."""
    _, a = make_code("priv-a", room="privroom")
    make_code("priv-b", room="privroom")
    _, c = make_code("priv-c", room="privroom")
    client.post("/messages", headers=a, json={"to": "priv-b", "text": "for your eyes only"})
    seen = [m["text"] for m in client.get("/messages?since=0&wait=0", headers=c).json()["messages"]]
    assert "for your eyes only" not in seen


def test_messages_never_cross_rooms(client, make_code):
    _, a = make_code("iso-a", room="iso-one")
    _, b = make_code("iso-b", room="iso-two")
    client.post("/messages", headers=a, json={"to": "all", "text": "room one only"})
    seen = [m["text"] for m in client.get("/messages?since=0&wait=0", headers=b).json()["messages"]]
    assert "room one only" not in seen
    assert "room one only" not in [m["text"] for m in client.get("/history", headers=b).json()["messages"]]


def test_cursor_advances_and_since_excludes_old_messages(client, make_code):
    _, a = make_code("cur-a", room="curroom")
    _, b = make_code("cur-b", room="curroom")
    client.post("/messages", headers=a, json={"to": "all", "text": "first"})
    first = client.get("/messages?since=0&wait=0", headers=b).json()
    cursor = first["cursor"]
    assert cursor > 0
    assert client.get(f"/messages?since={cursor}&wait=0", headers=b).json()["messages"] == []
    client.post("/messages", headers=a, json={"to": "all", "text": "second"})
    nxt = client.get(f"/messages?since={cursor}&wait=0", headers=b).json()
    assert [m["text"] for m in nxt["messages"]] == ["second"]
    assert nxt["cursor"] > cursor


def test_history_is_room_scoped_and_respects_limit(client, make_code):
    _, a = make_code("hist-a", room="histroom")
    for i in range(5):
        client.post("/messages", headers=a, json={"to": "all", "text": f"h{i}"})
    body = client.get("/history?limit=3", headers=a).json()
    assert body["room"] == "histroom"
    assert [m["text"] for m in body["messages"]] == ["h2", "h3", "h4"]


# -------------------------------------------------------------- turn-taking
def test_expects_reply_defaults_and_explicit_override(client, make_code):
    _, a = make_code("turn-a", room="turnroom")
    make_code("turn-b", room="turnroom")
    broadcast = client.post("/messages", headers=a, json={"to": "all", "text": "fyi"}).json()
    assert broadcast["message"]["expects_reply"] == "none"
    direct = client.post("/messages", headers=a, json={"to": "turn-b", "text": "hi"}).json()
    assert direct["message"]["expects_reply"] == "turn-b"
    open_q = client.post("/messages", headers=a,
                         json={"to": "all", "text": "q", "expects_reply": "anyone"}).json()
    assert open_q["message"]["expects_reply"] == "anyone"


def test_claim_is_atomic_first_responder_wins(client, make_code):
    _, a = make_code("claim-a", room="claimroom")
    _, b = make_code("claim-b", room="claimroom")
    _, c = make_code("claim-c", room="claimroom")
    seq = client.post("/messages", headers=a,
                      json={"to": "all", "text": "who?", "expects_reply": "anyone"}).json()["message"]["seq"]

    won = client.post(f"/messages/{seq}/claim", headers=b)
    assert won.status_code == 200
    assert won.json()["won"] is True
    assert won.json()["claimed_by"] == "claim-b"

    for loser in (c, a):
        lost = client.post(f"/messages/{seq}/claim", headers=loser)
        assert lost.status_code == 409
        assert lost.json()["won"] is False
        assert lost.json()["claimed_by"] == "claim-b"


def test_claim_unknown_sequence_is_404(client, make_code):
    _, a = make_code("claim-404", room="claim404room")
    assert client.post("/messages/999999/claim", headers=a).status_code == 404


def test_claim_cannot_reach_into_another_room(client, make_code):
    _, a = make_code("xr-a", room="xr-one")
    _, b = make_code("xr-b", room="xr-two")
    seq = client.post("/messages", headers=a,
                      json={"to": "all", "text": "mine", "expects_reply": "anyone"}).json()["message"]["seq"]
    assert client.post(f"/messages/{seq}/claim", headers=b).status_code == 404
