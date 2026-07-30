"""Argybargy CLI.

Two groups of commands. ``up`` / ``serve`` / ``invite`` / ``codes`` / ``revoke`` /
``token`` are the originals and are unchanged. ``room`` / ``post`` / ``close`` /
``reopen`` / ``rooms`` are the operator's day: start a stream, talk to it, end it.

The split that matters is which URL each one uses. ``room`` prints a brief for
somebody else's agent, so the block it prints advertises the *public* URL (the
saved tunnel, or whatever ``--url`` says). The operator's own commands carry the
admin token, so they talk to **localhost** by default: there is no reason to send
an admin token across a tunnel to reach a relay running on this machine. Point
them somewhere else with ``--url`` when the bridge is genuinely remote.

No command ever takes a token as an argument. They read it from the state
directory, which is the whole point: a bearer code pasted into a prompt is a
secret sitting in every transcript that prompt ever touches.
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request

from .auth import CodeStore
from .onboard import brief_block
from .paths import ADMIN_TOKEN_PATH, DB_PATH, URL_PATH
from .settings import settings
from .store import MessageStore
from .util import parse_expires


def _base_url(arg_url):
    if arg_url:
        return arg_url.rstrip("/")
    if URL_PATH.exists():
        saved = URL_PATH.read_text().strip()
        if saved:
            return saved.rstrip("/")
    return f"http://localhost:{settings.port}"


def _control_url(arg_url):
    """Where the operator's own commands talk to. Localhost unless told otherwise."""
    return arg_url.rstrip("/") if arg_url else f"http://127.0.0.1:{settings.port}"


def _admin_token():
    """Read the admin token off disk. Never an argument, never in a prompt."""
    if not ADMIN_TOKEN_PATH.exists():
        raise SystemExit(f"No admin token yet ({ADMIN_TOKEN_PATH}). Start the bridge once "
                         f"with 'argybargy serve' or 'argybargy up', then try again.")
    token = ADMIN_TOKEN_PATH.read_text().strip()
    if not token:
        raise SystemExit(f"The admin token file is empty ({ADMIN_TOKEN_PATH}). "
                         f"Restart the bridge to have it written again.")
    return token


def _call(method, url, body=None, timeout=20):
    """One small JSON request against the bridge, authenticated as the operator.

    stdlib only: the CLI is installed wherever the relay is, and a control command
    should not drag an HTTP client in with it. Every failure is turned into a line
    a human can act on, because "urllib.error.URLError" is not one.
    """
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/json", "X-Admin-Token": _admin_token()})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed scheme, operator's own URL)
            raw = resp.read().decode() or "{}"
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode() or "{}").get("detail", "")
        except Exception:
            pass
        if e.code in (401, 403):
            raise SystemExit(f"The bridge rejected the admin token ({e.code}). It may have been "
                             f"regenerated since; read the current one with 'argybargy token'.") from e
        raise SystemExit(f"{method} {url} failed: {e.code} {detail or e.reason}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"Could not reach the bridge at {url} ({e.reason}). Is it running? "
                         f"Start it with 'argybargy up', or pass --url for a remote one.") from e


def _panel(host, port, url, admin):
    local = f"http://{host}:{port}"
    print(f"""
==================================================================
  Argybargy is LIVE
------------------------------------------------------------------
  Public URL      : {url or '<local only — no tunnel running>'}
  Dashboard       : {(url or local)}/dashboard
  Local dashboard : {local}/dashboard
  Admin token     : {admin}
------------------------------------------------------------------
  Mint a key for an agent:
    argybargy invite --name <peer>{(' --url ' + url) if url else ''}
  …or open the dashboard and paste the admin token above.

  Ctrl+C to stop.
==================================================================
""")


def cmd_up(args):
    """Start the bridge AND a Cloudflare tunnel (if cloudflared is installed). Cross-platform."""
    import re
    import shutil
    import subprocess
    import threading

    import uvicorn

    from . import app as appmod

    host, port = args.host, args.port
    tunnel = None
    if not args.no_tunnel and shutil.which("cloudflared"):
        URL_PATH.parent.mkdir(parents=True, exist_ok=True)
        tunnel = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )

        def _watch():
            found = False
            try:
                for line in tunnel.stdout or []:
                    m = re.search(r"https://[A-Za-z0-9.-]+\.trycloudflare\.com", line)
                    if m and not found:
                        found = True
                        URL_PATH.write_text(m.group(0) + "\n")
                        _panel(host, port, m.group(0), appmod.ADMIN_TOKEN)
            except Exception:
                pass
            if not found:
                print(f"Tunnel did not report a URL (cloudflared may have failed). "
                      f"Running locally — dashboard at http://{host}:{port}/dashboard")

        threading.Thread(target=_watch, daemon=True).start()
        print("Starting bridge + Cloudflare tunnel… (public URL appears in a few seconds)")
    else:
        if not args.no_tunnel:
            print("cloudflared not found — running locally only. Install it for an internet URL.")
        _panel(host, port, None, appmod.ADMIN_TOKEN)

    try:
        uvicorn.run(appmod.app, host=host, port=port, log_level=settings.log_level)
    finally:
        if tunnel and tunnel.poll() is None:
            tunnel.terminate()
            try:
                tunnel.wait(timeout=5)
            except Exception:
                tunnel.kill()


def cmd_serve(args):
    import uvicorn

    from . import app as appmod

    base = f"http://{args.host}:{args.port}"
    print(f"Argybargy {appmod.VERSION} → {base}")
    print(f"Dashboard:    {base}/dashboard")
    print(f"Admin token:  {appmod.ADMIN_TOKEN}")
    print(f"State dir:    {DB_PATH.parent}")
    print("Run a single worker only (in-memory presence/long-poll). Use 'argybargy up' for a tunnel too.")
    uvicorn.run(appmod.app, host=args.host, port=args.port, log_level=settings.log_level)


def cmd_invite(args):
    store = CodeStore(DB_PATH)
    try:
        expires_at = parse_expires(args.expires)
    except ValueError as e:
        raise SystemExit(str(e)) from e
    code = store.issue(name=args.name, room=args.room, expires_at=expires_at, capabilities=args.capabilities or "")
    base = _base_url(args.url)

    print("Access code issued.\n")
    print(f"  name : {args.name}")
    print(f"  room : {args.room}")
    if args.capabilities:
        print(f"  can  : {args.capabilities}")
    print(f"  url  : {base}")
    print(f"  code : {code}")
    if expires_at:
        print(f"  expires: {expires_at.isoformat(timespec='seconds')}")
    if settings.hash_codes:
        print("  (codes are hashed at rest — copy this code now; it won't be shown again)")
    print("\nHand the agent its URL + code, plus this instruction:\n")
    print(f"  You can talk to other AI agents through a bridge at {base}")
    print(f"  GET {base}/ for full instructions. Authenticate EVERY request with the header:")
    print(f"      Authorization: Bearer {code}")
    print("  Introduce yourself with POST /messages, then poll GET /messages?wait=25&since=<cursor>")
    print("  and reply with POST /messages. Keep taking turns.\n")
    print("Quick test:")
    print(f"  curl -s {base}/whoami -H 'Authorization: Bearer {code}'")


def cmd_codes(args):
    rows = CodeStore(DB_PATH).list()
    if not rows:
        print("No codes issued yet. Use:  argybargy invite --name <peer>")
        return
    if settings.hash_codes:
        print("(hashed at rest — showing masked prefixes; full code is shown only at creation)\n")
    for r in rows:
        exp = r.get("expires") or "never"
        cap = f"  ({r['capabilities']})" if r.get("capabilities") else ""
        print(f"{r['name']:<16} room={r.get('room', 'default'):<12} expires={exp:<22} {r['code']}{cap}")


def cmd_revoke(args):
    n = CodeStore(DB_PATH).revoke(args.target)
    print(f"Revoked {n} code(s) matching '{args.target}'." if n else f"No codes matched '{args.target}'.")


def cmd_room(args):
    """Create a room, issue its two codes, and print a brief that works verbatim.

    One command instead of three, and the brief it prints is the real deliverable:
    a joining agent should not need anyone to explain the poll loop or, worse,
    guess at when it is allowed to stop.

    The room row is written directly, the same way ``invite`` writes codes, so this
    works whether or not the bridge is currently running. A room with a row shows in
    the dashboard sidebar straight away rather than only once somebody has spoken.
    """
    room = args.name
    store = MessageStore(DB_PATH)
    status = store.room_status(room)
    if status["status"] == "closed":
        raise SystemExit(f"Room '{room}' is closed (by {status['closed_by'] or 'operator'} at "
                         f"{status['closed_at']}). Reopen it first:  argybargy reopen {room}")
    store.set_room_status(room, "open", "cli")

    try:
        expires_at = parse_expires(args.expires)
    except ValueError as e:
        raise SystemExit(str(e)) from e
    codes = CodeStore(DB_PATH)
    worker_name = args.worker or f"{room}-worker"
    operator_name = args.operator or f"{room}-operator"
    worker_code = codes.issue(name=worker_name, room=room, expires_at=expires_at,
                              capabilities=args.capabilities or "")
    operator_code = codes.issue(name=operator_name, room=room, expires_at=expires_at,
                                capabilities="operator for this room")
    base = _base_url(args.url)

    print(f"Room '{room}' is open.\n")
    print(f"  worker   : {worker_name}")
    print(f"  operator : {operator_name}   code: {operator_code}")
    print(f"  url      : {base}")
    if expires_at:
        print(f"  expires  : {expires_at.isoformat(timespec='seconds')}")
    if settings.hash_codes:
        print("  (codes are hashed at rest, so copy them now; they will not be shown again)")
    print("\nGive the operator code to whoever is running the room on your behalf. You do not")
    print("need it yourself: 'argybargy post', 'close' and 'reopen' read the admin token from")
    print("the state directory, so no code has to go anywhere near a prompt.\n")
    print(f"Paste everything between the lines into the agent's brief:\n{'-' * 70}")
    print(brief_block(base, room, worker_name, worker_code, settings.max_idle_seconds))
    print("-" * 70)
    print(f"\nThen: argybargy post {room} \"...\" | argybargy rooms | argybargy close {room}")


def cmd_post(args):
    """Say something into a room as the operator, with no token on the command line."""
    url = _control_url(args.url) + "/admin/say"
    body = {"room": args.room, "text": args.text, "to": args.to, "sender": args.sender}
    if args.expects:
        body["expects_reply"] = args.expects
    msg = _call("POST", url, body).get("message", {})
    print(f"#{args.room} seq {msg.get('seq', '?')} sent as {args.sender} -> {args.to}")


def cmd_close(args):
    """Dismiss everyone in a room. Every long-poll parked on it wakes immediately."""
    url = _control_url(args.url) + f"/admin/rooms/{args.room}/close"
    room = _call("POST", url, {"by": args.by}).get("room", {})
    print(f"#{args.room} closed by {room.get('closed_by', args.by)} at {room.get('closed_at', '')}. "
          f"Everyone polling it has been told to leave.")


def cmd_reopen(args):
    """Let agents back into a room. Anyone already dismissed is gone for good."""
    url = _control_url(args.url) + f"/admin/rooms/{args.room}/reopen"
    _call("POST", url, {"by": args.by})
    print(f"#{args.room} is open again. Agents already dismissed will not come back; "
          f"invite new ones with 'argybargy room' or 'argybargy invite'.")


def cmd_rooms(args):
    """Every room, what state it is in, and who is waiting on you in it."""
    state = _call("GET", _control_url(args.url) + "/admin/state")
    summaries = state.get("rooms") or []
    statuses = state.get("room_status") or {}
    waiting = {}
    for w in state.get("waiting") or []:
        waiting[w["room"]] = waiting.get(w["room"], 0) + 1
    names = sorted({s["room"] for s in summaries} | set(statuses))
    if not names:
        print("No rooms yet. Start one with:  argybargy room <name>")
        return
    by_name = {s["room"]: s for s in summaries}
    print(f"{'ROOM':<24} {'STATUS':<8} {'MSGS':>6}  {'LAST':>8}  WAITING")
    for name in names:
        s = by_name.get(name)
        state_word = (statuses.get(name) or {}).get("status", "open")
        last = _age(s["seconds_since_last"]) if s else "never"
        n = waiting.get(name, 0)
        print(f"{name:<24} {state_word:<8} {(s['messages'] if s else 0):>6}  {last:>8}  "
              f"{n if n else '-'}")


def _age(seconds):
    """Short human age, same shape the dashboard uses."""
    seconds = max(0, int(seconds or 0))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def cmd_token(args):
    from . import app as appmod

    print(appmod.ADMIN_TOKEN)


def main(argv=None):
    p = argparse.ArgumentParser(prog="argybargy", description="Peer-to-peer bridge for AI agents.")
    sub = p.add_subparsers(dest="cmd", required=True)

    u = sub.add_parser("up", help="Start the bridge + a Cloudflare tunnel (recommended).")
    u.add_argument("--host", default=settings.host)
    u.add_argument("--port", type=int, default=settings.port)
    u.add_argument("--no-tunnel", action="store_true", help="Run locally only; do not start cloudflared.")
    u.set_defaults(func=cmd_up)

    s = sub.add_parser("serve", help="Run just the bridge server (no tunnel).")
    s.add_argument("--host", default=settings.host)
    s.add_argument("--port", type=int, default=settings.port)
    s.set_defaults(func=cmd_serve)

    i = sub.add_parser("invite", help="Issue an access code for an agent.")
    i.add_argument("--name", required=True, help="Peer name (e.g. alice).")
    i.add_argument("--room", default="default", help="Room to join (default: default).")
    i.add_argument("--url", default=None, help="Public tunnel URL (else uses saved url.txt or localhost).")
    i.add_argument("--expires", default=None, help="Lifetime: 10m, 30m, 60m, 1d, 1w, 1mo, or never (default).")
    i.add_argument("--capabilities", default=None, help="Short description of what this agent can do/offer.")
    i.set_defaults(func=cmd_invite)

    c = sub.add_parser("codes", help="List issued codes.")
    c.set_defaults(func=cmd_codes)

    r = sub.add_parser("revoke", help="Revoke a code by peer name or code value.")
    r.add_argument("target", help="Peer name or full code to revoke.")
    r.set_defaults(func=cmd_revoke)

    t = sub.add_parser("token", help="Print the admin token (for the dashboard).")
    t.set_defaults(func=cmd_token)

    # ----- the operator's day: start a stream, talk to it, end it -----
    rm = sub.add_parser("room", help="Create a room, issue its codes, print a ready-to-paste agent brief.")
    rm.add_argument("name", help="Room name (e.g. migration-review).")
    rm.add_argument("--worker", default=None, help="Worker agent name (default: <room>-worker).")
    rm.add_argument("--operator", default=None, help="Operator agent name (default: <room>-operator).")
    rm.add_argument("--url", default=None, help="Public URL for the brief (else saved url.txt or localhost).")
    rm.add_argument("--expires", default=None, help="Lifetime for both codes: 10m, 1d, 1w, 1mo, never (default).")
    rm.add_argument("--capabilities", default=None, help="What the worker is (lead with the model).")
    rm.set_defaults(func=cmd_room)

    po = sub.add_parser("post", help="Post into a room as the operator (reads the token from disk).")
    po.add_argument("room")
    po.add_argument("text")
    po.add_argument("--to", default="all", help="A peer name, or 'all' (default).")
    po.add_argument("--sender", default="operator", help="Name to post under (default: operator).")
    po.add_argument("--expects", default=None, help="expects_reply: none, anyone, or a peer name.")
    po.add_argument("--url", default=None, help="Bridge URL (default: this machine).")
    po.set_defaults(func=cmd_post)

    cl = sub.add_parser("close", help="Close a room: every agent polling it is told to leave.")
    cl.add_argument("room")
    cl.add_argument("--by", default="operator", help="Who is closing it, for the audit log.")
    cl.add_argument("--url", default=None, help="Bridge URL (default: this machine).")
    cl.set_defaults(func=cmd_close)

    ro = sub.add_parser("reopen", help="Reopen a closed room so new agents can join.")
    ro.add_argument("room")
    ro.add_argument("--by", default="operator", help="Who is reopening it, for the audit log.")
    ro.add_argument("--url", default=None, help="Bridge URL (default: this machine).")
    ro.set_defaults(func=cmd_reopen)

    ls = sub.add_parser("rooms", help="List rooms with status, volume and who is waiting on you.")
    ls.add_argument("--url", default=None, help="Bridge URL (default: this machine).")
    ls.set_defaults(func=cmd_rooms)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    main()
