"""CLI surface: argument parsing, key management commands, and the launcher wiring.

`up` and `serve` are exercised with the server call stubbed out — we assert the
CLI wires the right host/port/tunnel behaviour rather than actually binding a port.
"""
import time

import pytest

from argybargy import cli


# ------------------------------------------------------------------ base url
def test_base_url_prefers_explicit_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "URL_PATH", tmp_path / "url.txt")
    assert cli._base_url("https://example.test/") == "https://example.test"


def test_base_url_falls_back_to_saved_tunnel_url(monkeypatch, tmp_path):
    saved = tmp_path / "url.txt"
    saved.write_text("https://saved.trycloudflare.com/\n")
    monkeypatch.setattr(cli, "URL_PATH", saved)
    assert cli._base_url(None) == "https://saved.trycloudflare.com"


def test_base_url_falls_back_to_localhost(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "URL_PATH", tmp_path / "missing.txt")
    assert cli._base_url(None) == f"http://localhost:{cli.settings.port}"


def test_base_url_ignores_blank_saved_file(monkeypatch, tmp_path):
    blank = tmp_path / "url.txt"
    blank.write_text("   \n")
    monkeypatch.setattr(cli, "URL_PATH", blank)
    assert cli._base_url(None).startswith("http://localhost")


# --------------------------------------------------------------------- parse
def test_unknown_command_exits(capsys):
    with pytest.raises(SystemExit):
        cli.main(["definitely-not-a-command"])


def test_subcommand_is_required():
    with pytest.raises(SystemExit):
        cli.main([])


def test_invite_requires_name():
    with pytest.raises(SystemExit):
        cli.main(["invite"])


# -------------------------------------------------------------------- invite
def test_invite_issues_a_code_and_prints_instructions(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "cli.db")
    monkeypatch.setattr(cli, "URL_PATH", tmp_path / "url.txt")
    cli.main(["invite", "--name", "alice", "--room", "team", "--capabilities", "writes specs"])
    out = capsys.readouterr().out
    assert "Access code issued." in out
    assert "alice" in out and "team" in out and "writes specs" in out
    assert "Authorization: Bearer" in out

    from argybargy.auth import CodeStore
    rows = CodeStore(tmp_path / "cli.db").list()
    assert [r["name"] for r in rows] == ["alice"]
    assert rows[0]["room"] == "team"


def test_invite_honours_expiry_and_prints_it(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "cli.db")
    monkeypatch.setattr(cli, "URL_PATH", tmp_path / "url.txt")
    cli.main(["invite", "--name", "temp", "--expires", "10m"])
    assert "expires:" in capsys.readouterr().out


def test_invite_rejects_bad_expiry_with_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "cli.db")
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["invite", "--name", "bad", "--expires", "bogus"])
    assert "expires" in str(excinfo.value).lower()


def test_invite_uses_the_supplied_url_in_the_snippet(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "cli.db")
    monkeypatch.setattr(cli, "URL_PATH", tmp_path / "url.txt")
    cli.main(["invite", "--name", "remote", "--url", "https://x.trycloudflare.com"])
    assert "https://x.trycloudflare.com/whoami" in capsys.readouterr().out


# --------------------------------------------------------------------- codes
def test_codes_reports_when_empty(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "empty.db")
    cli.main(["codes"])
    assert "No codes issued yet" in capsys.readouterr().out


def test_codes_lists_name_room_and_capabilities(monkeypatch, tmp_path, capsys):
    db = tmp_path / "cli.db"
    monkeypatch.setattr(cli, "DB_PATH", db)
    monkeypatch.setattr(cli, "URL_PATH", tmp_path / "url.txt")
    cli.main(["invite", "--name", "dba", "--room", "ops", "--capabilities", "runs SQL"])
    capsys.readouterr()
    cli.main(["codes"])
    out = capsys.readouterr().out
    assert "dba" in out and "room=ops" in out and "runs SQL" in out


# -------------------------------------------------------------------- revoke
def test_revoke_reports_a_hit(monkeypatch, tmp_path, capsys):
    db = tmp_path / "cli.db"
    monkeypatch.setattr(cli, "DB_PATH", db)
    monkeypatch.setattr(cli, "URL_PATH", tmp_path / "url.txt")
    cli.main(["invite", "--name", "goner"])
    capsys.readouterr()
    cli.main(["revoke", "goner"])
    assert "Revoked 1 code(s)" in capsys.readouterr().out

    from argybargy.auth import CodeStore
    assert CodeStore(db).list() == []


def test_revoke_reports_a_miss(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "cli.db")
    cli.main(["revoke", "nobody"])
    assert "No codes matched" in capsys.readouterr().out


# --------------------------------------------------------------------- token
def test_token_prints_the_admin_token(capsys):
    from argybargy import app as appmod
    cli.main(["token"])
    assert capsys.readouterr().out.strip() == appmod.ADMIN_TOKEN


# ------------------------------------------------------------ serve / up
def test_serve_starts_uvicorn_on_the_requested_address(monkeypatch, capsys):
    """cmd_serve imports uvicorn locally, so patch the real module."""
    import uvicorn
    seen = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: seen.update(kw, app=app))
    cli.main(["serve", "--host", "0.0.0.0", "--port", "9123"])
    assert seen["host"] == "0.0.0.0"
    assert seen["port"] == 9123
    assert "/dashboard" in capsys.readouterr().out


def test_up_without_tunnel_never_launches_cloudflared(monkeypatch, tmp_path, capsys):
    import subprocess

    import uvicorn
    monkeypatch.setattr(cli, "URL_PATH", tmp_path / "url.txt")
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("no tunnel expected"))
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: None)
    cli.main(["up", "--no-tunnel", "--port", "9124"])
    assert "Argybargy is LIVE" in capsys.readouterr().out


def test_up_starts_a_tunnel_when_cloudflared_is_present(monkeypatch, tmp_path, capsys):
    import shutil
    import subprocess

    import uvicorn

    class FakeTunnel:
        stdout = iter(["INFO |  https://fake-abc.trycloudflare.com  |\n"])

        def poll(self):
            return 0

    calls = {}

    def fake_popen(cmd, **kw):
        calls["cmd"] = cmd
        return FakeTunnel()

    url_file = tmp_path / "url.txt"
    monkeypatch.setattr(cli, "URL_PATH", url_file)
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/cloudflared" if name == "cloudflared" else None)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: None)

    cli.main(["up", "--port", "9125"])
    assert calls["cmd"][:3] == ["cloudflared", "tunnel", "--url"]
    assert "9125" in calls["cmd"][3]

    # the watcher thread scrapes the URL out of cloudflared's output and saves it
    for _ in range(50):
        if url_file.exists() and url_file.read_text().strip():
            break
        time.sleep(0.05)
    assert url_file.read_text().strip() == "https://fake-abc.trycloudflare.com"


def test_panel_renders_public_url_and_token(capsys):
    cli._panel("127.0.0.1", 8765, "https://pub.example", "TOKEN123")
    out = capsys.readouterr().out
    assert "https://pub.example/dashboard" in out
    assert "TOKEN123" in out
    assert "http://127.0.0.1:8765/dashboard" in out


def test_panel_handles_local_only(capsys):
    cli._panel("127.0.0.1", 8765, None, "TOKEN123")
    out = capsys.readouterr().out
    assert "local only" in out
    assert "http://127.0.0.1:8765/dashboard" in out


# ----------------------------------------------------------------------- room
def test_room_creates_the_room_issues_two_codes_and_prints_a_brief(monkeypatch, tmp_path, capsys):
    db = tmp_path / "cli.db"
    monkeypatch.setattr(cli, "DB_PATH", db)
    monkeypatch.setattr(cli, "URL_PATH", tmp_path / "url.txt")
    cli.main(["room", "migration", "--url", "https://bridge.test"])
    out = capsys.readouterr().out

    from argybargy.auth import CodeStore
    from argybargy.store import MessageStore
    rows = {r["name"]: r for r in CodeStore(db).list()}
    assert set(rows) == {"migration-worker", "migration-operator"}
    assert rows["migration-worker"]["room"] == "migration"
    # the room exists before anyone has spoken, so the sidebar lists it straight away
    assert MessageStore(db).room_status("migration")["status"] == "open"

    assert "Room 'migration' is open." in out
    assert "https://bridge.test/messages?wait=25" in out
    assert "should_exit" in out and "idle_timeout" in out
    assert rows["migration-worker"]["code"] in out


def test_room_lets_you_name_the_two_agents(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "cli.db")
    monkeypatch.setattr(cli, "URL_PATH", tmp_path / "url.txt")
    cli.main(["room", "build", "--worker", "codex-1", "--operator", "pm"])
    from argybargy.auth import CodeStore
    assert {r["name"] for r in CodeStore(tmp_path / "cli.db").list()} == {"codex-1", "pm"}


def test_room_refuses_a_closed_room_and_names_the_way_out(monkeypatch, tmp_path):
    db = tmp_path / "cli.db"
    monkeypatch.setattr(cli, "DB_PATH", db)
    monkeypatch.setattr(cli, "URL_PATH", tmp_path / "url.txt")
    from argybargy.store import MessageStore
    MessageStore(db).set_room_status("shut", "closed", "titus")
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["room", "shut"])
    assert "argybargy reopen shut" in str(excinfo.value)


def test_room_rejects_a_bad_expiry(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "DB_PATH", tmp_path / "cli.db")
    monkeypatch.setattr(cli, "URL_PATH", tmp_path / "url.txt")
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["room", "bad", "--expires", "nonsense"])
    assert "expires" in str(excinfo.value).lower()


# ------------------------------------------------------------------ the brief
def test_the_brief_carries_the_url_room_agent_and_code():
    from argybargy.onboard import brief_block
    b = brief_block("https://x.test/", "build", "codex-1", "CODE123", 900)
    assert "https://x.test/messages?wait=25" in b
    assert "https://x.test//" not in b, "the trailing slash must not double up"
    assert "Room    : build" in b
    assert "You are : codex-1" in b
    assert "Authorization: Bearer CODE123" in b
    assert "900 seconds" in b


def test_the_brief_states_all_three_exit_branches_in_plain_language():
    from argybargy.onboard import brief_block
    b = brief_block("http://x.test", "r", "a", "C")
    assert "Finishing your work is not leaving." in b
    assert 'exit_reason "room_closed"' in b
    assert 'exit_reason "idle_timeout"' in b
    assert "not because the work failed" in b
    assert '"expects_reply":"anyone"' in b
    assert "/messages/<seq>/claim" in b


def test_the_brief_is_plain_text_a_non_claude_agent_can_follow():
    """No vendor, no SDK, no unsubstituted placeholder, and no em dashes."""
    from argybargy.onboard import brief_block
    b = brief_block("http://x.test", "r", "a", "C")
    assert "\u2014" not in b, "no em dashes"
    assert "{" not in b.replace('{"to"', "").replace('{"', "")
    for word in ("Claude", "Anthropic", "pip install", "npm"):
        assert word not in b


# ------------------------------------------------------- post / close / reopen
@pytest.fixture
def stub_call(monkeypatch):
    """Capture what the CLI would send, without a bridge."""
    seen = {}

    def fake(method, url, body=None, timeout=20):
        seen.update(method=method, url=url, body=body)
        return {"ok": True, "message": {"seq": 7}, "room": {"closed_by": "titus", "closed_at": "T"}}

    monkeypatch.setattr(cli, "_call", fake)
    return seen


def test_post_sends_admin_say_with_no_token_on_the_command_line(stub_call, capsys):
    cli.main(["post", "build", "ship it", "--to", "codex", "--expects", "codex"])
    assert stub_call["method"] == "POST"
    assert stub_call["url"].endswith("/admin/say")
    assert stub_call["body"] == {"room": "build", "text": "ship it", "to": "codex",
                                "sender": "operator", "expects_reply": "codex"}
    assert "seq 7" in capsys.readouterr().out


def test_post_defaults_to_the_whole_room_and_omits_expects(stub_call):
    cli.main(["post", "build", "morning"])
    assert stub_call["body"] == {"room": "build", "text": "morning", "to": "all", "sender": "operator"}


def test_close_and_reopen_hit_the_room_lifecycle_endpoints(stub_call, capsys):
    cli.main(["close", "build", "--by", "titus"])
    assert stub_call["url"].endswith("/admin/rooms/build/close")
    assert stub_call["body"] == {"by": "titus"}
    assert "told to leave" in capsys.readouterr().out

    cli.main(["reopen", "build"])
    assert stub_call["url"].endswith("/admin/rooms/build/reopen")
    assert stub_call["body"] == {"by": "operator"}
    assert "open again" in capsys.readouterr().out


def test_the_operator_commands_talk_to_this_machine_by_default(stub_call):
    cli.main(["post", "build", "hi"])
    assert stub_call["url"].startswith("http://127.0.0.1:")
    cli.main(["post", "build", "hi", "--url", "https://remote.test/"])
    assert stub_call["url"] == "https://remote.test/admin/say"


# ---------------------------------------------------------------------- rooms
def test_rooms_lists_status_volume_and_who_is_waiting(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_call", lambda *a, **k: {
        "rooms": [{"room": "build", "messages": 12, "seconds_since_last": 90},
                  {"room": "old", "messages": 3, "seconds_since_last": 7200}],
        "room_status": {"old": {"status": "closed"}},
        "waiting": [{"room": "build"}, {"room": "build"}],
    })
    cli.main(["rooms"])
    lines = capsys.readouterr().out.splitlines()
    build = [ln for ln in lines if ln.startswith("build")][0]
    old = [ln for ln in lines if ln.startswith("old")][0]
    assert "open" in build and "12" in build and "1m" in build and build.rstrip().endswith("2")
    assert "closed" in old and "2h" in old and old.rstrip().endswith("-")


def test_rooms_says_so_when_there_are_none(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_call", lambda *a, **k: {"rooms": [], "room_status": {}, "waiting": []})
    cli.main(["rooms"])
    assert "argybargy room <name>" in capsys.readouterr().out


def test_age_reads_in_the_biggest_unit_that_fits():
    assert [cli._age(x) for x in (0, 45, 90, 7200, 200000)] == ["0s", "45s", "1m", "2h", "2d"]


# ------------------------------------------------- reading the token off disk
def test_the_admin_token_is_read_from_the_state_directory(monkeypatch, tmp_path):
    path = tmp_path / "admin.token"
    path.write_text("SECRET\n")
    monkeypatch.setattr(cli, "ADMIN_TOKEN_PATH", path)
    assert cli._admin_token() == "SECRET"


def test_a_missing_token_file_says_how_to_get_one(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "ADMIN_TOKEN_PATH", tmp_path / "nope.token")
    with pytest.raises(SystemExit) as excinfo:
        cli._admin_token()
    assert "argybargy serve" in str(excinfo.value)


def test_an_empty_token_file_is_not_treated_as_a_token(monkeypatch, tmp_path):
    path = tmp_path / "admin.token"
    path.write_text("  \n")
    monkeypatch.setattr(cli, "ADMIN_TOKEN_PATH", path)
    with pytest.raises(SystemExit) as excinfo:
        cli._admin_token()
    assert "empty" in str(excinfo.value)


def test_an_unreachable_bridge_reads_as_an_instruction_not_a_traceback(monkeypatch, tmp_path):
    import urllib.error
    path = tmp_path / "admin.token"
    path.write_text("SECRET")
    monkeypatch.setattr(cli, "ADMIN_TOKEN_PATH", path)

    def boom(*a, **k):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(cli.urllib.request, "urlopen", boom)
    with pytest.raises(SystemExit) as excinfo:
        cli._call("GET", "http://127.0.0.1:9/admin/state")
    assert "Is it running?" in str(excinfo.value)


def test_a_rejected_admin_token_names_the_command_that_prints_the_real_one(monkeypatch, tmp_path):
    import io
    import urllib.error
    path = tmp_path / "admin.token"
    path.write_text("STALE")
    monkeypatch.setattr(cli, "ADMIN_TOKEN_PATH", path)

    def denied(*a, **k):
        raise urllib.error.HTTPError("http://x/admin/state", 401, "Unauthorized", {},
                                     io.BytesIO(b'{"detail":"nope"}'))

    monkeypatch.setattr(cli.urllib.request, "urlopen", denied)
    with pytest.raises(SystemExit) as excinfo:
        cli._call("GET", "http://x/admin/state")
    assert "argybargy token" in str(excinfo.value)
