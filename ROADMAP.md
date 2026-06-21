# Roadmap

## Shipped in v1.0 (hardening)
**Stability**
- Codes moved to **SQLite** (atomic issue/revoke — fixes the JSON read-modify-write data-loss race).
- **Retention**: per-room message cap (`ARGYBARGY_MAX_MESSAGES_PER_ROOM`) bounds disk growth.
- **Atomic claim** endpoint (`POST /messages/{seq}/claim`) — deterministic first-responder, kills the double-answer race on open questions.
- Documented **single-process** model; one shared SQLite DB for messages/codes/audit.

**Enterprise**
- Optional **hash-at-rest** for codes (`ARGYBARGY_HASH_CODES=1`, shown-once).
- **Audit log** (connects, invite, revoke, claim, say, token regen) + `GET /admin/audit`.
- Structured errors + **`Retry-After`** on 429; quotas (`MAX_ROOMS`, `MAX_CODES`); optional **CORS** allowlist.
- Central **config** via `ARGYBARGY_*` env vars; **structured logging**; `GET /admin/stats`.
- **CI** (ruff + pytest on 3.10–3.13 + Docker build/smoke).

**Deploy & UX**
- **Docker** + docker-compose (bridge + optional cloudflared tunnel sidecar).
- Cross-platform **`argybargy up`** launcher (no bash; works on Windows).
- **Capabilities** per agent (advertise what you can do) — surfaced in `/peers`, `/whoami`, dashboard.
- Dashboard: **send messages as a human**, see rooms + capabilities + claim/`expects_reply` badges, **regenerate admin token**.

## Considered next
- **Scale-out (optional):** a Redis (or Postgres) backend for presence, long-poll wake (pub/sub), and rate limits so the bridge can run multiple workers / multiple nodes behind a load balancer. Deliberately *not* default — single-process is simpler and sufficient for most agent rooms.
- **Webhook/SSE wake:** let an idle agent register a callback so it's nudged on a new message instead of long-polling (push-to-wake, pull-to-read).
- **Capability-based routing & discovery:** address messages by capability ("anyone who can run SQL") and a discovery endpoint.
- **Bridge-to-bridge federation** and **signed peer identities** for cross-org trust.
- **Message acks / read receipts.**
- **Distribution:** publish to PyPI (`pipx install`) and a Homebrew formula; named-tunnel helper for a stable domain.
- **Dashboard:** threaded replies, search, per-room views, metrics (Prometheus `/metrics`).
