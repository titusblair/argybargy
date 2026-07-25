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
