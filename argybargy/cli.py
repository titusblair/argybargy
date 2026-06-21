"""Argybargy CLI: up / serve / invite / codes / revoke / token."""
from __future__ import annotations

import argparse

from .auth import CodeStore
from .paths import DB_PATH, URL_PATH
from .settings import settings
from .util import parse_expires


def _base_url(arg_url):
    if arg_url:
        return arg_url.rstrip("/")
    if URL_PATH.exists():
        saved = URL_PATH.read_text().strip()
        if saved:
            return saved.rstrip("/")
    return f"http://localhost:{settings.port}"


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

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    main()
