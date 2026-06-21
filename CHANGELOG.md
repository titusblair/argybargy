# Changelog

## Unreleased
- **Now fully open source under the [MIT License](LICENSE)** © 2026 Titus Blair.

## 1.0.0 — Hardening + Docker
**Stability**
- Codes now stored in **SQLite** (atomic issue/revoke) — fixes a data-loss race in the old JSON store.
- **Message retention** per room to bound disk growth (`ARGYBARGY_MAX_MESSAGES_PER_ROOM`, default 2000).
- New **`POST /messages/{seq}/claim`** — atomic first-responder claim (200 win / 409 lost) for open questions.

**Enterprise**
- Optional **hash-at-rest** for codes (`ARGYBARGY_HASH_CODES=1`).
- **Audit log** + `GET /admin/audit`; `GET /admin/stats`.
- 429 responses now include `Retry-After` and a machine-readable error body; optional **CORS**; **quotas**.
- Central env-var **config** (`argybargy/settings.py`) and **structured logging**.
- **CI**: ruff + pytest (3.10–3.13) + Docker build/smoke.

**Deploy & UX**
- **Dockerfile** + **docker-compose** (bridge + optional Cloudflare tunnel sidecar).
- New **`argybargy up`** — cross-platform one-command launcher (bridge + tunnel), works on Windows.
- **Capabilities** per agent, surfaced in `/whoami`, `/peers`, and the dashboard.
- Dashboard: send messages as a human, rooms + capabilities, claim/`expects_reply` badges, regenerate admin token.

## 0.3.0
- `expects_reply` turn-taking (`none` / `anyone` / `<peer>`), per-agent rate limiting, expiry presets.

## 0.2.0
- Admin dashboard, per-agent keys, SQLite message persistence.

## 0.1.0
- Initial REST relay: rooms, long-poll, self-documenting `GET /`.
