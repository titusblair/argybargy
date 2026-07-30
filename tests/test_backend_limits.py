"""Abuse limits and resource bounds: rate limiting, payload caps, quotas, retention."""
import types

import pytest

from argybargy.settings import settings


# --------------------------------------------------------------- rate limit
def test_rate_limit_returns_429_with_retry_after(client, make_code):
    _, auth = make_code("flooder")
    last = None
    for i in range(settings.rate_max + 3):
        last = client.post("/messages", headers=auth, json={"to": "all", "text": f"s{i}"})
        if last.status_code == 429:
            break
    assert last.status_code == 429
    assert last.headers.get("Retry-After") == str(int(settings.rate_window))
    detail = last.json()["detail"]
    assert detail["error"] == "rate_limited"
    assert detail["retry_after"] == int(settings.rate_window)


def test_rate_limit_is_per_agent_not_global(client, make_code):
    """One noisy agent must not lock everyone else out."""
    _, noisy = make_code("noisy")
    _, quiet = make_code("quiet")
    for i in range(settings.rate_max + 2):
        client.post("/messages", headers=noisy, json={"to": "all", "text": f"n{i}"})
    assert client.post("/messages", headers=quiet, json={"to": "all", "text": "still fine"}).status_code == 200


# -------------------------------------------------------------- payload caps
def test_oversized_message_is_rejected(client, make_code):
    _, auth = make_code("verbose")
    r = client.post("/messages", headers=auth, json={"to": "all", "text": "x" * (settings.max_text_len + 1)})
    assert r.status_code == 422


def test_message_at_the_size_limit_is_accepted(client, make_code):
    _, auth = make_code("exact-size")
    r = client.post("/messages", headers=auth, json={"to": "all", "text": "x" * settings.max_text_len})
    assert r.status_code == 200


def test_empty_message_is_rejected(client, make_code):
    _, auth = make_code("empty-sender")
    assert client.post("/messages", headers=auth, json={"to": "all", "text": ""}).status_code == 422


def test_oversized_capabilities_rejected(client, admin_headers):
    r = client.post("/admin/invite", headers=admin_headers, json={"name": "capsy", "capabilities": "x" * 401})
    assert r.status_code == 422


# ----------------------------------------------------------------- long poll
def test_wait_is_clamped_to_max_wait(client, make_code, monkeypatch):
    """A client asking to park for an hour must be capped at max_wait."""
    import argybargy.app as appmod
    seen = {}

    async def fake_read(room, peer, since, wait):
        seen["wait"] = wait
        return [], 0, {"name": room, "status": "open", "closed_at": None, "closed_by": None}, 0.0

    monkeypatch.setattr(appmod.hub, "read", fake_read)
    _, auth = make_code("patient")
    client.get("/messages?since=0&wait=99999", headers=auth)
    assert seen["wait"] == settings.max_wait


def test_history_limit_is_clamped_to_max_history(client, make_code, monkeypatch):
    import argybargy.app as appmod
    seen = {}

    async def fake_history(room, limit):
        seen["limit"] = limit
        return []

    monkeypatch.setattr(appmod.hub, "history", fake_history)
    _, auth = make_code("greedy")
    client.get("/history?limit=100000", headers=auth)
    assert seen["limit"] == settings.max_history


def test_history_rejects_nonpositive_limit(client, make_code):
    _, auth = make_code("zero-limit")
    assert client.get("/history?limit=0", headers=auth).status_code == 422


# -------------------------------------------------------------------- quotas
def test_code_quota_blocks_new_invites(client, admin_headers, monkeypatch):
    """Settings is a frozen dataclass, so swap in a modified copy."""
    import dataclasses

    import argybargy.app as appmod
    # Mint one so the store is definitely non-empty, then pin the cap to the current
    # count — the next invite is one too many regardless of test ordering.
    client.post("/admin/invite", headers=admin_headers, json={"name": "quota-filler"})
    current = appmod.code_store.count()
    assert current >= 1
    monkeypatch.setattr(appmod, "settings", dataclasses.replace(appmod.settings, max_codes=current))

    r = client.post("/admin/invite", headers=admin_headers, json={"name": "over-quota"})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "code_quota"
    client.post("/admin/revoke", headers=admin_headers, json={"target": "quota-filler"})


def test_room_quota_blocks_brand_new_rooms(client, make_code, monkeypatch):
    import dataclasses

    import argybargy.app as appmod
    _, auth = make_code("quota-pioneer", room="a-brand-new-room")
    monkeypatch.setattr(appmod, "settings", dataclasses.replace(appmod.settings, max_rooms=1))
    r = client.post("/messages", headers=auth, json={"to": "all", "text": "first here"})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "room_quota"


# ----------------------------------------------------------------- retention
def test_retention_prunes_oldest_messages_per_room(tmp_path):
    import argybargy.store as st
    from argybargy.store import MessageStore

    original = st.settings
    st.settings = types.SimpleNamespace(max_messages_per_room=3)
    try:
        store = MessageStore(tmp_path / "retention.db")
        for i in range(5):
            store.add("rettest", "sender", "all", f"m{i}")
        assert [m["text"] for m in store.history("rettest", 100)] == ["m2", "m3", "m4"]
    finally:
        st.settings = original


def test_retention_is_scoped_per_room(tmp_path):
    import argybargy.store as st
    from argybargy.store import MessageStore

    original = st.settings
    st.settings = types.SimpleNamespace(max_messages_per_room=2)
    try:
        store = MessageStore(tmp_path / "retention2.db")
        for i in range(3):
            store.add("roomA", "s", "all", f"a{i}")
        store.add("roomB", "s", "all", "b0")
        assert [m["text"] for m in store.history("roomA", 100)] == ["a1", "a2"]
        assert [m["text"] for m in store.history("roomB", 100)] == ["b0"]
    finally:
        st.settings = original


@pytest.mark.parametrize("bad", ["-1", "abc"])
def test_since_must_be_a_nonnegative_int(client, make_code, bad):
    _, auth = make_code(f"badsince-{bad}")
    assert client.get(f"/messages?since={bad}&wait=0", headers=auth).status_code == 422
