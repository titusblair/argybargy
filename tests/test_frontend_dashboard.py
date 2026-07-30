"""Dashboard tests: static invariants, JS units, and real-browser behaviour.

Driven by Playwright *from pytest* — one toolchain (uv + pytest), no Node.
Install the browser once with:  uv run playwright install chromium
"""
import re

import pytest

from argybargy.dashboard import DASHBOARD_HTML

playwright_api = pytest.importorskip("playwright.sync_api")


# ============================================================ static analysis
# These need no browser: they guard the "single file, no build, offline" promise.

def test_page_is_self_contained_no_external_requests():
    external = re.findall(r'(?:src|href)\s*=\s*["\']?(?:https?:)?//', DASHBOARD_HTML)
    assert not external, f"dashboard must not reference external hosts: {external}"
    assert "@import" not in DASHBOARD_HTML
    assert not re.search(r'url\(\s*["\']?https?:', DASHBOARD_HTML)


def test_page_has_no_dynamic_code_execution():
    assert "eval(" not in DASHBOARD_HTML
    assert "new Function" not in DASHBOARD_HTML


def test_page_only_talks_to_the_five_admin_endpoints():
    called = set(re.findall(r'fetch\(\s*"(/[^"]*)"', DASHBOARD_HTML))
    called |= set(re.findall(r'api\(\s*"(/[^"]*)"', DASHBOARD_HTML))
    assert called == {
        "/admin/state", "/admin/say", "/admin/invite",
        "/admin/revoke", "/admin/regenerate-token",
    }, called


def test_no_unsubstituted_template_placeholders():
    for placeholder in ("__CSS__", "__ICONS__", "__LOGOS__"):
        assert placeholder not in DASHBOARD_HTML


def test_brand_and_title_present():
    assert "<title>Argybargy — Admin</title>" in DASHBOARD_HTML
    assert "Argybargy" in DASHBOARD_HTML


# ==================================================================== fixtures
@pytest.fixture(scope="session")
def seeded(client, admin_headers):
    """A room with vendor-branded agents, unbranded agents, and a claimed turn."""
    room = "uiroom"
    codes = {}
    for name, caps in [("claude-ui", "planner"), ("codex-ui", "reviewer"),
                       ("gemini-ui", "research"), ("hermes-ui", "no vendor logo")]:
        r = client.post("/admin/invite", headers=admin_headers,
                        json={"name": name, "room": room, "capabilities": caps})
        codes[name] = r.json()["code"]

    def auth(n):
        return {"Authorization": f"Bearer {codes[n]}"}

    for n in codes:
        client.get("/whoami", headers=auth(n))

    seq = client.post("/messages", headers=auth("claude-ui"),
                      json={"to": "all", "text": "ship it?", "expects_reply": "anyone"}
                      ).json()["message"]["seq"]
    client.post(f"/messages/{seq}/claim", headers=auth("codex-ui"))
    client.post("/messages", headers=auth("codex-ui"),
                json={"to": "claude-ui", "text": "regex bug first"})
    client.post("/messages", headers=auth("claude-ui"),
                json={"to": "all", "text": "fair enough", "expects_reply": "anyone"})
    client.post("/messages", headers=auth("hermes-ui"), json={"to": "all", "text": "unbranded here"})
    return {"room": room, "codes": codes}


@pytest.fixture
def dash(page, live_server, admin_headers, seeded):
    """Dashboard loaded, authenticated, parked on the seeded room."""
    token = admin_headers["X-Admin-Token"]
    page.add_init_script(f"localStorage.setItem('cc_admin', {token!r});")
    page.goto(f"{live_server}/dashboard")
    page.wait_for_selector(f'[data-room="{seeded["room"]}"]', timeout=15000)
    page.click(f'[data-room="{seeded["room"]}"]')
    page.wait_for_selector(".conv-msg", timeout=15000)
    return page


# ================================================================== JS units
# The dashboard exposes its pure helpers on window.__argy for testing.

def test_hue_is_deterministic_and_in_range(dash):
    a = dash.evaluate("window.__argy.hueFor('alice')")
    b = dash.evaluate("window.__argy.hueFor('alice')")
    c = dash.evaluate("window.__argy.hueFor('bob')")
    assert a == b
    assert a != c
    assert 0 <= a < 360


@pytest.mark.parametrize("seconds,expected", [(0, "now"), (0.4, "now"), (5, "5s"),
                                              (59, "59s"), (60, "1m"), (3599, "59m"), (7200, "2h")])
def test_last_seen_formatting(dash, seconds, expected):
    assert dash.evaluate(f"window.__argy.lastSeen({seconds})") == expected


@pytest.mark.parametrize("delta_ms,expected", [(0, "0:00"), (5000, "0:05"),
                                               (65000, "1:05"), (3600000, "60:00")])
def test_elapsed_formatting(dash, delta_ms, expected):
    assert dash.evaluate(f"window.__argy.elapsedSince(0, {delta_ms})") == expected


def test_elapsed_never_goes_negative(dash):
    assert dash.evaluate("window.__argy.elapsedSince(1000, 0)") == "0:00"


@pytest.mark.parametrize("name,expected", [
    ("claude-planner", "brand"), ("anthropic-bot", "brand"), ("codex-reviewer", "brand"),
    ("gpt-worker", "brand"), ("openai-x", "brand"), ("qwen-local", "brand"),
    ("gemini-scout", "brand"), ("cursor-dev", "brand"), ("opencode-x", "brand"),
    ("operator", "person"), ("some-human", "person"),
])
def test_known_vendors_and_person_resolve_to_glyphs(dash, name, expected):
    assert dash.evaluate(f"(window.__argy.glyphFor({name!r})||{{}}).kind") == expected


@pytest.mark.parametrize("name", ["hermes", "llama-farm", "mistral-worker", "zzz"])
def test_unknown_agents_fall_back_to_no_glyph(dash, name):
    """No glyph => the renderer draws the lettered monogram."""
    assert dash.evaluate(f"window.__argy.glyphFor({name!r})") is None
    assert dash.evaluate(f"window.__argy.brandAccent({name!r})") is None


def test_dedupe_keeps_the_liveliest_sighting(dash):
    result = dash.evaluate("""window.__argy.dedupe([
      {name:'a',room:'r1',life:'offline',online:false,secondsSinceSeen:90,hue:1,justJoined:false},
      {name:'a',room:'r2',life:'online', online:true, secondsSinceSeen:0, hue:1,justJoined:true},
      {name:'b',room:'r1',life:'fading', online:false,secondsSinceSeen:3, hue:2,justJoined:false}
    ]).map(function(x){return x.name+':'+x.life})""")
    assert sorted(result) == ["a:online", "b:fading"]


# ============================================================ rendering
def test_sidebar_lists_rooms_and_agents(dash, seeded):
    assert dash.locator(f'[data-room="{seeded["room"]}"]').count() == 1
    for name in seeded["codes"]:
        assert dash.locator(f'[data-agent="{name}"]').count() == 1, name


def test_vendor_agents_render_a_logo_and_unknown_ones_a_monogram(dash):
    assert dash.locator('[data-agent="claude-ui"] svg.agent-logo').count() == 1
    assert dash.locator('[data-agent="codex-ui"] svg.agent-logo').count() == 1
    assert dash.locator('[data-agent="hermes-ui"] svg.agent-logo').count() == 0
    assert dash.locator('[data-agent="hermes-ui"] .sb-av').inner_text().strip() == "HE"


def test_messages_render_with_claimed_and_expects_badges(dash):
    body = dash.locator(".conv-timeline").inner_text()
    assert "ship it?" in body
    assert "regex bug first" in body
    assert dash.locator('[data-badge="claimed"]').count() >= 1
    assert "codex-ui" in dash.locator('[data-badge="claimed"]').first.inner_text().lower()
    assert dash.locator('[data-badge="expects"]').count() >= 1
    assert re.match(r"\d+:\d{2}", dash.locator(".badge-pill__timer").first.inner_text())


def test_direct_messages_show_their_recipient(dash):
    assert "→ claude-ui" in dash.locator(".conv-timeline").inner_text()


def test_day_divider_is_labelled(dash):
    """Regression: the divider once rendered as two rules with no text."""
    divider = dash.locator(".conv-daydiv")
    assert divider.count() == 1
    assert divider.inner_text().strip().lower() == "today"


def test_no_element_has_numeric_attributes(dash):
    """A string passed in E()'s attrs slot would silently set attributes 0,1,2…"""
    stray = dash.evaluate(
        "Array.from(document.querySelectorAll('*')).flatMap(function(e){"
        "  return Array.from(e.attributes)"
        "    .map(function(a){return a.name})"
        "    .filter(function(n){return /^\\d+$/.test(n)})"
        "    .map(function(n){return e.tagName.toLowerCase()+'['+n+']'});"
        "})"
    )
    assert not stray, f"numeric attributes leaked from a mistyped E() call: {stray[:10]}"


def test_consecutive_messages_group_under_one_author(dash, client, admin_headers, seeded):
    code = seeded["codes"]["gemini-ui"]
    auth = {"Authorization": f"Bearer {code}"}
    for i in range(3):
        client.post("/messages", headers=auth, json={"to": "all", "text": f"grouped-{i}"})
    dash.wait_for_timeout(3500)
    group = dash.locator(".conv-group", has_text="grouped-0")
    assert group.count() >= 1
    assert group.first.locator(".conv-msg").count() >= 3, "one avatar, three message rows"


def test_empty_room_shows_a_friendly_placeholder(dash, client, admin_headers):
    client.post("/admin/invite", headers=admin_headers, json={"name": "lonely", "room": "emptyroom"})
    dash.wait_for_timeout(3500)
    dash.click('[data-room="emptyroom"]')
    assert "Nothing in #emptyroom yet" in dash.locator(".conv-empty").inner_text()


# ================================================================ per-room view
def test_room_rows_show_message_count_and_age(dash, seeded):
    row = dash.locator(f'[data-room="{seeded["room"]}"]')
    meta = row.locator('[data-testid="room-meta"]').inner_text()
    assert re.match(r"^\d+ · (now|\d+[smh])$", meta.strip()), meta
    assert "message" in (row.get_attribute("title") or "")


def test_selecting_a_room_filters_the_stream_to_that_room(dash, client, admin_headers):
    """The other room's traffic must not leak into the one on screen."""
    r = client.post("/admin/invite", headers=admin_headers,
                    json={"name": "other-room-agent", "room": "otherroom"})
    auth = {"Authorization": f"Bearer {r.json()['code']}"}
    client.post("/messages", headers=auth, json={"to": "all", "text": "only-in-otherroom"})

    dash.wait_for_selector('[data-room="otherroom"]', timeout=15000)
    dash.click('[data-room="otherroom"]')
    dash.wait_for_selector(".conv-msg", timeout=15000)
    assert dash.locator('[data-testid="channel-title"]').inner_text() == "otherroom"
    body = dash.locator(".conv-timeline").inner_text()
    assert "only-in-otherroom" in body
    assert "ship it?" not in body, "messages from the other room leaked in"

    dash.click('[data-room="uiroom"]')
    dash.wait_for_selector(".conv-msg", timeout=15000)
    back = dash.locator(".conv-timeline").inner_text()
    assert "ship it?" in back
    assert "only-in-otherroom" not in back


def test_selecting_a_room_updates_the_deep_link(dash, seeded):
    dash.click(f'[data-room="{seeded["room"]}"]')
    assert dash.evaluate("window.location.search") == f"?room={seeded['room']}"


def test_deep_link_opens_straight_into_that_room(page, live_server, admin_headers, seeded):
    """/dashboard?room=<name> is bookmarkable, so it must not land on room one."""
    token = admin_headers["X-Admin-Token"]
    page.add_init_script(f"localStorage.setItem('cc_admin', {token!r});")
    page.goto(f"{live_server}/dashboard?room={seeded['room']}")
    page.wait_for_selector(".conv-msg", timeout=15000)
    assert page.locator('[data-testid="channel-title"]').inner_text() == seeded["room"]
    assert page.locator(f'[data-room="{seeded["room"]}"]').get_attribute("aria-current") == "true"
    assert "ship it?" in page.locator(".conv-timeline").inner_text()


def test_header_shows_the_rooms_message_count(dash, seeded):
    dash.click(f'[data-room="{seeded["room"]}"]')
    count = dash.locator('[data-testid="room-count"]').inner_text()
    assert re.match(r"^\d+ msg · (now|\d+[smh]) ago$", count.strip()), count


# ============================================================== interaction
def test_clicking_an_agent_opens_a_filtered_direct_view(dash):
    dash.click('[data-agent="codex-ui"]')
    assert dash.locator('[data-testid="channel-title"]').inner_text() == "codex-ui"
    assert dash.locator(".conv-header__filterchip").count() == 1
    assert dash.locator("#composerInput").get_attribute("placeholder") == "Message @codex-ui"
    to_pill = dash.locator("#toPill")
    assert "codex-ui" in to_pill.inner_text()
    assert to_pill.is_disabled()
    dash.click("#backToRoom")
    assert dash.locator('[data-testid="channel-title"]').inner_text() == "uiroom"


def test_expects_pill_shows_the_default_the_server_will_actually_apply(dash):
    """With no explicit choice, the pill must show what admin_say/POST /messages
    will really set expects_reply to (see app.py's defaulting rule), not a dash
    that hides it. Broadcasting to the room defaults to "none"; targeting one
    peer defaults to that peer.
    """
    pill = dash.locator("#expectsPill")
    assert pill.inner_text() == "expects · none"
    assert "conv-pill--armed" not in (pill.get_attribute("class") or "")

    dash.click("#toPill")
    dash.click('[data-to="codex-ui"]')
    assert pill.inner_text() == "expects · codex-ui"
    assert "conv-pill--armed" not in (pill.get_attribute("class") or ""), \
        "same text as an explicit choice, but must not read as armed/explicit"


def test_expects_pill_cycles(dash):
    """Clicking still cycles null -> anyone -> <target> -> null. An explicit
    choice displays as itself and is visually marked armed; unpicking it
    (wrapping back to null) falls back to the default display, unarmed.
    """
    dash.click("#toPill")
    dash.click('[data-to="codex-ui"]')
    pill = dash.locator("#expectsPill")
    assert pill.inner_text() == "expects · codex-ui"  # default, unarmed

    pill.click()
    assert pill.inner_text() == "expects · anyone"
    assert "conv-pill--armed" in pill.get_attribute("class")

    pill.click()
    assert pill.inner_text() == "expects · codex-ui"  # explicit now, same text as default
    assert "conv-pill--armed" in pill.get_attribute("class")

    pill.click()
    assert pill.inner_text() == "expects · codex-ui"  # wrapped back to default
    assert "conv-pill--armed" not in pill.get_attribute("class")


def test_theme_toggle_applies_and_persists(dash, live_server):
    dash.click("#theme-light")
    assert dash.evaluate("document.documentElement.getAttribute('data-theme')") == "light"
    assert dash.evaluate("localStorage.getItem('cc_theme')") == "light"
    dash.reload()
    dash.wait_for_selector(".sb-root")
    assert dash.evaluate("document.documentElement.getAttribute('data-theme')") == "light"
    dash.click("#theme-dark")
    assert dash.evaluate("document.documentElement.getAttribute('data-theme')") == "dark"


def test_operator_can_send_a_message_to_the_room(dash, client, admin_headers, seeded):
    dash.fill("#composerInput", "operator says hello")
    dash.click("#sendBtn")
    dash.wait_for_timeout(500)
    assert dash.locator("#composerInput").input_value() == ""
    msgs = client.get("/admin/state", headers=admin_headers).json()["messages"]
    sent = [m for m in msgs if m["text"] == "operator says hello" and m["room"] == seeded["room"]]
    assert sent, "message should have reached the relay"
    assert sent[0]["from"] == "operator"


def test_mobile_viewport_collapses_the_sidebar_into_a_drawer(dash):
    dash.set_viewport_size({"width": 375, "height": 812})
    nav = dash.locator("#navWrap")
    assert "-translate-x-full" in nav.get_attribute("class")
    dash.click("#navOpen")
    assert "translate-x-0" in nav.get_attribute("class")
    assert dash.locator("#navScrim").is_visible()
    assert dash.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), \
        "no horizontal overflow on mobile"


# ============================================================== admin drawer
def test_drawer_mints_and_revokes_a_key(dash, client, admin_headers):
    dash.click("#openDrawer")
    dash.wait_for_selector("#adRoot")
    dash.fill("#adName", "ui-minted")
    dash.fill("#adCap", "made in the browser")
    dash.select_option("#adExpiry", "1d")
    dash.click("#adMint")
    dash.wait_for_selector(".ad-resultbox", timeout=10000)

    codes = client.get("/admin/state", headers=admin_headers).json()["codes"]
    minted = [c for c in codes if c["name"] == "ui-minted"]
    assert minted, "mint should have created a key"
    assert minted[0]["capabilities"] == "made in the browser"

    dash.wait_for_selector('[data-revoke="ui-minted"]', timeout=10000)
    dash.click('[data-revoke="ui-minted"]')           # arm
    dash.click('[data-revoke="ui-minted"]')           # confirm
    dash.wait_for_timeout(800)
    names = [c["name"] for c in client.get("/admin/state", headers=admin_headers).json()["codes"]]
    assert "ui-minted" not in names


def test_drawer_shows_public_url_and_key_count(dash, client, admin_headers):
    dash.click("#openDrawer")
    dash.wait_for_selector("#adRoot")
    assert dash.locator("#adUrl").inner_text().startswith("http")
    expected = len(client.get("/admin/state", headers=admin_headers).json()["codes"])
    assert dash.locator("#adKeyCount").inner_text().strip() == f"· {expected}"


def test_bad_token_surfaces_an_error_state(page, live_server):
    page.add_init_script("localStorage.setItem('cc_admin','totally-wrong');")
    page.goto(f"{live_server}/dashboard")
    page.wait_for_selector("#connDot.error", timeout=15000)
    assert page.locator('[data-agent]').count() == 0


# ==================================================================== security
def test_message_text_is_never_interpreted_as_html(dash, client, seeded):
    """Agent-supplied text must render as text — no injection into the operator's page."""
    payload = '<img src=x onerror="window.__xss=1"><script>window.__xss=1</script>'
    auth = {"Authorization": f"Bearer {seeded['codes']['claude-ui']}"}
    client.post("/messages", headers=auth, json={"to": "all", "text": payload})
    dash.wait_for_timeout(3500)
    assert dash.evaluate("window.__xss") is None, "agent text executed as script"
    assert dash.locator(".conv-timeline img").count() == 0
    assert payload in dash.locator(".conv-timeline").inner_text(), "should render literally"


def test_agent_names_are_never_interpreted_as_html(dash, client, admin_headers):
    evil = '<img src=x onerror="window.__xss2=1">'
    client.post("/admin/invite", headers=admin_headers, json={"name": evil, "room": "uiroom"})
    dash.wait_for_timeout(3500)
    assert dash.evaluate("window.__xss2") is None
    assert dash.locator(".sb-root img").count() == 0
    client.post("/admin/revoke", headers=admin_headers, json={"target": evil})


def test_capabilities_are_never_interpreted_as_html(dash, client, admin_headers):
    client.post("/admin/invite", headers=admin_headers,
                json={"name": "capsy-xss", "room": "uiroom",
                      "capabilities": '<img src=x onerror="window.__xss3=1">'})
    dash.click("#openDrawer")
    dash.wait_for_selector("#adRoot")
    dash.wait_for_timeout(3500)
    assert dash.evaluate("window.__xss3") is None
    assert dash.locator(".ad-kcap img").count() == 0
    client.post("/admin/revoke", headers=admin_headers, json={"target": "capsy-xss"})


def test_dashboard_makes_no_third_party_requests(page, live_server, admin_headers):
    seen = []
    page.on("request", lambda r: seen.append(r.url))
    token = admin_headers["X-Admin-Token"]
    page.add_init_script(f"localStorage.setItem('cc_admin', {token!r});")
    page.goto(f"{live_server}/dashboard")
    page.wait_for_selector(".sb-root")
    page.wait_for_timeout(1500)
    offsite = [u for u in seen if not u.startswith(live_server) and not u.startswith("data:")]
    assert not offsite, f"dashboard reached off-origin: {offsite}"


def test_page_has_no_console_errors(page, live_server, admin_headers):
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    token = admin_headers["X-Admin-Token"]
    page.add_init_script(f"localStorage.setItem('cc_admin', {token!r});")
    page.goto(f"{live_server}/dashboard")
    page.wait_for_selector(".sb-root")
    page.wait_for_timeout(2000)
    assert not errors, errors


# =============================================================== accessibility
def test_interactive_controls_have_accessible_names(dash):
    for selector in ('[data-room]', '[data-agent]', "#openDrawer", "#theme-auto", "#sendBtn"):
        el = dash.locator(selector).first
        name = el.get_attribute("aria-label") or el.inner_text().strip()
        assert name, f"{selector} has no accessible name"


def test_active_room_is_marked_for_assistive_tech(dash, seeded):
    active = dash.locator(f'[data-room="{seeded["room"]}"]')
    assert active.get_attribute("aria-current") == "true"
