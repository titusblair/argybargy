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


# ============================================================= unauthenticated
@pytest.fixture
def anon(page, live_server, seeded):
    """Dashboard loaded with no admin token, so /admin/state answers 401."""
    page.add_init_script("localStorage.removeItem('cc_admin');")
    page.goto(f"{live_server}/dashboard")
    page.wait_for_selector('[data-testid="auth-required"]', timeout=15000)
    return page


def test_unauthenticated_dashboard_names_the_401(anon):
    """No token must not read as a quiet relay with an empty room."""
    text = anon.locator('[data-testid="auth-required"]').inner_text()
    assert "Not signed in" in text
    assert "401" in text
    assert "admin token" in text
    timeline = anon.locator(".conv-timeline").inner_text()
    assert "Nothing in #" not in timeline, "a 401 must not render as an empty room"
    assert anon.locator('[data-testid="channel-title"]').inner_text() == "not signed in"
    assert anon.locator('[data-testid="sidebar-auth-note"]').count() == 1


def test_auth_notice_points_at_the_token_field(anon):
    anon.click("#authOpenDrawer")
    anon.wait_for_selector("#adToken", timeout=15000)
    assert anon.evaluate("document.activeElement.id") == "adToken"


def test_a_valid_token_clears_the_auth_notice(dash):
    assert dash.locator('[data-testid="auth-required"]').count() == 0
    assert dash.locator('[data-testid="sidebar-auth-note"]').count() == 0


# ================================================== reaching the token field cold
def test_cold_load_hides_the_token_field_behind_the_drawer(anon):
    """The field does not exist until the drawer has been rendered once.

    That is the trap: on a never-authenticated load there is nothing on screen to
    type into, so the empty state has to both say where it is and get you there.
    """
    assert anon.evaluate("!!document.getElementById('adToken')") is False
    assert anon.locator('[data-testid="auth-where"]').count() == 1
    where = anon.locator('[data-testid="auth-where"]').inner_text()
    assert "admin drawer" in where and "gear" in where


def test_the_cold_cta_opens_the_drawer_and_selects_the_field(anon):
    """Focus alone is not enough: a wrong token in the box must be replaced."""
    anon.click("#authOpenDrawer")
    anon.wait_for_selector("#adToken", timeout=15000)
    anon.fill("#adToken", "a-stale-value")
    anon.click("#adClose")
    anon.click("#authOpenDrawer")
    assert anon.evaluate("document.activeElement.id") == "adToken"
    selected = anon.evaluate(
        "() => { var f = document.getElementById('adToken');"
        "return f.value.substring(f.selectionStart, f.selectionEnd); }"
    )
    assert selected == "a-stale-value", "a paste must overwrite, not append"


def test_the_cold_path_works_on_a_phone_sized_viewport(page, live_server, seeded):
    """The gear lives in an off-canvas sidebar on mobile, so the CTA is the only route."""
    page.set_viewport_size({"width": 375, "height": 720})
    page.add_init_script("localStorage.removeItem('cc_admin');")
    page.goto(f"{live_server}/dashboard")
    page.wait_for_selector('[data-testid="auth-required"]', timeout=15000)
    assert page.locator("#authOpenDrawer").is_visible()
    page.click("#authOpenDrawer")
    page.wait_for_selector("#adToken", timeout=15000)
    assert page.locator("#adToken").is_visible()


def test_the_gear_says_a_token_is_needed_while_locked_out(anon):
    gear = anon.locator("#openDrawer")
    assert "admin token" in (gear.get_attribute("aria-label") or "")
    assert "token" in (gear.get_attribute("title") or "")


def test_the_gear_label_goes_back_to_normal_once_signed_in(dash):
    assert dash.locator("#openDrawer").get_attribute("aria-label") == "Open admin drawer"


# ======================================================= saving a token reports back
@pytest.fixture
def anon_drawer(anon):
    """Cold dashboard with the admin drawer open on the token field."""
    anon.click("#authOpenDrawer")
    anon.wait_for_selector("#adToken", timeout=15000)
    return anon


def test_saving_a_rejected_token_says_it_was_rejected(anon_drawer):
    """Silence on a bad token is what made Save look like a dead button."""
    anon_drawer.fill("#adToken", "not-the-admin-token")
    anon_drawer.click("#adSaveToken")
    anon_drawer.wait_for_selector('[data-testid="token-save-note"]', timeout=15000)
    note = anon_drawer.locator('[data-testid="token-save-note"]')
    anon_drawer.wait_for_function(
        "() => { var n = document.querySelector('[data-testid=\"token-save-note\"]');"
        "return n && n.innerText.indexOf('rejected') >= 0; }",
        timeout=15000,
    )
    text = note.inner_text()
    assert "rejected" in text
    assert "401" in text
    assert "argybargy token" in text, "must say how to find the real one"
    assert "ad-errorbox" in (note.get_attribute("class") or "")


def test_saving_an_empty_token_says_the_field_was_empty(anon_drawer):
    anon_drawer.fill("#adToken", "   ")
    anon_drawer.click("#adSaveToken")
    anon_drawer.wait_for_function(
        "() => { var n = document.querySelector('[data-testid=\"token-save-note\"]');"
        "return n && n.innerText.indexOf('No token entered') >= 0; }",
        timeout=15000,
    )


def test_saving_a_good_token_confirms_visibly(anon_drawer, admin_headers):
    anon_drawer.fill("#adToken", admin_headers["X-Admin-Token"])
    anon_drawer.click("#adSaveToken")
    anon_drawer.wait_for_function(
        "() => { var n = document.querySelector('[data-testid=\"token-save-note\"]');"
        "return n && n.innerText.indexOf('accepted') >= 0; }",
        timeout=15000,
    )
    note = anon_drawer.locator('[data-testid="token-save-note"]')
    assert "ad-resultbox" in (note.get_attribute("class") or "")
    assert anon_drawer.locator('[data-testid="auth-required"]').count() == 0


def test_the_admin_token_is_never_written_outside_its_own_field(anon_drawer, admin_headers):
    """The value belongs in the input the operator controls, and nowhere else."""
    token = admin_headers["X-Admin-Token"]
    anon_drawer.fill("#adToken", token)
    anon_drawer.click("#adSaveToken")
    anon_drawer.wait_for_function(
        "() => { var n = document.querySelector('[data-testid=\"token-save-note\"]');"
        "return n && n.innerText.indexOf('accepted') >= 0; }",
        timeout=15000,
    )
    assert token not in anon_drawer.inner_text("body")
    assert anon_drawer.evaluate("document.getElementById('adToken').value") == token


# =============================================== regenerating while locked out
def test_regenerate_while_locked_out_explains_the_chicken_and_egg(anon_drawer):
    """Regenerating is itself an admin write, so a 401 here is permanent, not a glitch.

    Only the failing path is exercised. A successful regenerate would rotate the
    token out from under every other test in the session.
    """
    anon_drawer.fill("#adToken", "not-the-admin-token")
    anon_drawer.click("#adSaveToken")
    anon_drawer.click("#adRegen")          # arms the confirm
    anon_drawer.click("#adRegen")          # fires it
    anon_drawer.wait_for_selector('[data-testid="regen-locked-out"]', timeout=15000)
    text = anon_drawer.locator('[data-testid="regen-locked-out"]').inner_text()
    assert "currently valid admin token" in text
    assert "401" in text
    assert "cannot get you back in" in text
    assert "argybargy token" in text or "admin.token" in text
    assert text.strip() != "Regenerate failed."


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


# ================================================= durable roster (bug: empty AGENTS)
@pytest.fixture
def drop_presence():
    """Forget one room's in-memory presence, the way restarting the relay does.

    Scoped to a single room and put back afterwards, so the rest of the session
    keeps whatever it had seen.
    """
    from argybargy import app as appmod
    dropped = {}

    def _drop(room):
        dropped[room] = appmod.hub._last_seen.pop(room, {})

    yield _drop
    for room, seen in dropped.items():
        appmod.hub._last_seen[room] = seen


@pytest.fixture
def roster_room(client, admin_headers, drop_presence):
    """A room whose agents have all finished, plus one that was never heard from."""
    room = "rosterroom"
    for name in ("roster-worker", "roster-invitee"):
        client.post("/admin/invite", headers=admin_headers, json={"name": name, "room": room})
    r = client.post("/admin/invite", headers=admin_headers, json={"name": "roster-worker-2", "room": room})
    auth = {"Authorization": f"Bearer {r.json()['code']}"}
    client.post("/messages", headers=auth, json={"to": "all", "text": "finished my part"})
    drop_presence(room)
    return room


@pytest.fixture
def roster_page(page, live_server, admin_headers, roster_room):
    token = admin_headers["X-Admin-Token"]
    page.add_init_script(f"localStorage.setItem('cc_admin', {token!r});")
    page.goto(f"{live_server}/dashboard?room={roster_room}")
    page.wait_for_selector('[data-testid="agent-list"] [data-agent]', timeout=15000)
    return page


def test_agents_list_is_not_empty_after_presence_is_lost(roster_page):
    """The reported bug: relay restarted, every agent had finished, the list went blank."""
    row = roster_page.locator('[data-testid="agent-list"] [data-agent="roster-worker-2"]')
    assert row.count() == 1, "an agent that posted must stay in the room's agent list"
    assert row.locator('[data-testid="last-seen"]').inner_text().strip() != "online"


def test_agents_list_is_scoped_to_the_room_in_view(roster_page):
    """Other rooms' agents must not be mixed into this room's roster."""
    names = roster_page.locator('[data-testid="agent-list"] [data-agent]').evaluate_all(
        "els => els.map(e => e.getAttribute('data-agent'))")
    assert "roster-worker-2" in names
    assert not [n for n in names if not n.startswith("roster-")], names


def test_agent_count_reads_online_over_total(roster_page):
    assert roster_page.locator('[data-testid="agent-count"]').inner_text().strip() == "· 0/3"


def test_a_code_holder_that_never_spoke_folds_under_invited(roster_page):
    toggle = roster_page.locator("#invitedToggle")
    assert "Invited · 2" in toggle.inner_text()
    assert roster_page.locator('[data-testid="invited-list"]').count() == 0
    toggle.click()
    row = roster_page.locator('[data-testid="invited-list"] [data-agent="roster-invitee"]')
    assert row.count() == 1
    assert row.locator('[data-testid="last-seen"]').inner_text().strip() == "invited"


def test_online_still_means_connected_right_now(roster_page, client, roster_room, admin_headers):
    """The roster widened who is listed. It must not have widened what online means."""
    r = client.post("/admin/invite", headers=admin_headers,
                    json={"name": "roster-live", "room": roster_room})
    client.get("/whoami", headers={"Authorization": f"Bearer {r.json()['code']}"})
    roster_page.wait_for_selector('[data-agent="roster-live"] [data-testid="last-seen"]', timeout=15000)
    roster_page.wait_for_function(
        "() => document.querySelector('[data-agent=\"roster-live\"] [data-testid=\"last-seen\"]')"
        ".innerText.trim() === 'online'", timeout=15000)
    stamps = roster_page.locator('[data-testid="agent-list"] [data-testid="last-seen"]').evaluate_all(
        "els => els.map(e => e.innerText.trim())")
    assert stamps.count("online") == 1, stamps


# ============================================= persisted unread (bug: reset on refresh)
@pytest.fixture
def unread_rooms(client, admin_headers):
    """Two rooms with traffic: one to stand in, one to leave and come back to."""
    codes = {}
    for room in ("unreadhome", "unreadother"):
        r = client.post("/admin/invite", headers=admin_headers,
                        json={"name": f"agent-{room}", "room": room})
        codes[room] = {"Authorization": f"Bearer {r.json()['code']}"}
        client.post("/messages", headers=codes[room], json={"to": "all", "text": f"first in {room}"})
    return codes


def _open_dashboard(page, live_server, token, room):
    page.add_init_script(f"localStorage.setItem('cc_admin', {token!r});")
    page.goto(f"{live_server}/dashboard?room={room}")
    page.wait_for_selector('[data-room="unreadother"]', timeout=15000)
    return page


def _has_unread(page, room):
    return page.locator(f'[data-room="{room}"] [data-testid="room-unread"]').count() == 1


def test_a_room_you_already_read_stays_read_across_a_refresh(page, live_server, admin_headers, unread_rooms):
    """The reported bug: every refresh marked every room you were not standing in."""
    token = admin_headers["X-Admin-Token"]
    _open_dashboard(page, live_server, token, "unreadhome")
    page.click('[data-room="unreadother"]')          # read it
    page.wait_for_timeout(500)
    page.click('[data-room="unreadhome"]')           # stand somewhere else
    page.wait_for_timeout(500)
    assert not _has_unread(page, "unreadother")

    page.reload()
    page.wait_for_selector('[data-room="unreadother"]', timeout=15000)
    page.wait_for_timeout(500)
    assert not _has_unread(page, "unreadother"), "a room read before the refresh came back unread"


def test_a_message_that_arrived_while_you_were_away_is_still_unread_after_a_refresh(
        page, live_server, admin_headers, unread_rooms):
    """The other half: persisting must not swallow genuinely new traffic."""
    token = admin_headers["X-Admin-Token"]
    _open_dashboard(page, live_server, token, "unreadhome")
    page.click('[data-room="unreadother"]')
    page.wait_for_timeout(500)
    page.click('[data-room="unreadhome"]')
    page.wait_for_timeout(500)

    from argybargy import app as appmod
    appmod.message_store.add("unreadother", "agent-unreadother", "all", "arrived while away")
    page.wait_for_timeout(4000)                      # one poll
    assert _has_unread(page, "unreadother")

    page.reload()
    page.wait_for_selector('[data-room="unreadother"]', timeout=15000)
    page.wait_for_timeout(500)
    assert _has_unread(page, "unreadother"), "unread that survived the poll must survive the reload"


def test_a_mark_left_over_from_an_older_database_does_not_pin_a_room_read(
        page, live_server, admin_headers, unread_rooms):
    """A stored mark above the room's own last_seq is stale, not a claim to have read it."""
    token = admin_headers["X-Admin-Token"]
    page.add_init_script(f"localStorage.setItem('cc_admin', {token!r});")
    page.add_init_script('localStorage.setItem("cc_seen", JSON.stringify({unreadother: 999999}));')
    page.goto(f"{live_server}/dashboard?room=unreadhome")
    page.wait_for_selector('[data-room="unreadother"]', timeout=15000)
    page.wait_for_timeout(500)
    assert _has_unread(page, "unreadother"), "a stale high mark must not read as 'already seen'"
    assert page.evaluate('JSON.parse(localStorage.getItem("cc_seen")).unreadother') == 0


def test_unread_marks_are_written_to_local_storage(page, live_server, admin_headers, unread_rooms):
    token = admin_headers["X-Admin-Token"]
    _open_dashboard(page, live_server, token, "unreadhome")
    page.wait_for_function(
        '() => { var s = localStorage.getItem("cc_seen");'
        ' return s && JSON.parse(s).unreadhome > 0; }', timeout=15000)


def test_unreadable_stored_marks_do_not_break_the_boot(page, live_server, admin_headers, unread_rooms):
    token = admin_headers["X-Admin-Token"]
    page.add_init_script(f"localStorage.setItem('cc_admin', {token!r});")
    page.add_init_script('localStorage.setItem("cc_seen", "{not json");')
    page.goto(f"{live_server}/dashboard?room=unreadhome")
    page.wait_for_selector('[data-testid="room-list"] [data-room]', timeout=15000)
    assert page.locator('[data-testid="channel-title"]').inner_text() == "unreadhome"
