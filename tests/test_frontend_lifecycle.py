"""Dashboard: the room open/closed indicator, the operator's Close control, and
the model each agent is running.

Its own room and its own page, so closing a room here cannot disturb the shared
fixtures in test_frontend_dashboard.py.
"""
import time

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def lifecycle_room(client, admin_headers):
    room = "lifeui"
    codes = {}
    for name, caps in [("claude-life", "Opus 5 - feature build"),
                       ("codex-life", "GPT-5 - review")]:
        codes[name] = client.post("/admin/invite", headers=admin_headers,
                                  json={"name": name, "room": room, "capabilities": caps}
                                  ).json()["code"]
    auth = {"Authorization": f"Bearer {codes['claude-life']}"}
    for c in codes.values():
        client.get("/whoami", headers={"Authorization": f"Bearer {c}"})
    client.post("/messages", headers=auth,
                json={"to": "all", "text": "who takes this?", "expects_reply": "anyone"})
    yield {"room": room, "codes": codes}
    client.post(f"/admin/rooms/{room}/reopen", headers=admin_headers)


@pytest.fixture
def dash(page, live_server, admin_headers, lifecycle_room):
    token = admin_headers["X-Admin-Token"]
    page.add_init_script(f"localStorage.setItem('cc_admin', {token!r});")
    page.goto(f"{live_server}/dashboard?room={lifecycle_room['room']}")
    page.wait_for_selector('[data-testid="room-status"]', timeout=15000)
    return page


def _wait_status(page, want):
    page.wait_for_function(
        "want => { var e = document.querySelector('[data-testid=\"room-status\"]');"
        "          return e && e.getAttribute('data-status') === want; }",
        arg=want, timeout=15000)


# --------------------------------------------------------------- the indicator
def test_an_open_room_says_open_and_offers_to_close_it(dash, lifecycle_room):
    assert dash.locator('[data-testid="room-status"]').inner_text().strip().lower() == "open"
    assert dash.locator('[data-testid="room-status"]').get_attribute("data-status") == "open"
    btn = dash.locator('[data-testid="room-close-btn"]')
    assert btn.get_attribute("data-action") == "close"
    assert "Close room" in btn.inner_text()
    row = dash.locator(f'[data-room="{lifecycle_room["room"]}"]')
    assert row.get_attribute("data-status") == "open"


def test_closing_from_the_header_closes_the_room_for_real(dash, client, admin_headers, lifecycle_room):
    """Two clicks (it dismisses everybody), then the relay really is closed."""
    room = lifecycle_room["room"]
    btn = dash.locator('[data-testid="room-close-btn"]')
    btn.click()
    assert "Confirm close" in btn.inner_text()
    btn.click()
    _wait_status(dash, "closed")

    state = client.get("/admin/state", headers=admin_headers).json()
    assert state["room_status"][room]["status"] == "closed"

    assert dash.locator('[data-testid="room-status"]').inner_text().strip().lower() == "closed"
    assert "Reopen room" in dash.locator('[data-testid="room-close-btn"]').inner_text()

    client.post(f"/admin/rooms/{room}/reopen", headers=admin_headers)


def test_a_closed_room_reads_as_closed_in_the_sidebar(dash, client, admin_headers, lifecycle_room):
    """At a glance, not in a tooltip: the meta slot says so and the row is struck."""
    room = lifecycle_room["room"]
    client.post(f"/admin/rooms/{room}/close", headers=admin_headers, json={"by": "titus"})
    _wait_status(dash, "closed")

    row = dash.locator(f'[data-room="{room}"]')
    assert row.get_attribute("data-status") == "closed"
    assert "closed" in row.get_attribute("class")
    assert row.locator('[data-testid="room-meta"]').inner_text().strip().lower() == "closed"
    assert "titus" in (row.get_attribute("title") or "")
    struck = dash.evaluate(
        "room => getComputedStyle(document.querySelector('[data-room=\"' + room + '\"] .sb-room__name'))"
        ".textDecorationLine", arg=room)
    assert struck == "line-through"

    client.post(f"/admin/rooms/{room}/reopen", headers=admin_headers)
    _wait_status(dash, "open")


def test_reopening_from_the_header_takes_one_click(dash, client, admin_headers, lifecycle_room):
    room = lifecycle_room["room"]
    client.post(f"/admin/rooms/{room}/close", headers=admin_headers)
    _wait_status(dash, "closed")
    dash.locator('[data-testid="room-close-btn"]').click()
    _wait_status(dash, "open")
    assert client.get("/admin/state", headers=admin_headers).json()["room_status"][room]["status"] == "open"


def test_status_helper_treats_an_unknown_room_as_open(dash):
    """No record is the normal state of a room, not missing data."""
    assert dash.evaluate("window.__argy.isClosed('a-room-nobody-ever-closed')") is False
    assert dash.evaluate("window.__argy.roomStatus('a-room-nobody-ever-closed').status") == "open"


# ------------------------------------------------------------------ the model
def test_each_agent_row_shows_the_model_it_is_running(dash):
    caps = dash.locator('[data-agent="claude-life"] [data-testid="agent-caps"]')
    assert caps.count() == 1
    assert caps.inner_text().strip() == "Opus 5 - feature build"
    assert dash.locator('[data-agent="codex-life"] [data-testid="agent-caps"]'
                        ).inner_text().strip() == "GPT-5 - review"


def test_a_long_capability_string_cannot_stretch_the_row(dash, client, admin_headers, live_server):
    """Its own room, so the extra member cannot change what 'anyone' resolves to."""
    long_caps = "Opus 5 - " + "very long build description " * 12
    code = client.post("/admin/invite", headers=admin_headers,
                       json={"name": "verbose-life", "room": "verboseui",
                             "capabilities": long_caps}).json()["code"]
    client.get("/whoami", headers={"Authorization": f"Bearer {code}"})
    dash.goto(f"{live_server}/dashboard?room=verboseui")
    dash.wait_for_selector('[data-agent="verbose-life"]', timeout=15000)
    widths = dash.evaluate(
        "() => { var r = document.querySelector('[data-agent=\"verbose-life\"]');"
        "        return [r.getBoundingClientRect().width, r.scrollWidth, r.getBoundingClientRect().height]; }")
    assert widths[1] <= widths[0] + 1, "the row must not scroll sideways"
    assert widths[2] <= 56, f"row grew to {widths[2]}px"
    client.post("/admin/revoke", headers=admin_headers, json={"target": "verbose-life"})


# ------------------------------------------------------- expects_reply resolved
def test_an_open_question_names_the_only_agent_who_can_answer(dash):
    label = dash.locator('[data-badge="expects"]').first.inner_text().lower()
    assert "codex-life" in label
    assert "anyone" not in label


def test_the_badge_falls_back_when_the_relay_sends_no_resolved_value(dash):
    """Old payload, new page: nothing breaks, it just shows the raw value."""
    assert dash.evaluate(
        "() => { var m = {expects_reply:'anyone', ts:'x', seq:1, room:'r'};"
        "        return (m.expects_reply_resolved || m.expects_reply); }") == "anyone"


def test_a_closed_room_still_shows_its_history(dash, client, admin_headers, lifecycle_room):
    """Closing dismisses agents; it does not hide the conversation from the operator."""
    room = lifecycle_room["room"]
    client.post(f"/admin/rooms/{room}/close", headers=admin_headers)
    _wait_status(dash, "closed")
    assert "who takes this?" in dash.locator(".conv-timeline").inner_text()
    client.post(f"/admin/rooms/{room}/reopen", headers=admin_headers)


def test_the_operator_can_still_post_into_a_room_they_closed(dash, client, admin_headers, lifecycle_room):
    room = lifecycle_room["room"]
    client.post(f"/admin/rooms/{room}/close", headers=admin_headers)
    _wait_status(dash, "closed")
    stamp = f"parting note {time.monotonic_ns()}"
    dash.fill("#composerInput", stamp)
    dash.click("#sendBtn")
    dash.wait_for_function("t => document.querySelector('.conv-timeline').innerText.indexOf(t) >= 0",
                           arg=stamp, timeout=15000)
    client.post(f"/admin/rooms/{room}/reopen", headers=admin_headers)
