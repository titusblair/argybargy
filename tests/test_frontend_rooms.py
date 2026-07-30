"""Dashboard: closed rooms fold away, and there is one obvious way back to them.

Nine rooms closed in a single day is what made this necessary: the sidebar was
mostly archive. Its own rooms and its own page so nothing here disturbs the
shared fixtures in the other frontend modules.
"""
import pytest

playwright_api = pytest.importorskip("playwright.sync_api")

OPEN_ROOM = "hideopen"
SHUT_ROOM = "hideshut"
SHUT_TWO = "hideshut2"


@pytest.fixture(scope="module")
def hide_rooms(client, admin_headers):
    """One open room and two closed ones, all with traffic so they list."""
    codes = {}
    for name, room in [("keeper", OPEN_ROOM), ("goner", SHUT_ROOM), ("goner2", SHUT_TWO)]:
        codes[name] = client.post("/admin/invite", headers=admin_headers,
                                  json={"name": name, "room": room}).json()["code"]
        client.post("/messages", headers={"Authorization": f"Bearer {codes[name]}"},
                    json={"to": "all", "text": f"hello from {room}"})
    for room in (SHUT_ROOM, SHUT_TWO):
        client.post(f"/admin/rooms/{room}/close", headers=admin_headers, json={"by": "titus"})
    yield {"codes": codes}
    for room in (SHUT_ROOM, SHUT_TWO):
        client.post(f"/admin/rooms/{room}/reopen", headers=admin_headers)
    for name in codes:
        client.post("/admin/revoke", headers=admin_headers, json={"target": name})


@pytest.fixture
def dash(page, live_server, admin_headers, hide_rooms):
    token = admin_headers["X-Admin-Token"]
    # a fresh browser context per test, so localStorage starts empty and the
    # reveal preference cannot leak from one test into the next
    page.add_init_script(f"localStorage.setItem('cc_admin', {token!r});")
    page.goto(f"{live_server}/dashboard?room={OPEN_ROOM}")
    page.wait_for_selector(f'[data-room="{OPEN_ROOM}"]', timeout=15000)
    return page


# ------------------------------------------------------------------ the rule
def test_closed_rooms_are_hidden_by_default(dash):
    assert dash.locator(f'[data-room="{SHUT_ROOM}"]').count() == 0
    assert dash.locator(f'[data-room="{SHUT_TWO}"]').count() == 0
    assert dash.locator(f'[data-room="{OPEN_ROOM}"]').count() == 1


def test_the_toggle_says_how_many_are_hidden(dash):
    toggle = dash.locator('[data-testid="closed-toggle"]')
    assert toggle.count() == 1
    assert int(toggle.get_attribute("data-hidden")) >= 2
    assert "Closed" in toggle.inner_text()
    assert "hidden" in (toggle.get_attribute("title") or "")


def test_the_toggle_reveals_them_and_puts_them_back(dash):
    dash.click('[data-testid="closed-toggle"]')
    dash.wait_for_selector(f'[data-room="{SHUT_ROOM}"]', timeout=15000)
    assert dash.locator(f'[data-room="{SHUT_TWO}"]').count() == 1
    assert dash.locator(f'[data-room="{SHUT_ROOM}"]').get_attribute("data-status") == "closed"

    dash.click('[data-testid="closed-toggle"]')
    dash.wait_for_function(
        "room => document.querySelectorAll('[data-room=\"' + room + '\"]').length === 0",
        arg=SHUT_ROOM, timeout=15000)


def test_revealing_survives_a_reload(dash, live_server):
    """Same durability as the token and the theme: localStorage, not memory."""
    dash.click('[data-testid="closed-toggle"]')
    dash.wait_for_selector(f'[data-room="{SHUT_ROOM}"]', timeout=15000)
    assert dash.evaluate("localStorage.getItem('cc_showclosed')") == "1"

    dash.goto(f"{live_server}/dashboard?room={OPEN_ROOM}")
    dash.wait_for_selector(f'[data-room="{SHUT_ROOM}"]', timeout=15000)
    assert dash.locator('[data-testid="closed-toggle"]').get_attribute("aria-expanded") == "true"


def test_the_room_you_are_reading_is_not_yanked_away_when_it_closes(dash, live_server):
    """Closing dismisses the agents. It must not also close the tab you are on."""
    dash.goto(f"{live_server}/dashboard?room={SHUT_ROOM}")
    dash.wait_for_selector(f'[data-room="{SHUT_ROOM}"]', timeout=15000)
    row = dash.locator(f'[data-room="{SHUT_ROOM}"]')
    assert row.get_attribute("data-status") == "closed"
    assert row.get_attribute("aria-current") == "true"
    # the other closed room is still folded away, so this is not "hiding is off"
    assert dash.locator(f'[data-room="{SHUT_TWO}"]').count() == 0
    assert dash.locator('[data-testid="closed-toggle"]').get_attribute("data-hidden") == "1"


def test_an_all_open_sidebar_shows_no_toggle_at_all(dash, client, admin_headers, live_server):
    """Zero hidden means no control, not an empty control."""
    for room in (SHUT_ROOM, SHUT_TWO):
        client.post(f"/admin/rooms/{room}/reopen", headers=admin_headers)
    try:
        dash.goto(f"{live_server}/dashboard?room={OPEN_ROOM}")
        dash.wait_for_selector(f'[data-room="{SHUT_ROOM}"]', timeout=15000)
        assert dash.locator('[data-testid="closed-toggle"]').count() == 0
    finally:
        for room in (SHUT_ROOM, SHUT_TWO):
            client.post(f"/admin/rooms/{room}/close", headers=admin_headers, json={"by": "titus"})


# -------------------------------------------------------------- the pure rule
def _part(dash, rooms, closed, show, current):
    return dash.evaluate(
        "a => window.__argy.partitionRooms(a.rooms, function (r) { return a.closed.indexOf(r) >= 0; },"
        "                                  a.show, a.current)",
        arg={"rooms": rooms, "closed": closed, "show": show, "current": current})


def test_partition_hides_only_the_closed_ones(dash):
    got = _part(dash, ["a", "b", "c"], ["b"], False, "a")
    assert got == {"shown": ["a", "c"], "hidden": ["b"]}


def test_partition_keeps_the_current_room_even_when_closed(dash):
    got = _part(dash, ["a", "b"], ["a", "b"], False, "a")
    assert got == {"shown": ["a"], "hidden": ["b"]}


def test_partition_shows_everything_when_revealed(dash):
    got = _part(dash, ["a", "b"], ["a", "b"], True, "")
    assert got == {"shown": ["a", "b"], "hidden": []}


def test_partition_survives_an_empty_room_list(dash):
    assert _part(dash, [], [], False, "") == {"shown": [], "hidden": []}
