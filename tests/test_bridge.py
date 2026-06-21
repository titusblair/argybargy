"""Offline checks for the bridge. Run with a temp data dir so it never touches ~/.argybargy:
    ARGYBARGY_DATA=$(mktemp -d) uv run --extra test pytest -q
"""
import types

from fastapi.testclient import TestClient

from argybargy import app as appmod
from argybargy.app import app
from argybargy.paths import DB_PATH
from argybargy.settings import settings
from argybargy.store import MessageStore

CODE_A = appmod.code_store.issue(name="a", room="default")
CODE_B = appmod.code_store.issue(name="b", room="default")
ADMIN = {"X-Admin-Token": appmod.ADMIN_TOKEN}
client = TestClient(app)


def auth(code):
    return {"Authorization": f"Bearer {code}"}


def test_health_and_manifest():
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["version"]
    body = client.get("/").json()
    assert "endpoints" in body and body["auth"]["header"].startswith("Authorization: Bearer")


def test_auth_required():
    assert client.get("/whoami").status_code == 401
    assert client.get("/whoami", headers=auth("nope")).status_code == 401


def test_whoami_and_capabilities():
    code = appmod.code_store.issue(name="cap", room="default", capabilities="reads QB; runs SQL")
    me = client.get("/whoami", headers=auth(code)).json()
    assert me == {"name": "cap", "room": "default", "capabilities": "reads QB; runs SQL"}
    peers = client.get("/peers", headers=auth(CODE_A)).json()["peers"]
    assert any(p["name"] == "cap" and "reads QB" in p["capabilities"] for p in peers)


def test_send_addressing_and_no_echo():
    assert client.post("/messages", headers=auth(CODE_A), json={"to": "b", "text": "ping"}).json()["ok"]
    got = client.get("/messages?since=0&wait=0", headers=auth(CODE_B)).json()
    assert "ping" in [m["text"] for m in got["messages"]]
    mine = client.get("/messages?since=0&wait=0", headers=auth(CODE_A)).json()
    assert all(m["from"] != "a" for m in mine["messages"])


def test_broadcast_seen_by_others():
    client.post("/messages", headers=auth(CODE_A), json={"to": "all", "text": "hello room"})
    got = client.get("/messages?since=0&wait=0", headers=auth(CODE_B)).json()
    assert "hello room" in [m["text"] for m in got["messages"]]


def test_expects_reply_defaults_and_override():
    code = appmod.code_store.issue(name="erp", room="default")
    assert client.post("/messages", headers=auth(code), json={"to": "all", "text": "fyi"}).json()["message"]["expects_reply"] == "none"
    assert client.post("/messages", headers=auth(code), json={"to": "b", "text": "hi"}).json()["message"]["expects_reply"] == "b"
    assert client.post("/messages", headers=auth(code), json={"to": "all", "text": "q", "expects_reply": "anyone"}).json()["message"]["expects_reply"] == "anyone"


def test_claim_is_atomic():
    seq = client.post("/messages", headers=auth(CODE_A), json={"to": "all", "text": "who?", "expects_reply": "anyone"}).json()["message"]["seq"]
    won = client.post(f"/messages/{seq}/claim", headers=auth(CODE_B))
    assert won.status_code == 200 and won.json()["won"] is True and won.json()["claimed_by"] == "b"
    lost = client.post(f"/messages/{seq}/claim", headers=auth(CODE_A))
    assert lost.status_code == 409 and lost.json()["claimed_by"] == "b"
    assert client.post("/messages/99999/claim", headers=auth(CODE_A)).status_code == 404


def test_rate_limit_429_with_retry_after():
    code = appmod.code_store.issue(name="flooder", room="default")
    last = None
    for i in range(settings.rate_max + 3):
        last = client.post("/messages", headers=auth(code), json={"to": "all", "text": f"s{i}"})
        if last.status_code == 429:
            break
    assert last.status_code == 429
    assert last.headers.get("Retry-After")
    assert last.json()["detail"]["error"] == "rate_limited"


def test_admin_requires_token_and_invite_revoke():
    assert client.get("/admin/state").status_code == 401
    r = client.post("/admin/invite", headers=ADMIN, json={"name": "carol", "capabilities": "researcher"})
    code = r.json()["code"]
    assert client.get("/whoami", headers=auth(code)).json()["name"] == "carol"
    state = client.get("/admin/state", headers=ADMIN).json()
    assert state["version"] and any(c["name"] == "carol" for c in state["codes"])
    assert client.post("/admin/revoke", headers=ADMIN, json={"target": "carol"}).json()["revoked"] >= 1
    assert client.get("/whoami", headers=auth(code)).status_code == 401


def test_admin_say_reaches_peers():
    client.post("/admin/say", headers=ADMIN, json={"room": "default", "to": "b", "text": "from the operator"})
    got = client.get("/messages?since=0&wait=0", headers=auth(CODE_B)).json()
    assert "from the operator" in [m["text"] for m in got["messages"]]


def test_admin_audit_and_stats():
    client.post("/admin/invite", headers=ADMIN, json={"name": "auditee"})
    events = client.get("/admin/audit", headers=ADMIN).json()["events"]
    assert any(e["action"] == "invite" for e in events)
    stats = client.get("/admin/stats", headers=ADMIN).json()
    assert stats["codes"] >= 1 and "messages" in stats and stats["version"]


def test_dashboard_served():
    r = client.get("/dashboard")
    assert r.status_code == 200 and "Argybargy" in r.text


def test_messages_persist_across_store_reopen():
    client.post("/messages", headers=auth(CODE_A), json={"to": "all", "text": "durable!"})
    reopened = MessageStore(DB_PATH)
    assert "durable!" in [m["text"] for m in reopened.history("default", 200)]


def test_retention_prunes_old_messages():
    import argybargy.store as st
    orig = st.settings
    st.settings = types.SimpleNamespace(max_messages_per_room=3)
    try:
        s = MessageStore(DB_PATH)
        for i in range(5):
            s.add("rettest", "x", "all", f"m{i}")
        texts = [m["text"] for m in s.history("rettest", 100)]
        assert texts == ["m2", "m3", "m4"]
    finally:
        st.settings = orig


def test_parse_expires_presets():
    import datetime as dt

    from argybargy.util import parse_expires
    assert parse_expires("never") is None and parse_expires(None) is None
    now = dt.datetime.now(dt.timezone.utc)
    mins = lambda s: (parse_expires(s) - now).total_seconds() / 60
    assert abs(mins("10m") - 10) < 1 and abs(mins("1d") - 1440) < 2
    assert abs(mins("1w") - 10080) < 5 and abs(mins("1mo") - 43200) < 60
    import pytest
    with pytest.raises(ValueError):
        parse_expires("bogus")


def test_hub_long_poll_wakes_on_post(tmp_path):
    import asyncio

    from argybargy.hub import Hub
    from argybargy.store import MessageStore
    h = Hub(MessageStore(tmp_path / "m.db"))

    async def scenario():
        async def delayed_post():
            await asyncio.sleep(0.2)
            await h.post("r", "y", "all", "wakeup")
        task = asyncio.create_task(delayed_post())
        msgs, _ = await h.read("r", "x", since=0, wait=5)
        await task
        return msgs

    msgs = asyncio.run(scenario())
    assert any(m["text"] == "wakeup" for m in msgs)


def test_hub_long_poll_times_out(tmp_path):
    import asyncio
    import time

    from argybargy.hub import Hub
    from argybargy.store import MessageStore
    h = Hub(MessageStore(tmp_path / "m2.db"))

    async def scenario():
        t0 = time.monotonic()
        msgs, _ = await h.read("r", "x", since=0, wait=1)
        return msgs, time.monotonic() - t0

    msgs, elapsed = asyncio.run(scenario())
    assert msgs == [] and elapsed >= 0.9


def test_expired_code_rejected():
    import datetime as dt
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    code = appmod.code_store.issue(name="ghost", room="default", expires_at=past)
    assert client.get("/whoami", headers=auth(code)).status_code == 401


def test_hash_codes_mode(tmp_path):
    import types

    import argybargy.auth as a
    from argybargy.auth import CodeStore
    orig = a.settings
    a.settings = types.SimpleNamespace(hash_codes=True)
    try:
        cs = CodeStore(tmp_path / "codes.db")
        code = cs.issue(name="secret", room="r")
        assert cs.resolve(code).name == "secret"          # resolves by plaintext
        row = cs.list()[0]
        assert row["code"] != code and "…" in row["code"]  # stored masked, not the real code
        assert cs.resolve("not-the-code") is None
    finally:
        a.settings = orig
