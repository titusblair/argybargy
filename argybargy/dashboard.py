"""Admin dashboard — a single self-contained HTML page (Preact, built with Vite).

Auto light/dark (follows the OS via prefers-color-scheme) with a manual Auto/Light/Dark
toggle. Asks for the admin token (stored in localStorage), polls /admin/state, and lets
you generate keys, watch peers + the live conversation, send messages, and revoke access.
Served at GET /dashboard.

Source lives in dashboard/ (a Vite + Preact sub-app, see dashboard/src). It's built with
`pnpm --dir dashboard run build`, which emits a single self-contained dist/index.html
(all JS/CSS inlined via vite-plugin-singlefile, zero external references). That build
output is copied here — to dashboard.html, alongside this module — by
`node dashboard/scripts/emit-dashboard.mjs`. The built file is committed so the package
ships pre-built: no Node toolchain required at install or runtime.
"""

from pathlib import Path

DASHBOARD_HTML = (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")
