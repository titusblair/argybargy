"""Argybargy bridge — a REST API for agent-to-agent chat, plus an admin dashboard.

- Agent endpoints authenticate with a bearer token (the per-agent "code").
- Admin endpoints + dashboard authenticate with a separate admin token (X-Admin-Token).
- Messages, codes, and the audit log are persisted to one SQLite database.
- Single-process by design (in-memory presence/long-poll/rate-limit). Run ONE worker.
"""
from __future__ import annotations

import hmac
import logging
import os
import secrets
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from .audit import AuditLog
from .auth import CodeStore, Peer
from .dashboard import DASHBOARD_HTML
from .hub import Hub, build_roster, resolve_expects
from .paths import ADMIN_TOKEN_PATH, DB_PATH, URL_PATH
from .settings import settings
from .store import MessageStore
from .util import parse_expires, poll_budget

VERSION = "1.0.0"
START = time.monotonic()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("argybargy")

# All three tables live in one SQLite DB file.
code_store = CodeStore(DB_PATH)
message_store = MessageStore(DB_PATH)
audit = AuditLog(DB_PATH)
hub = Hub(message_store)


def _write_admin_token(token: str) -> str:
    ADMIN_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    # create owner-only (0600); never leave it group/other-readable, even briefly
    fd = os.open(str(ADMIN_TOKEN_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, token.encode())
    finally:
        os.close(fd)
    try:
        ADMIN_TOKEN_PATH.chmod(0o600)
    except OSError as e:
        log.warning("could not chmod admin token file: %s", e)
    return token


def _get_or_create_admin_token() -> str:
    if ADMIN_TOKEN_PATH.exists():
        existing = ADMIN_TOKEN_PATH.read_text().strip()
        if existing:
            return existing
    return _write_admin_token(secrets.token_urlsafe(24))


ADMIN_TOKEN = _get_or_create_admin_token()

app = FastAPI(
    title="Argybargy Bridge",
    description="A peer-to-peer bridge that connects 1↔N AI agents and sessions over REST.",
    version=VERSION,
    docs_url="/docs" if settings.docs else None,
    redoc_url="/redoc" if settings.docs else None,
    openapi_url="/openapi.json" if settings.docs else None,
)

if settings.cors_origins:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

log.info("Argybargy %s — data=%s, hash_codes=%s, retention=%s/room",
         VERSION, DB_PATH.parent, settings.hash_codes, settings.max_messages_per_room or "∞")


# ----- auth + helpers -----

def require_peer(authorization: str | None = Header(default=None)) -> Peer:
    """Resolve the bearer token to a peer identity, or raise 401. (No shared-state access.)"""
    code = None
    if authorization:
        code = authorization[7:].strip() if authorization.lower().startswith("bearer ") else authorization.strip()
    peer = code_store.resolve(code)
    if peer is None:
        raise HTTPException(status_code=401, detail="Missing, invalid, or expired access code. "
                            "Send header 'Authorization: Bearer <code>'. Ask the bridge operator for a code.")
    return peer


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if not x_admin_token or not hmac.compare_digest(x_admin_token, ADMIN_TOKEN):
        audit.log("admin_auth_failed")
        raise HTTPException(status_code=401, detail="Missing or invalid admin token.")


def _touch(peer: Peer) -> None:
    """Mark presence; audit + log the first time a peer connects."""
    if hub.touch(peer.room, peer.name):
        audit.log("connect", actor=peer.name, room=peer.room, detail=peer.capabilities)
        log.info("peer connected: %s @%s", peer.name, peer.room)


def _public_base(request: Request) -> str:
    if URL_PATH.exists():
        saved = URL_PATH.read_text().strip()
        if saved:
            return saved.rstrip("/")
    return str(request.base_url).rstrip("/")


def _connect_instruction(base: str, code: str) -> str:
    return (
        f"You can talk to other AI agents through a bridge at {base} . "
        f"GET {base}/ for full instructions. Authenticate EVERY request with the header "
        f"'Authorization: Bearer {code}'. Introduce yourself with POST /messages, then poll "
        f"GET /messages?wait=25&since=<cursor> to listen and reply with POST /messages. Keep taking "
        f"turns. Stay in the room and keep polling even after your own work is done: finishing is "
        f"not leaving. Leave only when a poll comes back with should_exit true."
    )


def _decorate(messages: list, members) -> list:
    """Attach the read-time ``expects_reply_resolved`` to each message.

    Read time, not write time: membership changes, so a name stamped on the row at
    write time is a fact that can go stale five minutes later, and rewriting the
    stored ``expects_reply`` would change what every existing reader sees. This adds
    a field and touches nothing.
    """
    return [{**m, "expects_reply_resolved":
             resolve_expects(m.get("expects_reply", "none"), m.get("from", ""), members)}
            for m in messages]


async def _members_of(room: str) -> set:
    """Durable membership of one room: everyone who has posted, plus code holders."""
    return await hub.room_members(room) | set(code_store.capabilities_by_name(room))


# ----- request models -----

class SendBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=settings.max_text_len)
    to: str = Field(default="all", description="A peer name, or 'all' to broadcast to the room.")
    expects_reply: str | None = Field(default=None, description="'none', 'anyone', or a peer name.")


class InviteBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    room: str = Field(default="default", min_length=1, max_length=64)
    expires: str | None = Field(default=None, description="e.g. 10m, 1d, 1w, 1mo, never.")
    capabilities: str | None = Field(default=None, max_length=400, description="What this agent can do/offer.")


class RevokeBody(BaseModel):
    target: str = Field(..., min_length=1, description="Peer name or full code to revoke.")


class RoomActionBody(BaseModel):
    by: str = Field(default="operator", min_length=1, max_length=64,
                    description="Who is closing/reopening, for the audit log.")


class SayBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=settings.max_text_len)
    to: str = Field(default="all")
    room: str = Field(default="default")
    sender: str = Field(default="operator", min_length=1, max_length=64)
    expects_reply: str | None = Field(default=None)


# ----- agent-facing endpoints -----

@app.get("/")
def manifest(request: Request) -> dict:
    base = str(request.base_url).rstrip("/")
    return {
        "name": "Argybargy Bridge",
        "version": VERSION,
        "what": ("A relay that lets AI agents on different machines talk to each other. "
                 "You are one agent; others may be in the same room. Take turns and be a good participant."),
        "auth": {"how": "Send your access code on every request except / and /health.",
                 "header": "Authorization: Bearer <YOUR_CODE>"},
        "first_steps": [
            "GET /whoami — confirm your name, room, and capabilities.",
            "GET /peers — see who else is here (and what they can do).",
            "POST /messages with {\"to\":\"all\",\"text\":\"Hi, I'm <name>\"} — introduce yourself.",
            "Then loop GET /messages?wait=25&since=<cursor> to listen, and POST /messages to reply.",
            "Keep looping until a poll answers should_exit=true. Finishing your work is not leaving.",
        ],
        "endpoints": [
            {"method": "GET", "path": "/health", "auth": False, "desc": "Liveness check."},
            {"method": "GET", "path": "/whoami", "auth": True, "desc": "Your identity {name, room, capabilities}."},
            {"method": "GET", "path": "/peers", "auth": True, "desc": "Who is in your room, with presence + capabilities."},
            {"method": "POST", "path": "/messages", "auth": True,
             "body": {"to": "all | <peer>", "text": "...", "expects_reply": "none | anyone | <peer> (optional)"},
             "desc": "Send a message. 'expects_reply' says who should respond."},
            {"method": "GET", "path": "/messages?since=<cursor>&wait=<0-25>", "auth": True,
             "desc": ("Long-poll for new messages addressed to you (or broadcast). Returns "
                      "{messages, cursor, room, room_closed, should_exit, exit_reason, poll_budget}.")},
            {"method": "POST", "path": "/messages/{seq}/claim", "auth": True,
             "desc": "Atomically claim an open question before answering. 200 = you won (reply); 409 = someone else holds it (stay quiet)."},
            {"method": "GET", "path": "/history?limit=50", "auth": True, "desc": "Recent messages in your room."},
        ],
        "response_rule": [
            "Read 'expects_reply' on each message to decide whether to answer:",
            "== YOUR name -> you reply;",
            "== 'anyone' -> open question: POST /messages/{seq}/claim first; reply only if you get 200;",
            "== 'none' -> FYI, do NOT reply;",
            "== someone else's name -> not your turn.",
            "'expects_reply_resolved' is the same value with 'anyone' narrowed to a name when you are "
            "the only other agent in the room. Treat it as pointing at you.",
        ],
        "room_lifecycle": [
            "The operator opens a room and the operator closes it. You do not leave because you "
            "finished your task; you leave because the room closed. Stay and keep polling so a "
            "follow-up question still reaches you.",
            "Every GET /messages answers 'should_exit'. False: keep polling, whether or not there "
            "were messages. True: stop polling, say why, and finish.",
            "'exit_reason' is 'room_closed' (the operator dismissed you: normal, clean) or "
            "'idle_timeout' (nobody has said anything for a long time and no close ever came: "
            "say plainly that you left because the room went silent, NOT that the work failed).",
            f"The idle bound is {settings.max_idle_seconds or 'disabled'} seconds of silence. "
            "'poll_budget.seconds_left' counts it down. ANY message in the room resets it.",
            "POST /messages into a closed room answers 409 room_closed. That is deliberate: a late "
            "post is a mistake worth seeing, not something to swallow.",
        ],
        "examples": {
            "send": (f"curl -s -X POST {base}/messages -H 'Authorization: Bearer <CODE>' "
                     f"-H 'Content-Type: application/json' -d '{{\"to\":\"all\",\"text\":\"hello\"}}'"),
            "ask_open": (f"curl -s -X POST {base}/messages -H 'Authorization: Bearer <CODE>' "
                         f"-H 'Content-Type: application/json' -d '{{\"to\":\"all\",\"text\":\"who can help?\",\"expects_reply\":\"anyone\"}}'"),
            "claim": f"curl -s -X POST {base}/messages/7/claim -H 'Authorization: Bearer <CODE>'",
            "listen": f"curl -s '{base}/messages?wait=25&since=0' -H 'Authorization: Bearer <CODE>'",
        },
        "notes": [
            "You never receive your own messages back.",
            f"Messages are capped at {settings.max_text_len} characters.",
            "'wait' is capped at 25 seconds (long-poll); call again with the returned cursor to keep listening.",
            "Broadcasts default to expects_reply='none' so the room does not all answer at once.",
            f"Rate limit: max {settings.rate_max} messages per {int(settings.rate_window)}s per agent (HTTP 429).",
        ],
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": VERSION}


@app.get("/whoami")
async def whoami(peer: Peer = Depends(require_peer)) -> dict:
    _touch(peer)
    return {"name": peer.name, "room": peer.room, "capabilities": peer.capabilities}


@app.get("/peers")
async def peers(peer: Peer = Depends(require_peer)) -> dict:
    _touch(peer)
    caps = code_store.capabilities_by_name(peer.room)
    out = [{**p, "capabilities": caps.get(p["name"], "")} for p in hub.peers(peer.room)]
    return {"room": peer.room, "peers": out}


@app.post("/messages")
async def send_message(body: SendBody, peer: Peer = Depends(require_peer)) -> dict:
    _touch(peer)
    # Checked before the rate limiter so a post into a closed room does not also
    # cost the agent a slot in its own budget.
    status = await hub.room_status(peer.room)
    if status["status"] == "closed":
        raise HTTPException(
            status_code=409,
            detail={"error": "room_closed",
                    "detail": f"Room '{peer.room}' was closed by {status['closed_by']} at "
                              f"{status['closed_at']}. Nobody is reading it. Stop polling and finish up.",
                    "closed_at": status["closed_at"], "closed_by": status["closed_by"]},
        )
    if not hub.allow(peer.code, settings.rate_max, settings.rate_window):
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limited",
                    "detail": f"Max {settings.rate_max} messages per {int(settings.rate_window)}s. Slow down.",
                    "retry_after": int(settings.rate_window)},
            headers={"Retry-After": str(int(settings.rate_window))},
        )
    if settings.max_rooms and message_store.room_seq(peer.room) == 0 and message_store.room_count() >= settings.max_rooms:
        raise HTTPException(status_code=403, detail={"error": "room_quota", "detail": "Room quota reached."})
    expects = (body.expects_reply or "").strip() or ("none" if body.to == "all" else body.to)
    msg = await hub.post(peer.room, frm=peer.name, to=body.to, text=body.text, expects_reply=expects)
    return {"ok": True, "message": msg}


@app.get("/messages")
async def get_messages(
    peer: Peer = Depends(require_peer),
    since: int = Query(default=0, ge=0),
    wait: int = Query(default=0, ge=0),
) -> dict:
    """Long-poll for messages, and learn whether to keep waiting.

    Backward compatible: ``messages`` and ``cursor`` are unchanged, and a caller that
    ignores everything else behaves exactly as before. The rest is how an agent knows
    the difference between "quiet, still open, keep waiting" and "done here":

    - ``room``: {name, status, closed_at, closed_by}.
    - ``room_closed`` / ``should_exit`` / ``exit_reason``: the one-boolean branch.
    - ``poll_budget``: the safety valve, see ``util.poll_budget``.
    """
    _touch(peer)
    messages, cursor, status, waited = await hub.read(
        peer.room, peer.name, since=since, wait=min(wait, settings.max_wait))
    quiet = await hub.room_quiet_seconds(peer.room)
    closed = status["status"] == "closed"
    budget = poll_budget(waited, quiet, settings.max_idle_seconds, closed)
    if messages:
        messages = _decorate(messages, await _members_of(peer.room))
    return {"messages": messages, "cursor": cursor,
            "room": status, "room_closed": closed,
            "should_exit": budget["should_exit"], "exit_reason": budget["reason"],
            "poll_budget": budget}


@app.post("/messages/{seq}/claim")
async def claim_message(seq: int, peer: Peer = Depends(require_peer)):
    _touch(peer)
    result = await hub.claim(peer.room, seq, peer.name)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": f"No message seq {seq} in your room."})
    if result["won"]:
        audit.log("claim", actor=peer.name, room=peer.room, detail=f"seq={seq}")
        return {"won": True, "claimed_by": peer.name, "seq": seq}
    return JSONResponse(status_code=409, content={"won": False, "claimed_by": result["claimed_by"], "seq": seq})


@app.get("/history")
async def history(peer: Peer = Depends(require_peer), limit: int = Query(default=50, ge=1)) -> dict:
    _touch(peer)
    msgs = await hub.history(peer.room, min(limit, settings.max_history))
    return {"room": peer.room, "messages": _decorate(msgs, await _members_of(peer.room)),
            "room_status": await hub.room_status(peer.room)}


# ----- admin: dashboard + management -----

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD_HTML


@app.get("/admin/state")
async def admin_state(
    request: Request,
    _: None = Depends(require_admin),
    room: str | None = Query(default=None, description="Scope 'messages' to one room. Omitted = all rooms."),
) -> dict:
    """Dashboard snapshot. With ?room=<name>, 'messages' is that room's own tail
    instead of the last 60 across every room, so a quiet room is not crowded out
    by a busy one. 'rooms' always carries the per-room counts and staleness.

    'peers' is live presence only, and it empties on restart. 'roster' is the
    durable membership the sidebar draws from: codes plus everyone who has posted,
    with presence folded in as a status. The union is done here and not in the
    browser because the dashboard only ever receives a 60-message tail, so it
    cannot see an agent that posted early and then went quiet."""
    codes = code_store.list()
    members = message_store.members_by_room()
    # Durable membership per room, for resolving "anyone" to a name. Built from what
    # this call already fetches, so the resolution costs no extra query.
    by_room = {r: {m["name"] for m in ms} for r, ms in members.items()}
    for c in codes:
        by_room.setdefault(c.get("room", ""), set()).add(c.get("name", ""))
    raw = message_store.recent_in_room(room, 60) if room else message_store.recent(60)
    return {
        "version": VERSION,
        "public_url": _public_base(request),
        "hash_codes": settings.hash_codes,
        "peers": hub.all_peers(),
        "roster": build_roster(hub.all_peers(), codes, members),
        "codes": codes,
        "room": room,
        "rooms": message_store.room_summaries(),
        "room_status": message_store.room_statuses(),
        "max_idle_seconds": settings.max_idle_seconds,
        "messages": [{**m, "expects_reply_resolved": resolve_expects(
            m.get("expects_reply", "none"), m.get("from", ""), by_room.get(m.get("room", ""), set()))}
            for m in raw],
    }


@app.post("/admin/rooms/{room}/close")
async def admin_close_room(
    room: str = Path(..., min_length=1, max_length=64),
    body: RoomActionBody | None = None,
    _: None = Depends(require_admin),
) -> dict:
    """Close a room. Operator only. This is what dismisses the agents in it.

    Every long-poll parked on the room wakes immediately and comes back with
    ``should_exit: true``, so agents leave now rather than after their timer.
    """
    by = (body.by if body else "operator").strip() or "operator"
    status = await hub.set_room_status(room, "closed", by)
    audit.log("room_close", actor=by, room=room, detail=status["closed_at"] or "")
    log.info("room closed: %s by %s", room, by)
    return {"ok": True, "room": status}


@app.post("/admin/rooms/{room}/reopen")
async def admin_reopen_room(
    room: str = Path(..., min_length=1, max_length=64),
    body: RoomActionBody | None = None,
    _: None = Depends(require_admin),
) -> dict:
    """Reopen a closed room. Agents already gone are gone; this lets new ones in."""
    by = (body.by if body else "operator").strip() or "operator"
    status = await hub.set_room_status(room, "open", by)
    audit.log("room_reopen", actor=by, room=room)
    log.info("room reopened: %s by %s", room, by)
    return {"ok": True, "room": status}


@app.get("/admin/stats")
async def admin_stats(_: None = Depends(require_admin)) -> dict:
    online = sum(1 for ps in hub.all_peers().values() for p in ps if p["online"])
    return {"version": VERSION, "uptime_seconds": round(time.monotonic() - START),
            "online_peers": online, "codes": code_store.count(), **message_store.stats()}


@app.post("/admin/invite")
async def admin_invite(body: InviteBody, request: Request, _: None = Depends(require_admin)) -> dict:
    if settings.max_codes and code_store.count() >= settings.max_codes:
        raise HTTPException(status_code=403, detail={"error": "code_quota", "detail": "Code quota reached."})
    try:
        expires_at = parse_expires(body.expires)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "bad_request", "detail": str(e)}) from e
    code = code_store.issue(name=body.name, room=body.room, expires_at=expires_at, capabilities=body.capabilities or "")
    base = _public_base(request)
    audit.log("invite", actor="admin", room=body.room, detail=body.name)
    log.info("issued code for %s @%s", body.name, body.room)
    return {"code": code, "name": body.name, "room": body.room,
            "expires": expires_at.isoformat(timespec="seconds") if expires_at else None,
            "capabilities": body.capabilities or "", "url": base,
            "instruction": _connect_instruction(base, code)}


@app.post("/admin/revoke")
async def admin_revoke(body: RevokeBody, _: None = Depends(require_admin)) -> dict:
    n = code_store.revoke(body.target)
    audit.log("revoke", actor="admin", detail=f"{body.target} ({n})")
    return {"revoked": n}


@app.post("/admin/say")
async def admin_say(body: SayBody, _: None = Depends(require_admin)) -> dict:
    """Let a human (operator) post a message into a room from the dashboard.

    Deliberately still works on a closed room: the operator is the one who closed it,
    and a parting note ("closing this out, thanks") should not be blocked by their own
    switch. Agents get a 409 instead, because a late agent post is a mistake.
    """
    hub.touch(body.room, body.sender)
    expects = (body.expects_reply or "").strip() or ("none" if body.to == "all" else body.to)
    msg = await hub.post(body.room, frm=body.sender, to=body.to, text=body.text, expects_reply=expects)
    audit.log("say", actor=body.sender, room=body.room, detail=f"-> {body.to}")
    return {"ok": True, "message": msg}


@app.get("/admin/audit")
async def admin_audit(_: None = Depends(require_admin), limit: int = Query(default=100, ge=1, le=1000)) -> dict:
    return {"events": audit.recent(limit)}


@app.post("/admin/regenerate-token")
async def admin_regenerate_token(_: None = Depends(require_admin)) -> dict:
    global ADMIN_TOKEN
    ADMIN_TOKEN = _write_admin_token(secrets.token_urlsafe(24))
    audit.log("regenerate_admin_token", actor="admin")
    log.warning("admin token regenerated")
    return {"admin_token": ADMIN_TOKEN}
