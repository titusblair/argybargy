"""Dashboard: the operator inbox, above everything else in the sidebar.

Six agents asked a question on the same day, waited, heard nothing and each
decided alone. The questions were in six rooms and no screen ever showed them
together. These drive the screen that does.
"""
import json

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

ROOM = "inboxui"
OTHER = "inboxother"


@pytest.fixture(scope="module")
def inbox_room(client, admin_headers):
    codes = {}
    for name, room in [("asker", ROOM), ("farasker", OTHER)]:
        codes[name] = client.post("/admin/invite", headers=admin_headers,
                                  json={"name": name, "room": room}).json()["code"]
    seqs = {}
    seqs[ROOM] = client.post("/messages", headers={"Authorization": f"Bearer {codes['asker']}"},
                             json={"to": "all", "text": "move all 724 numbers to one provider?",
                                   "expects_reply": "anyone"}).json()["message"]["seq"]
    seqs[OTHER] = client.post("/messages", headers={"Authorization": f"Bearer {codes['farasker']}"},
                              json={"to": "all", "text": "safe to drop the old index?",
                                    "expects_reply": "anyone"}).json()["message"]["seq"]
    yield {"codes": codes, "seqs": seqs}
    for name in codes:
        client.post("/admin/revoke", headers=admin_headers, json={"target": name})


@pytest.fixture
def dash(page, live_server, admin_headers, inbox_room):
    token = admin_headers["X-Admin-Token"]
    page.add_init_script(f"localStorage.setItem('cc_admin', {token!r});")
    page.goto(f"{live_server}/dashboard?room={ROOM}")
    page.wait_for_selector(f'[data-testid="waiting-row"][data-goto-room="{ROOM}"]', timeout=15000)
    return page


def _row(page, room):
    return page.locator(f'[data-testid="waiting-row"][data-goto-room="{room}"]')


# ------------------------------------------------------------------- the list
def test_an_unanswered_question_shows_who_asked_and_what_they_asked(dash):
    row = _row(dash, ROOM)
    assert row.count() == 1
    assert "asker" in row.inner_text()
    assert row.locator('[data-testid="waiting-text"]').inner_text() == \
        "move all 724 numbers to one provider?"
    assert "#" + ROOM in row.inner_text()
    assert row.locator('[data-testid="waiting-timer"]').inner_text().strip() != ""


def test_a_question_in_a_room_you_are_not_looking_at_is_still_listed(dash):
    """The whole failure was information sitting in a room nobody had open."""
    assert _row(dash, OTHER).count() == 1


def test_the_count_matches_the_rows(dash):
    shown = dash.locator('[data-testid="waiting-row"]').count()
    label = dash.locator('[data-testid="waiting-count"]').inner_text()
    assert label.strip() == "· " + str(shown)


def test_the_inbox_sits_above_the_room_list(dash):
    """Who is blocked on me outranks which rooms exist."""
    assert dash.evaluate(
        "() => { var w = document.querySelector('[data-testid=\"waiting-list\"]');"
        "        var r = document.querySelector('[data-testid=\"room-list\"]');"
        "        return !!(w.compareDocumentPosition(r) & Node.DOCUMENT_POSITION_FOLLOWING); }")


def test_the_longest_wait_is_first(dash):
    """Server order, straight through: seconds descending."""
    secs = dash.evaluate(
        "() => window.__argy.waitingRows().map(function (w) { return w.seconds; })")
    assert secs == sorted(secs, reverse=True)


# ------------------------------------------------------------------- clicking
def test_clicking_a_row_opens_that_room_with_the_composer_focused(dash):
    _row(dash, OTHER).click()
    dash.wait_for_function(
        "room => { var e = document.querySelector('[data-testid=\"channel-title\"]');"
        "          return e && e.textContent === room; }", arg=OTHER, timeout=15000)
    assert dash.evaluate("document.activeElement.id") == "composerInput"
    # the room's own tail arrives on the next poll, so wait for it rather than race it
    dash.wait_for_function(
        "t => document.querySelector('.conv-timeline').innerText.indexOf(t) >= 0",
        arg="safe to drop the old index?", timeout=15000)


def test_answering_takes_the_row_away(dash, client, admin_headers):
    """Its own room, so the rest of this module still has something waiting."""
    room = "inboxanswered"
    code = client.post("/admin/invite", headers=admin_headers,
                       json={"name": "tempasker", "room": room}).json()["code"]
    client.post("/messages", headers={"Authorization": f"Bearer {code}"},
                json={"to": "all", "text": "which one?", "expects_reply": "anyone"})
    dash.wait_for_selector(f'[data-testid="waiting-row"][data-goto-room="{room}"]', timeout=15000)

    client.post("/admin/say", headers=admin_headers,
                json={"room": room, "to": "tempasker", "text": "no, keep the failover",
                      "expects_reply": "none"})
    dash.wait_for_function(
        "room => document.querySelectorAll("
        "  '[data-testid=\"waiting-row\"][data-goto-room=\"' + room + '\"]').length === 0",
        arg=room, timeout=15000)
    assert _row(dash, ROOM).count() == 1, "answering one must not clear the rest"
    client.post("/admin/revoke", headers=admin_headers, json={"target": "tempasker"})


# ------------------------------------------------------------------ loudness
def test_a_long_wait_reads_as_loud_and_a_fresh_one_does_not(dash, live_server):
    """Threshold is 5 minutes. Rewrites only the waiting list on the wire."""
    def fake(route):
        resp = route.fetch()
        body = resp.json()
        body["waiting"] = [
            {"room": "loudroom", "seq": 1, "ts": "2026-07-30T00:00:00+00:00", "from": "stuck",
             "to": "all", "text": "still waiting", "expects_reply": "anyone",
             "expects_reply_resolved": "anyone", "claimed_by": None, "waiting_seconds": 900.0},
            {"room": "freshroom", "seq": 2, "ts": "2026-07-30T00:00:00+00:00", "from": "new",
             "to": "all", "text": "just asked", "expects_reply": "anyone",
             "expects_reply_resolved": "anyone", "claimed_by": None, "waiting_seconds": 4.0},
        ]
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    dash.route("**/admin/state*", fake)
    dash.goto(f"{live_server}/dashboard?room={ROOM}")
    dash.wait_for_selector('[data-testid="waiting-row"][data-goto-room="loudroom"]', timeout=15000)
    assert _row(dash, "loudroom").get_attribute("data-loud") == "true"
    assert _row(dash, "freshroom").get_attribute("data-loud") == "false"
    colours = dash.evaluate(
        "() => ['loudroom', 'freshroom'].map(function (r) {"
        "  return getComputedStyle(document.querySelector("
        "    '[data-goto-room=\"' + r + '\"] [data-testid=\"waiting-timer\"]')).color; })")
    assert colours[0] != colours[1], "a long wait must not look like a fresh one"
    dash.unroute("**/admin/state*")


def test_nothing_waiting_renders_nothing_at_all(dash, live_server):
    """Not an empty box: an empty box teaches you to stop looking at the slot."""
    def empty(route):
        resp = route.fetch()
        body = resp.json()
        body["waiting"] = []
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body))

    dash.route("**/admin/state*", empty)
    dash.goto(f"{live_server}/dashboard?room={ROOM}")
    dash.wait_for_selector('[data-testid="room-list"]', timeout=15000)
    assert dash.locator('[data-testid="waiting-label"]').count() == 0
    assert dash.locator('[data-testid="waiting-list"]').count() == 0
    assert dash.locator('[data-testid="waiting-row"]').count() == 0
    dash.unroute("**/admin/state*")


# ----------------------------------------------------------- agent state pill
def test_an_agent_owed_a_reply_says_so_on_its_roster_row(dash):
    pill = dash.locator('[data-agent="asker"] [data-testid="agent-state"]')
    assert pill.count() == 1
    assert pill.get_attribute("data-state") == "waiting"
    assert pill.inner_text().strip().lower() == "waiting"
    # the state sits next to when it was last heard from, not instead of it
    assert dash.locator('[data-agent="asker"] [data-testid="last-seen"]').count() == 1


def _state(dash, agent, waiting=None):
    return dash.evaluate(
        "a => window.__argy.agentState(a.agent, a.waiting)",
        arg={"agent": agent, "waiting": waiting or {}})


def test_waiting_outranks_everything_else(dash):
    busy = {"name": "x", "online": True, "life": "online", "lastMessageSeconds": 1}
    assert _state(dash, busy) == "working"
    assert _state(dash, busy, {"x": True}) == "waiting"


def test_a_recent_post_reads_as_working_and_an_old_one_does_not(dash):
    assert _state(dash, {"name": "x", "online": True, "life": "online",
                         "lastMessageSeconds": 119}) == "working"
    assert _state(dash, {"name": "x", "online": True, "life": "online",
                         "lastMessageSeconds": 121}) == "standing"


def test_live_but_with_nothing_outstanding_is_standing_by(dash):
    """Finished its chunk, still polling, waiting to be dismissed."""
    assert _state(dash, {"name": "x", "online": True, "life": "online",
                         "lastMessageSeconds": None}) == "standing"


def test_an_agent_nobody_has_heard_from_gets_no_state_at_all(dash):
    """Offline and invited already say what they are. Naming a state would invent one."""
    assert _state(dash, {"name": "x", "online": False, "life": "offline",
                         "lastMessageSeconds": 10}) == ""
    assert _state(dash, {"name": "x", "online": False, "life": "unseen"}) == ""
