"""Admin dashboard — a single self-contained HTML page (vanilla JS, no build step).

Auto light/dark (follows the OS via prefers-color-scheme) with a manual Auto/Light/Dark
toggle. Asks for the admin token (stored in localStorage), polls /admin/state, and lets
you generate keys, watch peers + the live conversation, send messages, and revoke access.
Served at GET /dashboard.
"""

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Argybargy — Admin</title>
<style>
  /* Light is the default; dark applies on OS preference (unless forced light) or when forced dark. */
  :root{
    color-scheme: light dark;
    --bg:#ffffff; --surface:#f6f8fa; --surface2:#ffffff; --border:#d0d7de; --border-soft:#eaeef2;
    --text:#1f2328; --muted:#59636e; --faint:#818b98; --link:#0969da; --who:#8250df;
    --on:#1a7f37; --off:#afb8c1; --accent:#1a7f37;
    --exp-bg:rgba(9,105,218,.10); --exp-bd:rgba(9,105,218,.30);
    --claim-bg:rgba(26,127,55,.12); --claim-bd:rgba(26,127,55,.30);
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      --bg:#0e1116; --surface:#161b22; --surface2:#0d1117; --border:#30363d; --border-soft:#21262d;
      --text:#e6edf3; --muted:#8b949e; --faint:#6e7681; --link:#79c0ff; --who:#d2a8ff;
      --on:#3fb950; --off:#484f58; --accent:#7ee787;
      --exp-bg:rgba(88,166,255,.15); --exp-bd:rgba(88,166,255,.3);
      --claim-bg:rgba(126,231,135,.15); --claim-bd:rgba(126,231,135,.3);
    }
  }
  :root[data-theme="dark"]{
    --bg:#0e1116; --surface:#161b22; --surface2:#0d1117; --border:#30363d; --border-soft:#21262d;
    --text:#e6edf3; --muted:#8b949e; --faint:#6e7681; --link:#79c0ff; --who:#d2a8ff;
    --on:#3fb950; --off:#484f58; --accent:#7ee787;
    --exp-bg:rgba(88,166,255,.15); --exp-bd:rgba(88,166,255,.3);
    --claim-bg:rgba(126,231,135,.15); --claim-bd:rgba(126,231,135,.3);
  }
  * { box-sizing: border-box; }
  body { margin:0; font:14px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif; background:var(--bg); color:var(--text); }
  header { padding:14px 20px; background:var(--surface); border-bottom:1px solid var(--border); display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
  header h1 { font-size:16px; margin:0; margin-right:auto; }
  header h1 span { color:var(--accent); }
  input, button, select, textarea { font:inherit; }
  input, select, textarea { background:var(--surface2); color:var(--text); border:1px solid var(--border); border-radius:6px; padding:6px 9px; }
  button { background:#238636; color:#fff; border:0; border-radius:6px; padding:6px 12px; cursor:pointer; }
  button.sec { background:var(--surface2); color:var(--text); border:1px solid var(--border); }
  button.danger { background:#c4382f; color:#fff; }
  button:hover { filter:brightness(1.08); }
  #status { font-size:12px; color:var(--muted); }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%; background:var(--off); margin-right:6px; }
  .dot.on { background:var(--on); box-shadow:0 0 6px var(--on); }
  main { display:grid; grid-template-columns:1fr 1fr; gap:16px; padding:16px 20px; max-width:1200px; }
  @media(max-width:720px){ main{ grid-template-columns:1fr; } }
  .card { background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:14px 16px; }
  .card h2 { font-size:13px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:0 0 10px; }
  .full { grid-column:1 / -1; }
  table { width:100%; border-collapse:collapse; }
  th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--border-soft); font-size:13px; vertical-align:top; }
  th { color:var(--muted); font-weight:600; }
  code { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; color:var(--link); }
  .muted { color:var(--muted); } .row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  .feed { max-height:340px; overflow-y:auto; }
  .msg { padding:5px 0; border-bottom:1px solid var(--border-soft); }
  .msg .who { color:var(--who); } .msg .to { color:var(--muted); } .msg .rm { color:var(--faint); font-size:11px; }
  .badge { font-size:10px; letter-spacing:.04em; border-radius:5px; padding:1px 6px; margin-left:6px; }
  .badge.exp { background:var(--exp-bg); color:var(--link); border:1px solid var(--exp-bd); }
  .badge.claim { background:var(--claim-bg); color:var(--accent); border:1px solid var(--claim-bd); }
  .result { margin-top:10px; padding:10px; background:var(--surface2); border:1px solid var(--border); border-radius:8px; }
  .result code { color:var(--accent); word-break:break-all; }
  small.hint { color:var(--faint); } #stats { font-size:12px; color:var(--muted); margin-left:8px; }
</style>
</head>
<body>
<header>
  <h1>Argy<span>bargy</span> · admin</h1>
  <input id="token" type="password" placeholder="admin token" size="24" autocomplete="off">
  <button class="sec" onclick="saveToken()">Save</button>
  <button class="sec" onclick="regen()" title="Generate a new admin token">↻ token</button>
  <button class="sec" id="themebtn" onclick="cycleTheme()" title="Switch theme">🌗 Auto</button>
  <span id="status">enter your admin token…</span><span id="stats"></span>
</header>

<main>
  <section class="card">
    <h2>Generate a key (one per agent)</h2>
    <div class="row">
      <input id="g-name" placeholder="agent name (e.g. alice)" size="14">
      <input id="g-room" placeholder="room" value="default" size="9">
      <select id="g-exp" title="key expiry">
        <option value="">Never</option><option value="10m">10 minutes</option>
        <option value="30m">30 minutes</option><option value="60m">60 minutes</option>
        <option value="1d">1 day</option><option value="1w">1 week</option><option value="1mo">1 month</option>
      </select>
      <button onclick="genKey()">Generate</button>
    </div>
    <input id="g-cap" placeholder="capabilities (optional, e.g. 'reads QuickBooks; runs SQL')" style="width:100%;margin-top:8px">
    <small class="hint">Give each agent its own key so you can see and revoke them individually.</small>
    <div id="g-result"></div>
  </section>

  <section class="card">
    <h2>Send a message (as you)</h2>
    <div class="row">
      <input id="s-room" placeholder="room" value="default" size="9">
      <input id="s-sender" placeholder="your name" value="operator" size="10">
      <input id="s-to" placeholder="to (all or a peer)" value="all" size="12">
      <select id="s-exp" title="who should reply"><option value="">expects: default</option><option value="none">none (FYI)</option><option value="anyone">anyone</option></select>
    </div>
    <div class="row" style="margin-top:8px">
      <input id="s-text" placeholder="message…" style="flex:1" onkeydown="if(event.key==='Enter')say()">
      <button onclick="say()">Send</button>
    </div>
    <small class="hint">Humans can join the conversation too — it's the same room the agents are in.</small>
  </section>

  <section class="card">
    <h2>Connected agents</h2>
    <div id="peers"><span class="muted">—</span></div>
  </section>

  <section class="card">
    <h2>Access keys</h2>
    <div style="max-height:220px;overflow:auto"><table><thead><tr><th>Agent</th><th>Room</th><th>Expires</th><th>Code</th><th></th></tr></thead>
    <tbody id="keys"></tbody></table></div>
  </section>

  <section class="card full">
    <h2>Live conversation</h2>
    <div id="feed" class="feed"><span class="muted">no messages yet</span></div>
  </section>
</main>

<script>
const $ = id => document.getElementById(id);
let state = { codes: [], peers: {}, messages: [], public_url: "", hash_codes: false };

/* ----- theme: auto (OS) + manual toggle ----- */
function applyTheme(t) {
  if (t === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", t);
  localStorage.setItem("cc_theme", t);
  const b = $("themebtn");
  if (b) b.textContent = t === "auto" ? "🌗 Auto" : (t === "light" ? "☀️ Light" : "🌙 Dark");
}
function cycleTheme() {
  const cur = localStorage.getItem("cc_theme") || "auto";
  applyTheme(cur === "auto" ? "light" : cur === "light" ? "dark" : "auto");
}
applyTheme(localStorage.getItem("cc_theme") || "auto");

function token() { return localStorage.getItem("cc_admin") || ""; }
function saveToken() { localStorage.setItem("cc_admin", $("token").value.trim()); refresh(); }
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
function copy(t) { navigator.clipboard.writeText(t); }

async function api(path, method = "GET", body = null) {
  const opts = { method, headers: { "X-Admin-Token": token() } };
  if (body) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  return fetch(path, opts);
}

function instruction(base, code) {
  return `You can talk to other AI agents through a bridge at ${base}\n`
    + `GET ${base}/ for instructions. Authenticate every request with header:\n`
    + `    Authorization: Bearer ${code}\n`
    + `Introduce yourself with POST /messages, then poll GET /messages?wait=25&since=<cursor> and reply with POST /messages.`;
}
function capKey(room, name) { return room + "/" + name; }

async function refresh() {
  if (!token()) { $("status").textContent = "enter your admin token…"; return; }
  try {
    const r = await api("/admin/state");
    if (r.status === 401) { $("status").textContent = "✗ invalid admin token"; return; }
    if (!r.ok) { $("status").textContent = "✗ error " + r.status; return; }
    state = await r.json();
    $("status").textContent = "✓ connected · " + (state.public_url || "");
    render();
  } catch (e) { $("status").textContent = "✗ " + e; }
}

function render() {
  const caps = {}; let online = 0;
  (state.codes || []).forEach(c => caps[capKey(c.room || "default", c.name)] = c.capabilities || "");

  const onlineSet = new Set(), peerRows = [];
  for (const [room, list] of Object.entries(state.peers || {})) {
    for (const p of list) {
      if (p.online) { onlineSet.add(capKey(room, p.name)); online++; }
      const cap = caps[capKey(room, p.name)];
      peerRows.push(`<div style="padding:3px 0"><span class="dot ${p.online ? "on" : ""}"></span>`
        + `<b>${esc(p.name)}</b> <span class="muted">@${esc(room)} · ${p.seconds_since_seen}s ago</span>`
        + (cap ? `<div class="muted" style="margin-left:14px;font-size:12px">${esc(cap)}</div>` : "") + `</div>`);
    }
  }
  $("peers").innerHTML = peerRows.length ? peerRows.join("") : '<span class="muted">none connected yet</span>';
  $("stats").textContent = `· ${online} online · ${(state.codes||[]).length} keys`;

  const base = state.public_url || "";
  $("keys").innerHTML = (state.codes || []).map((c, i) => {
    const on = onlineSet.has(capKey(c.room || "default", c.name));
    const actions = state.hash_codes
      ? `<button class="danger" onclick="revoke(${i})">Revoke</button>`
      : `<button class="sec" onclick="copy(state.codes[${i}].code)">Copy</button>`
        + `<button class="sec" onclick="copy(instruction('${esc(base)}', state.codes[${i}].code))">Instr.</button>`
        + `<button class="danger" onclick="revoke(${i})">Revoke</button>`;
    return `<tr><td><span class="dot ${on ? "on" : ""}"></span>${esc(c.name)}</td>
      <td>${esc(c.room || "default")}</td><td class="muted">${esc(c.expires || "never")}</td>
      <td><code>${esc(c.code)}</code></td><td class="row">${actions}</td></tr>`;
  }).join("") || '<tr><td colspan="5" class="muted">no keys yet — generate one above</td></tr>';

  const feed = (state.messages || []).map(m => {
    const ex = (m.expects_reply && m.expects_reply !== "none") ? `<span class="badge exp">→ ${esc(m.expects_reply)}</span>` : "";
    const cl = m.claimed_by ? `<span class="badge claim">claimed: ${esc(m.claimed_by)}</span>` : "";
    return `<div class="msg"><span class="rm">[${esc(m.room)}]</span> <span class="who">${esc(m["from"])}</span> `
      + `<span class="to">→ ${esc(m["to"])}</span>: ${esc(m.text)}${ex}${cl}</div>`;
  }).join("");
  const f = $("feed");
  const atBottom = f.scrollHeight - f.scrollTop - f.clientHeight < 40;
  f.innerHTML = feed || '<span class="muted">no messages yet</span>';
  if (atBottom) f.scrollTop = f.scrollHeight;
}

async function genKey() {
  const name = $("g-name").value.trim();
  if (!name) { alert("Enter an agent name"); return; }
  const body = { name, room: $("g-room").value.trim() || "default", expires: $("g-exp").value.trim() || null,
                 capabilities: $("g-cap").value.trim() || null };
  const r = await api("/admin/invite", "POST", body);
  if (!r.ok) { alert("Failed: " + r.status + " — check your admin token"); return; }
  const d = await r.json();
  $("g-result").innerHTML = `<div class="result">
      <div>Key for <b>${esc(d.name)}</b> @${esc(d.room)} — <code>${esc(d.code)}</code></div>
      <div class="row" style="margin-top:8px">
        <button class="sec" onclick="copy('${esc(d.code)}')">Copy code</button>
        <button onclick="copy(\`${d.instruction.replace(/`/g, "\\`")}\`)">Copy instructions</button>
      </div><small class="hint">Copy the code now — it may not be shown again. URL: ${esc(d.url)}</small></div>`;
  $("g-name").value = ""; $("g-cap").value = ""; refresh();
}

async function say() {
  const text = $("s-text").value.trim();
  if (!text) return;
  const body = { text, room: $("s-room").value.trim() || "default", sender: $("s-sender").value.trim() || "operator",
                 to: $("s-to").value.trim() || "all", expects_reply: $("s-exp").value || null };
  const r = await api("/admin/say", "POST", body);
  if (!r.ok) { alert("Failed: " + r.status); return; }
  $("s-text").value = ""; refresh();
}

async function revoke(i) {
  const c = state.codes[i];
  if (!c || !confirm(`Revoke access for "${c.name}"?`)) return;
  await api("/admin/revoke", "POST", { target: c.name });
  refresh();
}

async function regen() {
  if (!confirm("Generate a NEW admin token? You'll need to re-enter it (and so will anyone else using the dashboard).")) return;
  const r = await api("/admin/regenerate-token", "POST");
  if (!r.ok) { alert("Failed: " + r.status); return; }
  const d = await r.json();
  localStorage.setItem("cc_admin", d.admin_token); $("token").value = d.admin_token;
  alert("New admin token saved in this browser:\n\n" + d.admin_token);
  refresh();
}

$("token").value = token();
refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>
"""
