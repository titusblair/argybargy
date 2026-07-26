"""Admin dashboard — one self-contained HTML page, no build step.

A presence-first mesh client: sidebar (rooms + live agents with vendor logos),
a conversation timeline with turn-taking badges, a pinned composer, and an
admin drawer for keys/token. Auto light/dark following the OS, with a manual
Auto/Light/Dark toggle. Asks for the admin token (stored in localStorage),
polls /admin/state, and lets you mint keys, watch peers + the live
conversation, send messages as a human, and revoke access. Served at
GET /dashboard.

Plain HTML + CSS + vanilla JS in one string — no Node, no bundler, no
framework, no external requests. Edit this file directly.

Design, CSS and layout are derived from the dashboard redesign contributed by
Nick Mason (@designnotdrum), reimplemented here without the build toolchain.
Vendor marks come from simple-icons (CC0); UI glyphs from Phosphor Icons (MIT).
Brand marks are trademarks of their respective owners, used only to identify
which vendor an agent belongs to.
"""

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Argybargy — Admin</title>
<style>
.ad-root{background:var(--surface);flex-direction:column;height:100%;display:flex}.ad-head{border-bottom:1px solid var(--border);flex:none;align-items:center;gap:10px;height:52px;padding:0 16px;display:flex}.ad-title{font-size:14px;font-weight:600}.ad-sub{color:var(--faint);font-size:10px}.ad-close{width:28px;height:28px;color:var(--muted);border-radius:7px;place-items:center;margin-left:auto;display:grid}.ad-close:hover{color:var(--text);background:var(--raised)}.ad-body{padding:4px 16px calc(20px + env(safe-area-inset-bottom));flex:1;overflow-y:auto}.ad-sec{border-bottom:1px solid var(--border);padding:16px 0}.ad-sec:last-child{border-bottom:0}.ad-label{color:var(--faint);text-transform:uppercase;letter-spacing:.1em;align-items:center;gap:6px;margin-bottom:10px;font-size:10px;font-weight:600;display:flex}.ad-label.danger{color:color-mix(in srgb, var(--red) 70%, var(--faint))}.ad-hint{color:var(--faint);margin:8px 0 0;font-size:11.5px;line-height:1.5}.ad-urlrow{font-family:var(--mono);color:var(--muted);background:var(--bg);border:1px solid var(--border);border-radius:8px;align-items:center;gap:8px;padding:7px 6px 7px 11px;font-size:12px;display:flex}.ad-urlrow .ad-u{text-overflow:ellipsis;white-space:nowrap;flex:1;overflow:hidden}.ad-field{width:100%;color:var(--text);background:var(--bg);border:1px solid var(--border-strong);border-radius:8px;outline:none;padding:7px 10px;font-family:inherit;font-size:13px}.ad-field:focus{border-color:color-mix(in srgb, var(--green) 40%, var(--border-strong))}.ad-field::placeholder{color:var(--faint)}select.ad-field{appearance:none;background-image:none}.ad-frow{gap:8px;margin-bottom:8px;display:flex}.ad-frow .ad-grow{flex:1;min-width:0}.ad-btn{height:30px;color:var(--text);background:var(--raised);border:1px solid var(--border-strong);border-radius:8px;align-items:center;gap:6px;padding:0 13px;font-size:12.5px;font-weight:500;display:inline-flex}.ad-btn:hover{border-color:color-mix(in srgb, var(--text) 25%, transparent)}.ad-btn.primary{color:var(--bg);background:var(--text);border-color:#0000}.ad-btn.primary:hover{opacity:.9}.ad-btn.danger{color:var(--red);border-color:color-mix(in srgb, var(--red) 38%, transparent);background:0 0}.ad-btn.danger:hover{background:var(--red-dim)}.ad-btn.danger.confirm{color:#fff;background:var(--red);border-color:#0000}.ad-btn:disabled{cursor:default;opacity:.55}.ad-resultbox{background:var(--green-dim);border:1px solid color-mix(in srgb, var(--green) 32%, transparent);border-radius:9px;margin-top:10px;padding:10px 12px;font-size:12px;line-height:1.6}.ad-resultbox .ad-code{font-family:var(--mono);color:var(--text);word-break:break-all;font-size:11.5px}.ad-resultbox .ad-hint{margin-top:4px}.ad-errorbox{color:var(--red);background:var(--red-dim);border:1px solid color-mix(in srgb, var(--red) 38%, transparent);border-radius:9px;margin-top:10px;padding:10px 12px;font-size:12px;line-height:1.6}.ad-krow{border-bottom:1px solid var(--border);padding:9px 0}.ad-krow:last-child{border-bottom:0}.ad-kline{align-items:center;gap:7px;min-width:0;display:flex}.ad-kdot{background:var(--faint);border-radius:50%;flex:none;width:6px;height:6px}.ad-kdot.on{background:var(--green)}.ad-kname{font-size:12.5px;font-weight:600}.ad-kmeta{text-overflow:ellipsis;font-family:var(--mono);color:var(--faint);white-space:nowrap;flex:1;font-size:10px;overflow:hidden}.ad-kacts{flex:none;gap:2px;display:flex}.ad-icbtn{width:24px;height:22px;color:var(--faint);border-radius:6px;place-items:center;display:grid}.ad-icbtn:hover{color:var(--text);background:var(--raised)}.ad-icbtn.ok{color:var(--green)}.ad-kkill{color:var(--faint);letter-spacing:.04em;border-radius:6px;padding:2px 7px;font-size:10.5px;font-weight:600}.ad-kkill:hover{color:var(--red);background:var(--red-dim)}.ad-kkill.confirm{color:#fff;background:var(--red)}.ad-kcode{font-family:var(--mono);color:var(--muted);word-break:break-all;margin:3px 0 0 13px;font-size:10.5px}.ad-kcap{color:var(--faint);margin:2px 0 0 13px;font-size:11px}@media (width<=640px){.ad-field,.ad-btn{font-size:16px}}@media (prefers-reduced-motion:reduce){.ad-root,.ad-root *{transition:none!important;animation:none!important}}.conv-pane{min-width:0;height:100%;min-height:0;color:var(--text);background:var(--bg);flex-direction:column;flex:1;display:flex}.hue-0{--agent:#ef93b4}.hue-1{--agent:#7cb3f5}.hue-2{--agent:#a78bfa}.hue-3{--agent:#e3b25c}.hue-4{--agent:#55d0bf}.hue-op{--agent:#cfc4a6}:root[data-theme=light] .hue-0{--agent:#bd3e6c}:root[data-theme=light] .hue-1{--agent:#2e6fd0}:root[data-theme=light] .hue-2{--agent:#6b4fd8}:root[data-theme=light] .hue-3{--agent:#96690a}:root[data-theme=light] .hue-4{--agent:#0c8577}:root[data-theme=light] .hue-op{--agent:#7a6d4c}.conv-header{border-bottom:1px solid var(--border);flex:none;align-items:center;gap:9px;min-width:0;height:52px;padding:0 16px;display:flex}.conv-header__hash{color:var(--faint);flex:none}.conv-header__name{text-overflow:ellipsis;white-space:nowrap;font-size:14px;font-weight:600;overflow:hidden}.conv-header__meta{color:var(--faint);white-space:nowrap;align-items:center;gap:5px;font-size:11px;display:flex}.conv-header__sep{background:var(--border-strong);flex:none;width:1px;height:16px}.conv-header__back{width:28px;height:28px;color:var(--muted);border-radius:7px;place-items:center;margin-left:-6px;display:grid}.conv-header__back:hover{color:var(--text);background:var(--raised)}.conv-header__filterchip{font-family:var(--mono);color:var(--faint);border:1px solid var(--border);border-radius:999px;flex:none;align-items:center;gap:4px;margin-left:auto;padding:3px 8px;font-size:10px;display:inline-flex}.conv-timeline{flex:1;min-height:0;padding:10px 0 16px;overflow:hidden auto}.conv-daydiv{align-items:center;gap:10px;padding:6px 18px 10px;display:flex}.conv-daydiv:before,.conv-daydiv:after{content:"";background:var(--border);flex:1;height:1px}.conv-daydiv span{color:var(--faint);text-transform:uppercase;letter-spacing:.12em;font-size:9.5px;font-weight:600}.conv-group{--dotring:var(--bg);gap:10px;padding:7px 18px;display:flex}.conv-group__body{flex:1;min-width:0}.conv-group__head{align-items:baseline;gap:8px;min-width:0;display:flex}.conv-group__name{color:var(--agent);font-size:13px;font-weight:600}.conv-group--op .conv-group__name{color:var(--text)}.conv-oppill{color:var(--muted);text-transform:uppercase;letter-spacing:.09em;border:1px solid var(--border-strong);border-radius:4px;padding:1.5px 5px;font-size:8.5px;font-weight:600;position:relative;top:-1px}.conv-msg{max-width:78ch;color:var(--text);overflow-wrap:anywhere;margin-top:2px;font-size:13.5px;line-height:1.55}.conv-msg+.conv-msg{margin-top:5px}.conv-dir{font-family:var(--mono);color:color-mix(in srgb, var(--agent) 78%, var(--muted));margin-right:6px;font-size:11.5px;font-weight:500}.conv-empty{place-items:center;height:100%;display:grid}.conv-empty .ph{color:var(--faint);opacity:.5;margin:0 auto 10px}.conv-empty__t1{color:var(--muted);text-align:center;font-size:13.5px;font-weight:500}.conv-empty__t2{color:var(--faint);text-align:center;margin-top:3px;font-size:12px}.conv-avatar{width:30px;height:30px;color:var(--agent);letter-spacing:.02em;-webkit-user-select:none;user-select:none;background:color-mix(in srgb, var(--agent) 15%, transparent);border:1px solid color-mix(in srgb, var(--agent) 40%, transparent);border-radius:9px;flex:none;place-items:center;font-size:11px;font-weight:600;display:grid;position:relative}.conv-avatar--round{border-radius:50%}.conv-avatar--sm{border-radius:6px;width:20px;height:20px;font-size:8px}.conv-avatar--sm.conv-avatar--round{border-radius:50%}.conv-avatar__dot{background:var(--green);width:9px;height:9px;box-shadow:0 0 0 2.5px var(--dotring,var(--bg));border-radius:50%;position:absolute;bottom:-3px;right:-3px}.conv-avatar__dot--off{background:var(--dotring,var(--bg));border:1.5px solid var(--faint);box-shadow:0 0 0 2px var(--dotring,var(--bg))}.badge-pill{vertical-align:1px;text-transform:uppercase;letter-spacing:.09em;white-space:nowrap;border:1px solid;border-radius:999px;align-items:center;gap:5px;margin-left:8px;padding:2.5px 8px;font-size:9px;font-weight:600;display:inline-flex}.badge-pill__timer{font-family:var(--mono);text-transform:none;letter-spacing:0;opacity:.85;font-size:10px;font-weight:500}.badge-pill--expects{color:var(--amber);background:var(--amber-dim);border-color:color-mix(in srgb, var(--amber) 42%, transparent)}.badge-pill--claimed{color:color-mix(in srgb, var(--green) 78%, var(--muted));background:var(--green-dim);border-color:color-mix(in srgb, var(--green) 35%, transparent)}.conv-composer{padding:10px 16px calc(12px + env(safe-area-inset-bottom));border-top:1px solid var(--border);flex:none}.conv-composer__error{color:var(--red);background:var(--red-dim);border:1px solid color-mix(in srgb, var(--red) 38%, transparent);border-radius:8px;margin-bottom:8px;padding:7px 10px;font-size:12px}.conv-composer__frame{background:var(--surface);border:1px solid var(--border-strong);border-radius:10px;transition:border-color .15s}.conv-composer__frame:focus-within{border-color:color-mix(in srgb, var(--green) 40%, var(--border-strong))}.conv-composer__input{width:100%;font:400 13.5px / 1.5 var(--sans);color:var(--text);background:0 0;border:0;outline:0;padding:10px 12px 2px;display:block}.conv-composer__input::placeholder{color:var(--faint)}.conv-composer__row{flex-wrap:wrap;align-items:center;gap:6px;padding:7px 8px 8px;display:flex}.conv-pill{height:24px;color:var(--muted);border:1px solid var(--border);background:0 0;border-radius:999px;align-items:center;gap:5px;padding:0 9px;font-size:11.5px;font-weight:500;display:inline-flex}.conv-pill:hover{color:var(--text);border-color:var(--border-strong)}.conv-pill--armed{color:var(--amber);background:var(--amber-dim);border-color:color-mix(in srgb, var(--amber) 42%, transparent)}.conv-pill--hued{color:var(--agent);border-color:color-mix(in srgb, var(--agent) 38%, transparent)}.conv-pill--lock{cursor:default}.conv-pill--lock:hover{border-color:color-mix(in srgb, var(--agent) 38%, transparent)}.conv-composer__as-input{width:82px;height:24px;font:500 11.5px var(--sans);color:var(--text);border:1px solid var(--border-strong);background:0 0;border-radius:999px;outline:0;padding:0 9px}.conv-composer__to-wrap{position:relative}.conv-menu{z-index:20;background:var(--raised);border:1px solid var(--border-strong);min-width:190px;box-shadow:var(--pop-shadow);border-radius:9px;padding:4px;position:absolute;bottom:calc(100% + 6px);left:0}:root[data-theme=light] .conv-menu{background:#fff}.conv-menu__item{--dotring:var(--raised);width:100%;color:var(--text);text-align:left;background:0 0;border-radius:6px;align-items:center;gap:8px;padding:6px 8px;font-size:12.5px;display:flex}.conv-menu__item:hover{background:color-mix(in srgb, var(--text) 7%, transparent)}.conv-menu__who{flex:1}.conv-menu__k{font-family:var(--mono);color:var(--faint);font-size:9.5px}.conv-send{width:32px;height:26px;color:var(--faint);background:var(--raised);border:1px solid var(--border);border-radius:8px;place-items:center;margin-left:auto;transition:color .15s;display:grid}.conv-send--ready{color:var(--green)}.conv-send:hover{border-color:var(--border-strong)}@media (width<=640px){.conv-header{padding:0 12px}.conv-group{padding:7px 12px}.conv-daydiv{padding:6px 12px 10px}.conv-composer{padding-left:12px;padding-right:12px}.conv-composer__input,.conv-composer__as-input{font-size:16px}.conv-header__plabel{display:none}}@media (prefers-reduced-motion:reduce){.conv-pane *{transition:none!important;animation:none!important}}.agent-logo{width:58%;height:58%}.agent-logo--person{width:70%;height:70%}.sb-av.is-brand,.conv-avatar.is-brand{color:var(--agent);background:color-mix(in srgb, var(--text) 6%, transparent);border-color:var(--border-strong)}.sb-aname--brand{color:var(--agent)}.sb-root{width:100%;height:100%;min-height:0;color:var(--text);background:var(--rail);flex-direction:column;display:flex}.sb-head{border-bottom:1px solid var(--border);flex:none;align-items:center;gap:8px;height:52px;padding:0 16px;display:flex}.sb-wsname{letter-spacing:-.01em;font-size:14px;font-weight:600}.sb-conn{background:var(--faint);border-radius:50%;flex:none;width:7px;height:7px}.sb-conn.live{background:var(--green);box-shadow:0 0 7px color-mix(in srgb, var(--green) 55%, transparent)}.sb-conn.error{background:var(--red);box-shadow:0 0 7px color-mix(in srgb, var(--red) 55%, transparent)}.sb-wsurl{color:var(--faint);margin-left:auto;font-size:10px}.sb-nav{flex:1;min-height:0;padding-bottom:8px;overflow:hidden auto}.sb-label{color:var(--faint);text-transform:uppercase;letter-spacing:.1em;align-items:center;gap:5px;padding:16px 16px 6px;font-size:10px;font-weight:600;display:flex}.sb-label .sb-n{font-family:var(--mono);font-weight:500}.sb-room{width:calc(100% - 12px);height:30px;color:var(--muted);text-align:left;border-radius:7px;align-items:center;gap:8px;margin:0 6px;padding:0 10px;font-size:13px;display:flex}.sb-room .sb-ph{color:var(--faint);flex:none;display:block}.sb-room:hover{color:var(--text);background:color-mix(in srgb, var(--raised) 70%, transparent)}.sb-room.active{color:var(--text);background:var(--raised)}.sb-room.active .sb-ph{color:var(--muted)}.sb-room.unread{color:var(--text);font-weight:600}.sb-udot{background:var(--text);border-radius:50%;flex:none;width:5px;height:5px;margin-left:auto}.sb-arow{--dotring:var(--rail);text-align:left;border-radius:7px;align-items:center;gap:9px;width:calc(100% - 12px);max-height:44px;margin:0 6px;padding:6px 10px;transition:opacity 2s;display:flex;overflow:hidden}.sb-arow:hover{background:color-mix(in srgb, var(--raised) 70%, transparent)}.sb-arow.active{background:var(--raised)}.sb-aname{text-overflow:ellipsis;color:var(--text);white-space:nowrap;font-size:13px;font-weight:500;overflow:hidden}.sb-alast{font-family:var(--mono);color:var(--faint);flex:none;margin-left:auto;font-size:10.5px}.sb-arow.fading{opacity:.45}.sb-arow.fading .sb-aname{color:var(--muted)}.sb-arow.joining{animation:.35s sb-rowin}@keyframes sb-rowin{0%{opacity:0;transform:translateY(3px)}to{opacity:1;transform:none}}.sb-av{width:26px;height:26px;color:var(--agent);letter-spacing:.02em;-webkit-user-select:none;user-select:none;background:color-mix(in srgb, var(--agent) 15%, transparent);border:1px solid color-mix(in srgb, var(--agent) 40%, transparent);border-radius:8px;flex:none;place-items:center;font-size:10px;font-weight:600;display:grid;position:relative}.sb-pdot{background:var(--green);width:9px;height:9px;box-shadow:0 0 0 2.5px var(--dotring,var(--rail));border-radius:50%;position:absolute;bottom:-3px;right:-3px}.sb-pdot.off{background:var(--dotring,var(--rail));border:1.5px solid var(--faint);box-shadow:0 0 0 2px var(--dotring,var(--rail))}.sb-arow.fading .sb-av{filter:grayscale(.55)}.sb-arow.join-pulse .sb-pdot{animation:.9s ease-out 2 sb-joinpulse}@keyframes sb-joinpulse{0%{box-shadow:0 0 0 2.5px var(--dotring,var(--rail)), 0 0 0 2.5px color-mix(in srgb, var(--green) 55%, transparent)}to{box-shadow:0 0 0 2.5px var(--dotring,var(--rail)), 0 0 0 12px transparent}}.sb-recent-head{width:calc(100% - 12px);color:var(--faint);text-align:left;border-radius:7px;align-items:center;gap:6px;margin:6px 6px 0;padding:5px 10px;font-size:11px;font-weight:500;display:flex}.sb-recent-head:hover{color:var(--muted);background:color-mix(in srgb, var(--raised) 60%, transparent)}.sb-recent-head .sb-ph{transition:transform .15s}.sb-recent-head.open .sb-ph{transform:rotate(90deg)}.sb-recent-row{--dotring:var(--rail);opacity:.55}.sb-recent-row .sb-av{filter:grayscale(.55)}.sb-recent-row .sb-aname{color:var(--muted);font-weight:400}.sb-foot{height:52px;padding:0 10px calc(0px + env(safe-area-inset-bottom));border-top:1px solid var(--border);flex:none;align-items:center;gap:8px;display:flex}.sb-iconbtn{width:30px;height:28px;color:var(--muted);border-radius:7px;flex:none;place-items:center;display:grid}.sb-iconbtn:hover{color:var(--text);background:var(--raised)}.sb-seg{border:1px solid var(--border);border-radius:7px;flex:none;min-inline-size:auto;margin:0 0 0 auto;padding:0;display:flex;overflow:hidden}.sb-seg button{width:28px;height:24px;color:var(--faint);place-items:center;display:grid}.sb-seg button:hover{color:var(--muted)}.sb-seg button.on{color:var(--text);background:var(--raised)}.sb-seg button+button{border-left:1px solid var(--border)}@media (prefers-reduced-motion:reduce){.sb-arow,.sb-arow.joining,.sb-arow.join-pulse .sb-pdot{transition:none!important;animation:none!important}}@layer properties{@supports (((-webkit-hyphens:none)) and (not (margin-trim:inline))) or ((-moz-orient:inline) and (not (color:rgb(from red r g b)))){*,:before,:after,::backdrop{--tw-translate-x:0;--tw-translate-y:0;--tw-translate-z:0;--tw-rotate-x:initial;--tw-rotate-y:initial;--tw-rotate-z:initial;--tw-skew-x:initial;--tw-skew-y:initial;--tw-border-style:solid;--tw-blur:initial;--tw-brightness:initial;--tw-contrast:initial;--tw-grayscale:initial;--tw-hue-rotate:initial;--tw-invert:initial;--tw-opacity:initial;--tw-saturate:initial;--tw-sepia:initial;--tw-drop-shadow:initial;--tw-drop-shadow-color:initial;--tw-drop-shadow-alpha:100%;--tw-drop-shadow-size:initial;--tw-duration:initial;--tw-ease:initial}}}@layer theme{:root,:host{--font-sans:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans", Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji";--font-mono:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;--spacing:.25rem;--text-xs:.75rem;--text-xs--line-height:calc(1 / .75);--radius-md:.375rem;--ease-in-out:cubic-bezier(.4, 0, .2, 1);--default-transition-duration:.15s;--default-transition-timing-function:cubic-bezier(.4, 0, .2, 1);--default-font-family:var(--font-sans);--default-mono-font-family:var(--font-mono)}}@layer base{*,:after,:before,::backdrop{box-sizing:border-box;border:0 solid;margin:0;padding:0}::file-selector-button{box-sizing:border-box;border:0 solid;margin:0;padding:0}html,:host{-webkit-text-size-adjust:100%;tab-size:4;line-height:1.5;font-family:var(--default-font-family,-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans", Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji");font-feature-settings:var(--default-font-feature-settings,normal);font-variation-settings:var(--default-font-variation-settings,normal);-webkit-tap-highlight-color:transparent}hr{height:0;color:inherit;border-top-width:1px}abbr:where([title]){-webkit-text-decoration:underline dotted;text-decoration:underline dotted}h1,h2,h3,h4,h5,h6{font-size:inherit;font-weight:inherit}a{color:inherit;-webkit-text-decoration:inherit;-webkit-text-decoration:inherit;-webkit-text-decoration:inherit;-webkit-text-decoration:inherit;text-decoration:inherit}b,strong{font-weight:bolder}code,kbd,samp,pre{font-family:var(--default-mono-font-family,ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace);font-feature-settings:var(--default-mono-font-feature-settings,normal);font-variation-settings:var(--default-mono-font-variation-settings,normal);font-size:1em}small{font-size:80%}sub,sup{vertical-align:baseline;font-size:75%;line-height:0;position:relative}sub{bottom:-.25em}sup{top:-.5em}table{text-indent:0;border-color:inherit;border-collapse:collapse}:-moz-focusring:where(:not(iframe)){outline:auto}progress{vertical-align:baseline}summary{display:list-item}ol,ul,menu{list-style:none}img,svg,video,canvas,audio,iframe,embed,object{vertical-align:middle;display:block}img,video{max-width:100%;height:auto}button,input,select,optgroup,textarea{font:inherit;font-feature-settings:inherit;font-variation-settings:inherit;letter-spacing:inherit;color:inherit;opacity:1;background-color:#0000;border-radius:0}::file-selector-button{font:inherit;font-feature-settings:inherit;font-variation-settings:inherit;letter-spacing:inherit;color:inherit;opacity:1;background-color:#0000;border-radius:0}:where(select:is([multiple],[size])) optgroup{font-weight:bolder}:where(select:is([multiple],[size])) optgroup option{padding-inline-start:20px}::file-selector-button{margin-inline-end:4px}::placeholder{opacity:1}@supports (not ((-webkit-appearance:-apple-pay-button))) or (contain-intrinsic-size:1px){::placeholder{color:currentColor}@supports (color:color-mix(in lab, red, red)){::placeholder{color:color-mix(in oklab, currentcolor 50%, transparent)}}}textarea{resize:vertical}::-webkit-search-decoration{-webkit-appearance:none}::-webkit-date-and-time-value{min-height:1lh;text-align:inherit}::-webkit-datetime-edit{display:inline-flex}::-webkit-datetime-edit-fields-wrapper{padding:0}::-webkit-datetime-edit{padding-block:0}::-webkit-datetime-edit-year-field{padding-block:0}::-webkit-datetime-edit-month-field{padding-block:0}::-webkit-datetime-edit-day-field{padding-block:0}::-webkit-datetime-edit-hour-field{padding-block:0}::-webkit-datetime-edit-minute-field{padding-block:0}::-webkit-datetime-edit-second-field{padding-block:0}::-webkit-datetime-edit-millisecond-field{padding-block:0}::-webkit-datetime-edit-meridiem-field{padding-block:0}::-webkit-calendar-picker-indicator{line-height:1}:-moz-ui-invalid{box-shadow:none}button,input:where([type=button],[type=reset],[type=submit]){appearance:button}::file-selector-button{appearance:button}::-webkit-inner-spin-button{height:auto}::-webkit-outer-spin-button{height:auto}[hidden]:where(:not([hidden=until-found])){display:none!important}}@layer components;@layer utilities{.collapse{visibility:collapse}.visible{visibility:visible}.fixed{position:fixed}.static{position:static}.inset-0{inset:0}.inset-y-0{inset-block:0}.right-0{right:0}.left-0{left:0}.z-30{z-index:30}.z-40{z-index:40}.z-50{z-index:50}.block{display:block}.flex{display:flex}.grid{display:grid}.hidden{display:none}.inline{display:inline}.h-dvh{height:100dvh}.min-h-0{min-height:0}.w-\[min\(82vw\,300px\)\]{width:min(82vw,300px)}.w-\[min\(430px\,100vw\)\]{width:min(430px,100vw)}.w-full{width:100%}.min-w-0{min-width:0}.flex-1{flex:1}.-translate-x-full{--tw-translate-x:-100%;translate:var(--tw-translate-x) var(--tw-translate-y)}.translate-x-0{--tw-translate-x:0px;translate:var(--tw-translate-x) var(--tw-translate-y)}.transform{transform:var(--tw-rotate-x,) var(--tw-rotate-y,) var(--tw-rotate-z,) var(--tw-skew-x,) var(--tw-skew-y,)}.flex-col{flex-direction:column}.items-center{align-items:center}.overflow-hidden{overflow:hidden}.rounded-md{border-radius:var(--radius-md)}.border-r{border-right-style:var(--tw-border-style);border-right-width:1px}.border-b{border-bottom-style:var(--tw-border-style);border-bottom-width:1px}.border-l{border-left-style:var(--tw-border-style);border-left-width:1px}.border-\[var\(--border\)\]{border-color:var(--border)}.border-\[var\(--border-strong\)\]{border-color:var(--border-strong)}.bg-\[var\(--bg\)\]{background-color:var(--bg)}.bg-\[var\(--scrim\)\]{background-color:var(--scrim)}.px-2{padding-inline:calc(var(--spacing) * 2)}.px-3{padding-inline:calc(var(--spacing) * 3)}.py-1{padding-block:var(--spacing)}.py-2{padding-block:calc(var(--spacing) * 2)}.text-xs{font-size:var(--text-xs);line-height:var(--tw-leading,var(--text-xs--line-height))}.text-\[var\(--muted\)\]{color:var(--muted)}.text-\[var\(--text\)\]{color:var(--text)}.lowercase{text-transform:lowercase}.filter{filter:var(--tw-blur,) var(--tw-brightness,) var(--tw-contrast,) var(--tw-grayscale,) var(--tw-hue-rotate,) var(--tw-invert,) var(--tw-saturate,) var(--tw-sepia,) var(--tw-drop-shadow,)}.transition-transform{transition-property:transform,translate,scale,rotate;transition-timing-function:var(--tw-ease,var(--default-transition-timing-function));transition-duration:var(--tw-duration,var(--default-transition-duration))}.duration-200{--tw-duration:.2s;transition-duration:.2s}.ease-in-out{--tw-ease:var(--ease-in-out);transition-timing-function:var(--ease-in-out)}@media (width>=40rem){.sm\:static{position:static}.sm\:z-auto{z-index:auto}.sm\:hidden{display:none}.sm\:w-64{width:calc(var(--spacing) * 64)}.sm\:shrink-0{flex-shrink:0}.sm\:translate-x-0{--tw-translate-x:0px;translate:var(--tw-translate-x) var(--tw-translate-y)}.sm\:border-r{border-right-style:var(--tw-border-style);border-right-width:1px}.sm\:border-\[var\(--border\)\]{border-color:var(--border)}}}:root{--bg:#0a0c10;--rail:#0d1016;--surface:#10141b;--raised:#151a23;--border:#ffffff12;--border-strong:#ffffff21;--text:#e7ebf2;--muted:#8b94a3;--faint:#5c6472;--green:#34d399;--green-dim:#34d3991f;--amber:#f0b64f;--amber-dim:#f0b64f17;--red:#f47067;--red-dim:#f470671a;--scrim:#0204088c;--pop-shadow:none;--mono:ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace;--sans:ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;--lightningcss-light: ;--lightningcss-dark:initial;color-scheme:dark}:root[data-theme=light]{--bg:#fff;--rail:#f4f5f8;--surface:#f8f9fb;--raised:#e9ecf2;--border:#121a2917;--border-strong:#121a292b;--text:#1a212e;--muted:#5c6675;--faint:#98a1b0;--green:#0e9b6c;--green-dim:#0e9b6c17;--amber:#9a6700;--amber-dim:#9a670012;--red:#c9403a;--red-dim:#c9403a12;--scrim:#171c2652;--pop-shadow:0 8px 24px #141c2d1a;--lightningcss-light:initial;--lightningcss-dark: ;color-scheme:light}:root[data-theme=dark]{--bg:#0a0c10;--rail:#0d1016;--surface:#10141b;--raised:#151a23;--border:#ffffff12;--border-strong:#ffffff21;--text:#e7ebf2;--muted:#8b94a3;--faint:#5c6472;--green:#34d399;--green-dim:#34d3991f;--amber:#f0b64f;--amber-dim:#f0b64f17;--red:#f47067;--red-dim:#f470671a;--scrim:#0204088c;--pop-shadow:none;--lightningcss-light: ;--lightningcss-dark:initial;color-scheme:dark}@media (prefers-color-scheme:light){:root,:root[data-theme=auto]{--bg:#fff;--rail:#f4f5f8;--surface:#f8f9fb;--raised:#e9ecf2;--border:#121a2917;--border-strong:#121a292b;--text:#1a212e;--muted:#5c6675;--faint:#98a1b0;--green:#0e9b6c;--green-dim:#0e9b6c17;--amber:#9a6700;--amber-dim:#9a670012;--red:#c9403a;--red-dim:#c9403a12;--scrim:#171c2652;--pop-shadow:0 8px 24px #141c2d1a;--lightningcss-light:initial;--lightningcss-dark: ;color-scheme:light}}:root{--hue-0:#ef93b4;--hue-1:#7cb3f5;--hue-2:#a78bfa;--hue-3:#e3b25c;--hue-4:#55d0bf;--hue-5:#cfc4a6}:root[data-theme=light]{--hue-0:#bd3e6c;--hue-1:#2e6fd0;--hue-2:#6b4fd8;--hue-3:#96690a;--hue-4:#0c8577;--hue-5:#7a6d4c}:root[data-theme=dark]{--hue-0:#ef93b4;--hue-1:#7cb3f5;--hue-2:#a78bfa;--hue-3:#e3b25c;--hue-4:#55d0bf;--hue-5:#cfc4a6}@media (prefers-color-scheme:light){:root,:root[data-theme=auto]{--hue-0:#bd3e6c;--hue-1:#2e6fd0;--hue-2:#6b4fd8;--hue-3:#96690a;--hue-4:#0c8577;--hue-5:#7a6d4c}}.h0{--agent:var(--hue-0)}.h1{--agent:var(--hue-1)}.h2{--agent:var(--hue-2)}.h3{--agent:var(--hue-3)}.h4{--agent:var(--hue-4)}.hop{--agent:var(--hue-5)}body{font:400 13.5px / 1.5 var(--sans);-webkit-font-smoothing:antialiased;color:var(--text);background:var(--bg);text-rendering:optimizelegibility}.mono{font-family:var(--mono)}:focus-visible{outline:2px solid var(--green)}@supports (color:color-mix(in lab, red, red)){:focus-visible{outline:2px solid color-mix(in srgb, var(--green) 55%, transparent)}}:focus-visible{outline-offset:1px;border-radius:6px}*{scrollbar-color:var(--border-strong) transparent;scrollbar-width:thin}::-webkit-scrollbar{width:8px;height:8px}::-webkit-scrollbar-thumb{background:var(--border-strong);border-radius:4px}::-webkit-scrollbar-track{background:0 0}@media (prefers-reduced-motion:reduce){*,:before,:after{transition:none!important;animation:none!important}}@property --tw-translate-x{syntax:"*";inherits:false;initial-value:0}@property --tw-translate-y{syntax:"*";inherits:false;initial-value:0}@property --tw-translate-z{syntax:"*";inherits:false;initial-value:0}@property --tw-rotate-x{syntax:"*";inherits:false}@property --tw-rotate-y{syntax:"*";inherits:false}@property --tw-rotate-z{syntax:"*";inherits:false}@property --tw-skew-x{syntax:"*";inherits:false}@property --tw-skew-y{syntax:"*";inherits:false}@property --tw-border-style{syntax:"*";inherits:false;initial-value:solid}@property --tw-blur{syntax:"*";inherits:false}@property --tw-brightness{syntax:"*";inherits:false}@property --tw-contrast{syntax:"*";inherits:false}@property --tw-grayscale{syntax:"*";inherits:false}@property --tw-hue-rotate{syntax:"*";inherits:false}@property --tw-invert{syntax:"*";inherits:false}@property --tw-opacity{syntax:"*";inherits:false}@property --tw-saturate{syntax:"*";inherits:false}@property --tw-sepia{syntax:"*";inherits:false}@property --tw-drop-shadow{syntax:"*";inherits:false}@property --tw-drop-shadow-color{syntax:"*";inherits:false}@property --tw-drop-shadow-alpha{syntax:"<percentage>";inherits:false;initial-value:100%}@property --tw-drop-shadow-size{syntax:"*";inherits:false}@property --tw-duration{syntax:"*";inherits:false}@property --tw-ease{syntax:"*";inherits:false}
/*$vite$:1*/
</style>
</head>
<body>
<div id="app"></div>
<script>
(function () {
  "use strict";

  /* ---------------------------------------------------------------- icons */
  /* Phosphor Icons (MIT), 24x24 drawn on a 0 0 256 256 grid. */
  var ICON = {"hash":"M224,88H175.4l8.47-46.57a8,8,0,0,0-15.74-2.86l-9,49.43H111.4l8.47-46.57a8,8,0,0,0-15.74-2.86L95.14,88H48a8,8,0,0,0,0,16H92.23L83.5,152H32a8,8,0,0,0,0,16H80.6l-8.47,46.57a8,8,0,0,0,6.44,9.3A7.79,7.79,0,0,0,80,224a8,8,0,0,0,7.86-6.57l9-49.43H144.6l-8.47,46.57a8,8,0,0,0,6.44,9.3A7.79,7.79,0,0,0,144,224a8,8,0,0,0,7.86-6.57l9-49.43H208a8,8,0,0,0,0-16H163.77l8.73-48H224a8,8,0,0,0,0-16Zm-76.5,64H99.77l8.73-48h47.73Z","caretRight":"M181.66,133.66l-80,80a8,8,0,0,1-11.32-11.32L164.69,128,90.34,53.66a8,8,0,0,1,11.32-11.32l80,80A8,8,0,0,1,181.66,133.66Z","gear":"M128,80a48,48,0,1,0,48,48A48.05,48.05,0,0,0,128,80Zm0,80a32,32,0,1,1,32-32A32,32,0,0,1,128,160Zm88-29.84q.06-2.16,0-4.32l14.92-18.64a8,8,0,0,0,1.48-7.06,107.21,107.21,0,0,0-10.88-26.25,8,8,0,0,0-6-3.93l-23.72-2.64q-1.48-1.56-3-3L186,40.54a8,8,0,0,0-3.94-6,107.71,107.71,0,0,0-26.25-10.87,8,8,0,0,0-7.06,1.49L130.16,40Q128,40,125.84,40L107.2,25.11a8,8,0,0,0-7.06-1.48A107.6,107.6,0,0,0,73.89,34.51a8,8,0,0,0-3.93,6L67.32,64.27q-1.56,1.49-3,3L40.54,70a8,8,0,0,0-6,3.94,107.71,107.71,0,0,0-10.87,26.25,8,8,0,0,0,1.49,7.06L40,125.84Q40,128,40,130.16L25.11,148.8a8,8,0,0,0-1.48,7.06,107.21,107.21,0,0,0,10.88,26.25,8,8,0,0,0,6,3.93l23.72,2.64q1.49,1.56,3,3L70,215.46a8,8,0,0,0,3.94,6,107.71,107.71,0,0,0,26.25,10.87,8,8,0,0,0,7.06-1.49L125.84,216q2.16.06,4.32,0l18.64,14.92a8,8,0,0,0,7.06,1.48,107.21,107.21,0,0,0,26.25-10.88,8,8,0,0,0,3.93-6l2.64-23.72q1.56-1.48,3-3L215.46,186a8,8,0,0,0,6-3.94,107.71,107.71,0,0,0,10.87-26.25,8,8,0,0,0-1.49-7.06Zm-16.1-6.5a73.93,73.93,0,0,1,0,8.68,8,8,0,0,0,1.74,5.48l14.19,17.73a91.57,91.57,0,0,1-6.23,15L187,173.11a8,8,0,0,0-5.1,2.64,74.11,74.11,0,0,1-6.14,6.14,8,8,0,0,0-2.64,5.1l-2.51,22.58a91.32,91.32,0,0,1-15,6.23l-17.74-14.19a8,8,0,0,0-5-1.75h-.48a73.93,73.93,0,0,1-8.68,0,8,8,0,0,0-5.48,1.74L100.45,215.8a91.57,91.57,0,0,1-15-6.23L82.89,187a8,8,0,0,0-2.64-5.1,74.11,74.11,0,0,1-6.14-6.14,8,8,0,0,0-5.1-2.64L46.43,170.6a91.32,91.32,0,0,1-6.23-15l14.19-17.74a8,8,0,0,0,1.74-5.48,73.93,73.93,0,0,1,0-8.68,8,8,0,0,0-1.74-5.48L40.2,100.45a91.57,91.57,0,0,1,6.23-15L69,82.89a8,8,0,0,0,5.1-2.64,74.11,74.11,0,0,1,6.14-6.14A8,8,0,0,0,82.89,69L85.4,46.43a91.32,91.32,0,0,1,15-6.23l17.74,14.19a8,8,0,0,0,5.48,1.74,73.93,73.93,0,0,1,8.68,0,8,8,0,0,0,5.48-1.74L155.55,40.2a91.57,91.57,0,0,1,15,6.23L173.11,69a8,8,0,0,0,2.64,5.1,74.11,74.11,0,0,1,6.14,6.14,8,8,0,0,0,5.1,2.64l22.58,2.51a91.32,91.32,0,0,1,6.23,15l-14.19,17.74A8,8,0,0,0,199.87,123.66Z","circleHalf":"M128,24A104,104,0,1,0,232,128,104.11,104.11,0,0,0,128,24Zm8,16.37a86.4,86.4,0,0,1,16,3V212.67a86.4,86.4,0,0,1-16,3Zm32,9.26a87.81,87.81,0,0,1,16,10.54V195.83a87.81,87.81,0,0,1-16,10.54ZM40,128a88.11,88.11,0,0,1,80-87.63V215.63A88.11,88.11,0,0,1,40,128Zm160,50.54V77.46a87.82,87.82,0,0,1,0,101.08Z","sun":"M120,40V16a8,8,0,0,1,16,0V40a8,8,0,0,1-16,0Zm72,88a64,64,0,1,1-64-64A64.07,64.07,0,0,1,192,128Zm-16,0a48,48,0,1,0-48,48A48.05,48.05,0,0,0,176,128ZM58.34,69.66A8,8,0,0,0,69.66,58.34l-16-16A8,8,0,0,0,42.34,53.66Zm0,116.68-16,16a8,8,0,0,0,11.32,11.32l16-16a8,8,0,0,0-11.32-11.32ZM192,72a8,8,0,0,0,5.66-2.34l16-16a8,8,0,0,0-11.32-11.32l-16,16A8,8,0,0,0,192,72Zm5.66,114.34a8,8,0,0,0-11.32,11.32l16,16a8,8,0,0,0,11.32-11.32ZM48,128a8,8,0,0,0-8-8H16a8,8,0,0,0,0,16H40A8,8,0,0,0,48,128Zm80,80a8,8,0,0,0-8,8v24a8,8,0,0,0,16,0V216A8,8,0,0,0,128,208Zm112-88H216a8,8,0,0,0,0,16h24a8,8,0,0,0,0-16Z","moon":"M233.54,142.23a8,8,0,0,0-8-2,88.08,88.08,0,0,1-109.8-109.8,8,8,0,0,0-10-10,104.84,104.84,0,0,0-52.91,37A104,104,0,0,0,136,224a103.09,103.09,0,0,0,62.52-20.88,104.84,104.84,0,0,0,37-52.91A8,8,0,0,0,233.54,142.23ZM188.9,190.34A88,88,0,0,1,65.66,67.11a89,89,0,0,1,31.4-26A106,106,0,0,0,96,56,104.11,104.11,0,0,0,200,160a106,106,0,0,0,14.92-1.06A89,89,0,0,1,188.9,190.34Z","usersThree":"M244.8,150.4a8,8,0,0,1-11.2-1.6A51.6,51.6,0,0,0,192,128a8,8,0,0,1-7.37-4.89,8,8,0,0,1,0-6.22A8,8,0,0,1,192,112a24,24,0,1,0-23.24-30,8,8,0,1,1-15.5-4A40,40,0,1,1,219,117.51a67.94,67.94,0,0,1,27.43,21.68A8,8,0,0,1,244.8,150.4ZM190.92,212a8,8,0,1,1-13.84,8,57,57,0,0,0-98.16,0,8,8,0,1,1-13.84-8,72.06,72.06,0,0,1,33.74-29.92,48,48,0,1,1,58.36,0A72.06,72.06,0,0,1,190.92,212ZM128,176a32,32,0,1,0-32-32A32,32,0,0,0,128,176ZM72,120a8,8,0,0,0-8-8A24,24,0,1,1,87.24,82a8,8,0,1,0,15.5-4A40,40,0,1,0,37,117.51,67.94,67.94,0,0,0,9.6,139.19a8,8,0,1,0,12.8,9.61A51.6,51.6,0,0,1,64,128,8,8,0,0,0,72,120Z","paperPlane":"M231.87,114l-168-95.89A16,16,0,0,0,40.92,37.34L71.55,128,40.92,218.67A16,16,0,0,0,56,240a16.15,16.15,0,0,0,7.93-2.1l167.92-96.05a16,16,0,0,0,.05-27.89ZM56,224a.56.56,0,0,0,0-.12L85.74,136H144a8,8,0,0,0,0-16H85.74L56.06,32.16A.46.46,0,0,0,56,32l168,95.83Z","person":"M230.93,220a8,8,0,0,1-6.93,4H32a8,8,0,0,1-6.92-12c15.23-26.33,38.7-45.21,66.09-54.16a72,72,0,1,1,73.66,0c27.39,8.95,50.86,27.83,66.09,54.16A8,8,0,0,1,230.93,220Z","gearSix":"M128,80a48,48,0,1,0,48,48A48.05,48.05,0,0,0,128,80Zm0,80a32,32,0,1,1,32-32A32,32,0,0,1,128,160Zm109.94-52.79a8,8,0,0,0-3.89-5.4l-29.83-17-.12-33.62a8,8,0,0,0-2.83-6.08,111.91,111.91,0,0,0-36.72-20.67,8,8,0,0,0-6.46.59L128,41.85,97.88,25a8,8,0,0,0-6.47-.6A112.1,112.1,0,0,0,54.73,45.15a8,8,0,0,0-2.83,6.07l-.15,33.65-29.83,17a8,8,0,0,0-3.89,5.4,106.47,106.47,0,0,0,0,41.56,8,8,0,0,0,3.89,5.4l29.83,17,.12,33.62a8,8,0,0,0,2.83,6.08,111.91,111.91,0,0,0,36.72,20.67,8,8,0,0,0,6.46-.59L128,214.15,158.12,231a7.91,7.91,0,0,0,3.9,1,8.09,8.09,0,0,0,2.57-.42,112.1,112.1,0,0,0,36.68-20.73,8,8,0,0,0,2.83-6.07l.15-33.65,29.83-17a8,8,0,0,0,3.89-5.4A106.47,106.47,0,0,0,237.94,107.21Zm-15,34.91-28.57,16.25a8,8,0,0,0-3,3c-.58,1-1.19,2.06-1.81,3.06a7.94,7.94,0,0,0-1.22,4.21l-.15,32.25a95.89,95.89,0,0,1-25.37,14.3L134,199.13a8,8,0,0,0-3.91-1h-.19c-1.21,0-2.43,0-3.64,0a8.08,8.08,0,0,0-4.1,1l-28.84,16.1A96,96,0,0,1,67.88,201l-.11-32.2a8,8,0,0,0-1.22-4.22c-.62-1-1.23-2-1.8-3.06a8.09,8.09,0,0,0-3-3.06l-28.6-16.29a90.49,90.49,0,0,1,0-28.26L61.67,97.63a8,8,0,0,0,3-3c.58-1,1.19-2.06,1.81-3.06a7.94,7.94,0,0,0,1.22-4.21l.15-32.25a95.89,95.89,0,0,1,25.37-14.3L122,56.87a8,8,0,0,0,4.1,1c1.21,0,2.43,0,3.64,0a8.08,8.08,0,0,0,4.1-1l28.84-16.1A96,96,0,0,1,188.12,55l.11,32.2a8,8,0,0,0,1.22,4.22c.62,1,1.23,2,1.8,3.06a8.09,8.09,0,0,0,3,3.06l28.6,16.29A90.49,90.49,0,0,1,222.9,142.12Z","copy":"M216,32H88a8,8,0,0,0-8,8V80H40a8,8,0,0,0-8,8V216a8,8,0,0,0,8,8H168a8,8,0,0,0,8-8V176h40a8,8,0,0,0,8-8V40A8,8,0,0,0,216,32ZM160,208H48V96H160Zm48-48H176V88a8,8,0,0,0-8-8H96V48H208Z","broadcast":"M128,88a40,40,0,1,0,40,40A40,40,0,0,0,128,88Zm0,64a24,24,0,1,1,24-24A24,24,0,0,1,128,152Zm73.71,7.14a80,80,0,0,1-14.08,22.2,8,8,0,0,1-11.92-10.67,63.95,63.95,0,0,0,0-85.33,8,8,0,1,1,11.92-10.67,80.08,80.08,0,0,1,14.08,84.47ZM69,103.09a64,64,0,0,0,11.26,67.58,8,8,0,0,1-11.92,10.67,79.93,79.93,0,0,1,0-106.67A8,8,0,1,1,80.29,85.34,63.77,63.77,0,0,0,69,103.09ZM248,128a119.58,119.58,0,0,1-34.29,84,8,8,0,1,1-11.42-11.2,103.9,103.9,0,0,0,0-145.56A8,8,0,1,1,213.71,44,119.58,119.58,0,0,1,248,128ZM53.71,200.78A8,8,0,1,1,42.29,212a119.87,119.87,0,0,1,0-168,8,8,0,1,1,11.42,11.2,103.9,103.9,0,0,0,0,145.56Z","key":"M216.57,39.43A80,80,0,0,0,83.91,120.78L28.69,176A15.86,15.86,0,0,0,24,187.31V216a16,16,0,0,0,16,16H72a8,8,0,0,0,8-8V208H96a8,8,0,0,0,8-8V184h16a8,8,0,0,0,5.66-2.34l9.56-9.57A79.73,79.73,0,0,0,160,176h.1A80,80,0,0,0,216.57,39.43ZM224,98.1c-1.09,34.09-29.75,61.86-63.89,61.9H160a63.7,63.7,0,0,1-23.65-4.51,8,8,0,0,0-8.84,1.68L116.69,168H96a8,8,0,0,0-8,8v16H72a8,8,0,0,0-8,8v16H40V187.31l58.83-58.82a8,8,0,0,0,1.68-8.84A63.72,63.72,0,0,1,96,95.92c0-34.14,27.81-62.8,61.9-63.89A64,64,0,0,1,224,98.1ZM192,76a12,12,0,1,1-12-12A12,12,0,0,1,192,76Z","arrowClockwise":"M240,56v48a8,8,0,0,1-8,8H184a8,8,0,0,1,0-16H211.4L184.81,71.64l-.25-.24a80,80,0,1,0-1.67,114.78,8,8,0,0,1,11,11.63A95.44,95.44,0,0,1,128,224h-1.32A96,96,0,1,1,195.75,60L224,85.8V56a8,8,0,1,1,16,0Z","arrowLeft":"M224,128a8,8,0,0,1-8,8H59.31l58.35,58.34a8,8,0,0,1-11.32,11.32l-72-72a8,8,0,0,1,0-11.32l72-72a8,8,0,0,1,11.32,11.32L59.31,120H216A8,8,0,0,1,224,128Z","at":"M128,24a104,104,0,0,0,0,208c21.51,0,44.1-6.48,60.43-17.33a8,8,0,0,0-8.86-13.33C166,210.38,146.21,216,128,216a88,88,0,1,1,88-88c0,26.45-10.88,32-20,32s-20-5.55-20-32V88a8,8,0,0,0-16,0v4.26a48,48,0,1,0,5.93,65.1c6,12,16.35,18.64,30.07,18.64,22.54,0,36-17.94,36-48A104.11,104.11,0,0,0,128,24Zm0,136a32,32,0,1,1,32-32A32,32,0,0,1,128,160Z","check":"M232.49,80.49l-128,128a12,12,0,0,1-17,0l-56-56a12,12,0,1,1,17-17L96,183,215.51,63.51a12,12,0,0,1,17,17Z"};

  /* Vendor marks from simple-icons (CC0), on a 0 0 24 24 grid, plus the
     signature colour each mark and agent name renders in. */
  var LOGOS = {"anthropic":{"path":"M17.3041 3.541h-3.6718l6.696 16.918H24Zm-10.6082 0L0 20.459h3.7442l1.3693-3.5527h7.0052l1.3693 3.5528h3.7442L10.5363 3.5409Zm-.3712 10.2232 2.2914-5.9456 2.2914 5.9456Z","color":"#D97757"},"openai":{"path":"M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z","color":"var(--text)"},"qwen":{"path":"M23.919 14.545 20.817 9.17l1.47-2.544a.56.56 0 0 0 0-.566l-1.633-2.83a.57.57 0 0 0-.49-.283h-6.207L12.487.402a.57.57 0 0 0-.49-.284H8.732a.56.56 0 0 0-.49.284L5.139 5.775h-2.94a.56.56 0 0 0-.49.284L.077 8.887a.56.56 0 0 0 0 .567L3.18 14.83l-1.47 2.545a.56.56 0 0 0 0 .566l1.634 2.83a.57.57 0 0 0 .49.283h6.205l1.47 2.545a.57.57 0 0 0 .49.284h3.266a.57.57 0 0 0 .49-.284l3.104-5.375h2.94a.57.57 0 0 0 .49-.283l1.634-2.828a.55.55 0 0 0-.004-.568M8.733.686l1.634 2.828-1.634 2.828H21.8L20.164 9.17H7.425L5.63 6.06Zm1.306 19.801-6.205-.002 1.634-2.83h3.265L2.201 6.344h3.267q3.182 5.517 6.367 11.032zm10.124-5.66L18.53 12l-6.532 11.315-1.634-2.83c2.129-3.673 4.25-7.351 6.373-11.028h3.592l3.102 5.374z","color":"#6950EF"},"gemini":{"path":"M11.04 19.32Q12 21.51 12 24q0-2.49.93-4.68.96-2.19 2.58-3.81t3.81-2.55Q21.51 12 24 12q-2.49 0-4.68-.93a12.3 12.3 0 0 1-3.81-2.58 12.3 12.3 0 0 1-2.58-3.81Q12 2.49 12 0q0 2.49-.96 4.68-.93 2.19-2.55 3.81a12.3 12.3 0 0 1-3.81 2.58Q2.49 12 0 12q2.49 0 4.68.96 2.19.93 3.81 2.55t2.55 3.81","color":"#4285F4"},"cursor":{"path":"M11.503.131 1.891 5.678a.84.84 0 0 0-.42.726v11.188c0 .3.162.575.42.724l9.609 5.55a1 1 0 0 0 .998 0l9.61-5.55a.84.84 0 0 0 .42-.724V6.404a.84.84 0 0 0-.42-.726L12.497.131a1.01 1.01 0 0 0-.996 0M2.657 6.338h18.55c.263 0 .43.287.297.515L12.23 22.918c-.062.107-.229.064-.229-.06V12.335a.59.59 0 0 0-.295-.51l-9.11-5.257c-.109-.063-.064-.23.061-.23","color":"#6B7A90"},"opencode":{"path":"M22 24H2V0h20zM17 4.8H7v14.4h10z","color":"#E8A33D"}};

  var LOGO_RULES = [
    ["anthropic", /claude|anthropic/i],
    ["openai", /codex|gpt|openai/i],
    ["qwen", /qwen/i],
    ["gemini", /gemini/i],
    ["cursor", /cursor/i],
    ["opencode", /opencode/i]
  ];
  var PERSON_RE = /operator|human|\byou\b/i;

  var TOKEN_KEY = "cc_admin";
  var THEME_KEY = "cc_theme";
  var POLL_MS = 3000;
  var FADE_MS = 8000;
  var BOTTOM_SLOP_PX = 32;
  var EXPIRY_OPTIONS = [
    ["never", "never"], ["10m", "10 minutes"], ["30m", "30 minutes"],
    ["60m", "60 minutes"], ["1d", "1 day"], ["1w", "1 week"], ["1mo", "1 month"]
  ];

  /* ---------------------------------------------------------------- state */
  var S = {
    token: localStorage.getItem(TOKEN_KEY) || "",
    data: null,               /* last /admin/state payload */
    conn: "idle",             /* idle | live | error */
    view: { kind: "room", room: "", agent: null },
    agents: [],               /* reconciled presence */
    now: Date.now(),
    stick: true,              /* timeline pinned to bottom */
    recentOpen: false,
    navOpen: false,
    drawerOpen: false,
    menuOpen: false,
    editingAs: false,
    sendAs: "operator",
    to: "all",
    expects: null,
    sendError: null,
    baseline: { now: Date.now(), key: "" },
    firstSeen: {},            /* "room#seq" -> ms, for the expects timer */
    copied: {},               /* transient "copied!" flags */
    confirmKill: {},
    mint: { result: null, error: null, pending: false },
    regen: { armed: false, result: null, error: null, pending: false }
  };

  /* ----------------------------------------------------------- dom helpers */
  function E(tag, cls, attrs) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (attrs) {
      for (var k in attrs) {
        if (!Object.prototype.hasOwnProperty.call(attrs, k)) { continue; }
        var v = attrs[k];
        if (v === null || v === false || v === undefined) { continue; }
        if (k === "text") { e.textContent = v; }
        else if (k.slice(0, 2) === "on") { e.addEventListener(k.slice(2), v); }
        else if (k.slice(0, 2) === "--") { e.style.setProperty(k, v); }
        else { e.setAttribute(k, v === true ? "" : v); }
      }
    }
    for (var i = 3; i < arguments.length; i++) {
      var c = arguments[i];
      if (c === null || c === undefined || c === false) { continue; }
      e.appendChild(typeof c === "object" ? c : document.createTextNode(String(c)));
    }
    return e;
  }
  function frag() {
    var f = document.createDocumentFragment();
    for (var i = 0; i < arguments.length; i++) {
      if (arguments[i]) { f.appendChild(arguments[i]); }
    }
    return f;
  }
  var NS = "http://www.w3.org/2000/svg";
  /* `d` is always one of our own constants — never user data. */
  function icon(name, size, cls, weightFill) {
    var d = ICON[name];
    if (!d) { return document.createTextNode(""); }
    var s = document.createElementNS(NS, "svg");
    s.setAttribute("xmlns", NS);
    s.setAttribute("viewBox", "0 0 256 256");
    s.setAttribute("width", size || 16);
    s.setAttribute("height", size || 16);
    s.setAttribute("fill", weightFill || "currentColor");
    s.setAttribute("aria-hidden", "true");
    if (cls) { s.setAttribute("class", cls); }
    d.split("§").forEach(function (seg) {
      var p = document.createElementNS(NS, "path");
      p.setAttribute("d", seg);
      s.appendChild(p);
    });
    return s;
  }
  function vendorSvg(pathData) {
    var s = document.createElementNS(NS, "svg");
    s.setAttribute("viewBox", "0 0 24 24");
    s.setAttribute("aria-hidden", "true");
    s.setAttribute("class", "agent-logo");
    var p = document.createElementNS(NS, "path");
    p.setAttribute("d", pathData);
    p.setAttribute("fill", "var(--agent)");
    s.appendChild(p);
    return s;
  }

  /* -------------------------------------------------------------- presence */
  function hueFor(name) {
    var hash = 0;
    for (var i = 0; i < name.length; i++) {
      hash = (hash * 31 + name.charCodeAt(i)) % 2147483648;
    }
    return hash % 360;
  }
  function glyphFor(name) {
    for (var i = 0; i < LOGO_RULES.length; i++) {
      if (LOGO_RULES[i][1].test(name)) {
        var l = LOGOS[LOGO_RULES[i][0]];
        return { kind: "brand", path: l.path, color: l.color };
      }
    }
    if (PERSON_RE.test(name)) { return { kind: "person" }; }
    return null;
  }
  function brandAccent(name) {
    var g = glyphFor(name);
    return g && g.kind === "brand" ? g.color : null;
  }
  function lastSeen(sec) {
    if (sec < 1) { return "now"; }
    if (sec < 60) { return Math.floor(sec) + "s"; }
    if (sec < 3600) { return Math.floor(sec / 60) + "m"; }
    return Math.floor(sec / 3600) + "h";
  }
  function elapsedSince(ms, now) {
    var total = Math.max(0, Math.floor((now - ms) / 1000));
    return Math.floor(total / 60) + ":" + String(total % 60).padStart(2, "0");
  }
  function reconcile(data) {
    var prev = {};
    S.agents.forEach(function (a) { prev[a.room + "/" + a.name] = a; });
    var out = [];
    Object.keys(data.peers || {}).forEach(function (room) {
      (data.peers[room] || []).forEach(function (p) {
        var was = prev[room + "/" + p.name];
        var life;
        if (p.online) { life = "online"; }
        else { life = p.seconds_since_seen * 1000 >= FADE_MS ? "offline" : "fading"; }
        out.push({
          name: p.name, room: room, online: p.online, life: life,
          secondsSinceSeen: p.seconds_since_seen, hue: hueFor(p.name),
          justJoined: p.online && !(was && was.online)
        });
      });
    });
    return out;
  }
  /* One row per agent name, keeping the liveliest sighting across rooms. */
  function dedupe(views) {
    var rank = { offline: 0, fading: 1, online: 2 };
    var by = {};
    views.forEach(function (v) {
      var ex = by[v.name];
      if (!ex) { by[v.name] = Object.assign({}, v); return; }
      var better = rank[v.life] > rank[ex.life] ||
        (rank[v.life] === rank[ex.life] && v.secondsSinceSeen < ex.secondsSinceSeen);
      by[v.name] = {
        name: ex.name, room: ex.room, hue: ex.hue,
        online: ex.online || v.online,
        justJoined: ex.justJoined || v.justJoined,
        life: better ? v.life : ex.life,
        secondsSinceSeen: better ? v.secondsSinceSeen : ex.secondsSinceSeen
      };
    });
    return Object.keys(by).map(function (k) { return by[k]; });
  }
  function roomList() {
    if (!S.data) { return []; }
    var set = {};
    Object.keys(S.data.peers || {}).forEach(function (r) { set[r] = 1; });
    (S.data.codes || []).forEach(function (c) { set[c.room] = 1; });
    return Object.keys(set).sort(function (a, b) { return a.localeCompare(b); });
  }
  function messagesFor() {
    if (!S.data) { return []; }
    var all = (S.data.messages || []).filter(function (m) { return m.room === S.view.room; });
    if (S.view.kind === "dm" && S.view.agent) {
      var who = S.view.agent;
      all = all.filter(function (m) { return m.from === who || m.to === who; });
    }
    return all;
  }
  function msgKey(m) { return m.room + "#" + m.seq; }
  function expectsSince(m) {
    var k = msgKey(m);
    if (!S.firstSeen[k]) { S.firstSeen[k] = Date.now(); }
    return S.firstSeen[k];
  }

  /* ---------------------------------------------------------------- avatar */
  function avatar(name, size, dot) {
    var g = glyphFor(name);
    var brand = g && g.kind === "brand" ? g.color : null;
    var isOp = name === "operator";
    var span;
    if (size === "row") {
      span = E("span", "sb-av " + (brand ? "is-brand" : (isOp ? "hop" : "h" + (hueFor(name) % 5))));
    } else {
      var cls = ["conv-avatar"];
      if (size === "sm") { cls.push("conv-avatar--sm"); }
      if (size === "round" || isOp) { cls.push("conv-avatar--round"); }
      cls.push(brand ? "is-brand" : (isOp ? "hue-op" : "hue-" + (hueFor(name) % 5)));
      span = E("span", cls.join(" "));
    }
    if (brand) { span.style.setProperty("--agent", brand); }
    if (!g) { span.appendChild(document.createTextNode(name.slice(0, 2).toUpperCase())); }
    else if (g.kind === "person") { span.appendChild(icon("person", 14, "agent-logo agent-logo--person")); }
    else { span.appendChild(vendorSvg(g.path)); }
    if (dot) {
      var on = dot === "on";
      span.appendChild(size === "row"
        ? E("span", on ? "sb-pdot" : "sb-pdot off")
        : E("span", on ? "conv-avatar__dot" : "conv-avatar__dot conv-avatar__dot--off"));
    }
    return span;
  }

  /* ---------------------------------------------------------------- badges */
  function claimedBadge(by) {
    return E("span", "badge-pill badge-pill--claimed",
      { "data-badge": "claimed", title: 'claimed_by: "' + by + '"' },
      icon("check", 10, "ph"), " claimed · " + by);
  }
  function expectsBadge(m) {
    var label = m.expects_reply;
    return E("span", "badge-pill badge-pill--expects",
      { "data-badge": "expects", title: 'expects_reply: "' + label + '" · unclaimed' },
      "expects · " + label,
      E("span", "badge-pill__timer mono", { text: elapsedSince(expectsSince(m), S.now) }));
  }
  function turnChip(m) {
    if (!m) { return null; }
    return m.claimed_by ? claimedBadge(m.claimed_by) : expectsBadge(m);
  }
  function latestTurn() {
    if (!S.data) { return null; }
    var all = S.data.messages || [];
    for (var i = all.length - 1; i >= 0; i--) {
      var m = all[i];
      if (m.room !== S.view.room) { continue; }
      if (!m.expects_reply || m.expects_reply === "none") { continue; }
      return m;
    }
    return null;
  }

  /* --------------------------------------------------------------- sidebar */
  function renderSidebar() {
    var nav = document.getElementById("sbNav");
    if (!nav) { return; }
    var roster = dedupe(S.agents);
    var key = roster.map(function (r) { return r.name + ":" + r.secondsSinceSeen + ":" + r.life; }).join("|");
    if (key !== S.baseline.key) { S.baseline = { now: S.now, key: key }; }
    var drift = Math.max(0, (S.now - S.baseline.now) / 1000);
    var shown = function (a) { return a.life === "online" ? 0 : a.secondsSinceSeen + drift; };

    var visible = roster.filter(function (r) { return r.life !== "offline"; })
      .sort(function (a, b) {
        var ra = a.life === "online" ? 0 : 1, rb = b.life === "online" ? 0 : 1;
        return ra - rb || a.name.localeCompare(b.name);
      });
    var offline = roster.filter(function (r) { return r.life === "offline"; })
      .sort(function (a, b) { return a.secondsSinceSeen - b.secondsSinceSeen; });
    var onlineCount = roster.filter(function (r) { return r.life === "online"; }).length;

    var out = document.createDocumentFragment();
    out.appendChild(E("div", "sb-label", null, "Rooms"));
    var rl = E("div", null, { "data-testid": "room-list" });
    roomList().forEach(function (r) {
      var active = S.view.kind === "room" && S.view.room === r;
      rl.appendChild(E("button", active ? "sb-room active" : "sb-room",
        { type: "button", "data-room": r, "aria-label": "Room " + r, "aria-current": active ? "true" : null },
        icon("hash", 14, "sb-ph"), E("span", null, { text: r })));
    });
    out.appendChild(rl);

    out.appendChild(E("div", "sb-label", null, "Agents ",
      E("span", "sb-n", { text: "· " + onlineCount })));
    var al = E("div", null, { "data-testid": "agent-list" });
    visible.forEach(function (a) { al.appendChild(agentRow(a, shown(a), false)); });
    out.appendChild(al);

    if (offline.length) {
      out.appendChild(E("button", S.recentOpen ? "sb-recent-head open" : "sb-recent-head",
        { type: "button", id: "recentToggle", "aria-expanded": S.recentOpen ? "true" : "false" },
        icon("caretRight", 12, "sb-ph"), " Recently offline · " + offline.length));
      if (S.recentOpen) {
        var ol = E("div", null, { "data-testid": "recent-offline-list" });
        offline.forEach(function (a) { ol.appendChild(agentRow(a, shown(a), true)); });
        out.appendChild(ol);
      }
    }
    nav.textContent = "";
    nav.appendChild(out);

    var dot = document.getElementById("connDot");
    if (dot) {
      dot.className = "sb-conn " + S.conn;
      dot.setAttribute("title", S.conn === "live"
        ? "relay reachable — /admin/state answering" : "connection: " + S.conn);
    }
  }
  function agentRow(a, seconds, recent) {
    var cls = [recent ? "sb-arow sb-recent-row" : "sb-arow"];
    if (!recent && a.life === "fading") { cls.push("fading"); }
    if (!recent && a.justJoined) { cls.push("join-pulse"); }
    if (S.view.kind === "dm" && S.view.agent === a.name) { cls.push("active"); }
    var b = E("button", cls.join(" "), {
      type: "button", "data-agent": a.name,
      "aria-label": a.name + " — " + (a.life === "online" ? "online" : lastSeen(seconds) + " ago") + ", open direct view"
    });
    b.style.setProperty("--hue", a.hue);
    b.appendChild(avatar(a.name, "row", a.life === "online" ? "on" : "off"));
    var brand = brandAccent(a.name);
    var nm = E("span", brand ? "sb-aname is-brand sb-aname--brand" : "sb-aname", { text: a.name });
    if (brand) { nm.style.setProperty("--agent", brand); }
    b.appendChild(nm);
    b.appendChild(E("span", "sb-alast mono",
      { "data-testid": "last-seen", text: a.life === "online" ? "online" : lastSeen(seconds) + " ago" }));
    return b;
  }

  /* ---------------------------------------------------------------- header */
  function renderHeader() {
    var h = document.getElementById("convHeader");
    if (!h) { return; }
    h.textContent = "";
    if (S.view.kind === "dm" && S.view.agent) {
      var who = S.view.agent;
      var peer = S.agents.filter(function (a) { return a.name === who && a.room === S.view.room; })[0] ||
                 S.agents.filter(function (a) { return a.name === who; })[0];
      var on = peer ? peer.online : false;
      var secs = peer ? peer.secondsSinceSeen : 0;
      h.appendChild(E("button", "conv-header__back",
        { type: "button", id: "backToRoom", "aria-label": "Back to room", title: "Back to #" + S.view.room },
        icon("arrowLeft", 16, "ph")));
      h.appendChild(avatar(who, "round-sm-dot" === "" ? "sm" : "sm", on ? "on" : "off"));
      h.appendChild(E("span", "conv-header__name", { "data-testid": "channel-title", text: who }));
      h.appendChild(E("span", "conv-header__meta mono",
        { text: on ? "online · " + lastSeen(secs) : "offline · " + lastSeen(secs) + " ago" }));
      h.appendChild(E("span", "conv-header__filterchip",
        { title: "Direct view = client-side filter over room messages" },
        icon("at", 11, "ph"), " filtered · #" + S.view.room));
      return;
    }
    var present = S.agents.filter(function (a) { return a.online && a.room === S.view.room; }).length;
    h.appendChild(icon("hash", 16, "ph conv-header__hash"));
    h.appendChild(E("span", "conv-header__name", { "data-testid": "channel-title", text: S.view.room }));
    h.appendChild(E("span", "conv-header__sep"));
    h.appendChild(E("span", "conv-header__meta", null,
      icon("usersThree", 13, "ph"), E("span", null, { text: String(present) }),
      E("span", "conv-header__plabel", null, " present")));
    var chip = turnChip(latestTurn());
    if (chip) { h.appendChild(chip); }
  }

  /* -------------------------------------------------------------- timeline */
  function renderTimeline() {
    var tl = document.getElementById("timeline");
    if (!tl) { return; }
    var msgs = messagesFor();
    tl.textContent = "";
    if (!msgs.length) {
      tl.appendChild(E("div", "conv-empty", null,
        icon("hash", 36, "ph"),
        E("div", "conv-empty__t1", { text: "Nothing in #" + S.view.room + " yet" }),
        E("div", "conv-empty__t2", null, "Messages agents send here will show up live.")));
      return;
    }
    tl.appendChild(E("div", "conv-daydiv", null, E("span", null, "today")));
    var groups = [];
    msgs.forEach(function (m) {
      var last = groups[groups.length - 1];
      if (last && last.sender === m.from) { last.messages.push(m); }
      else { groups.push({ sender: m.from, isOperator: m.from === "operator", messages: [m] }); }
    });
    groups.forEach(function (g) {
      var wrap = E("div", "conv-group" + (g.isOperator ? " conv-group--op" : ""));
      wrap.appendChild(avatar(g.sender, "lg", null));
      var body = E("div", "conv-group__body");
      var head = E("div", "conv-group__head");
      var brand = !g.isOperator && brandAccent(g.sender);
      var nm;
      if (brand) {
        nm = E("span", "conv-group__name is-brand", { text: g.sender });
        nm.style.setProperty("--agent", brand);
      } else {
        nm = E("span", "conv-group__name " + (g.isOperator ? "" : "hue-" + (hueFor(g.sender) % 5)),
          { text: g.sender });
      }
      head.appendChild(nm);
      if (g.isOperator) { head.appendChild(E("span", "conv-oppill", null, "operator")); }
      body.appendChild(head);
      g.messages.forEach(function (m) {
        var row = E("div", "conv-msg");
        var hide = S.view.kind === "dm" ? S.view.agent : undefined;
        if (m.to && m.to !== "all" && m.to !== hide) {
          row.appendChild(E("span", "conv-dir hue-" + (hueFor(m.to) % 5), { text: "→ " + m.to }));
        }
        row.appendChild(document.createTextNode(m.text));
        if (m.claimed_by) { row.appendChild(claimedBadge(m.claimed_by)); }
        else if (m.expects_reply && m.expects_reply !== "none") { row.appendChild(expectsBadge(m)); }
        body.appendChild(row);
      });
      wrap.appendChild(body);
      tl.appendChild(wrap);
    });
    if (S.stick) { tl.scrollTop = tl.scrollHeight; }
  }

  /* -------------------------------------------------------------- composer */
  function renderComposer() {
    var input = document.getElementById("composerInput");
    var dm = S.view.kind === "dm" ? S.view.agent : null;
    if (input) { input.placeholder = dm ? "Message @" + dm : "Message #" + S.view.room; }

    var asBtn = document.getElementById("asPill");
    if (asBtn && !S.editingAs) {
      asBtn.textContent = "as ";
      asBtn.appendChild(E("b", null, { text: S.sendAs }));
    }
    var toBtn = document.getElementById("toPill");
    if (toBtn) {
      toBtn.textContent = "→ " + (dm || (S.to === "all" ? "everyone" : S.to));
      toBtn.disabled = !!dm;
      toBtn.className = "conv-pill" + (dm ? " conv-pill--locked" : "") +
        (!dm && S.to !== "all" ? " conv-pill--armed" : "");
    }
    var exBtn = document.getElementById("expectsPill");
    if (exBtn) {
      /* No explicit choice yet: show what the server will actually default
         expects_reply to for the current target (see admin_say), not a dash
         that hides it. Unarmed styling still marks it as a default. */
      var exDefault = (dm || S.to) === "all" ? "none" : (dm || S.to);
      exBtn.textContent = "expects · " + (S.expects || exDefault);
      exBtn.className = "conv-pill" + (S.expects ? " conv-pill--armed" : "");
    }
    var send = document.getElementById("sendBtn");
    if (send && input) {
      send.className = "conv-send" + (input.value.trim() ? " conv-send--ready" : "");
    }
    var err = document.getElementById("composerError");
    if (err) {
      err.hidden = !S.sendError;
      err.textContent = S.sendError || "";
    }
    var menu = document.getElementById("toMenu");
    if (menu) {
      menu.hidden = !(S.menuOpen && !dm);
      if (S.menuOpen && !dm) {
        menu.textContent = "";
        menu.appendChild(E("button", "conv-menu__item", { type: "button", "data-to": "all" },
          icon("usersThree", 15, "ph"),
          E("span", "conv-menu__who", null, "everyone"),
          E("span", "conv-menu__k mono", null, "to: all")));
        S.agents.filter(function (a) {
          return a.online && a.room === S.view.room && a.name !== "operator";
        }).forEach(function (a) {
          menu.appendChild(E("button", "conv-menu__item", { type: "button", "data-to": a.name },
            avatar(a.name, "sm", null),
            E("span", "conv-menu__who", { text: a.name }),
            E("span", "conv-menu__k mono", { text: "to: " + a.name })));
        });
      }
    }
  }

  /* ---------------------------------------------------------------- drawer */
  function renderDrawer() {
    var wrap = document.getElementById("drawerWrap");
    var scrim = document.getElementById("drawerScrim");
    if (!wrap || !scrim) { return; }
    wrap.hidden = !S.drawerOpen;
    scrim.hidden = !S.drawerOpen;
    if (!S.drawerOpen) { return; }
    if (!document.getElementById("adRoot")) { buildDrawer(); }
    renderKeys();
    var u = document.getElementById("adUrl");
    if (u) { u.textContent = (S.data && S.data.public_url) || ""; }
  }
  function buildDrawer() {
    var wrap = document.getElementById("drawerWrap");
    var root = E("aside", "ad-root", { id: "adRoot", "aria-label": "Admin", "data-testid": "admin-drawer" });

    root.appendChild(E("header", "ad-head", null,
      icon("gearSix", 16), E("span", "ad-title", null, "Admin"),
      E("span", "ad-sub", null, "keys · token · relay"),
      E("button", "ad-close", { type: "button", id: "adClose", "aria-label": "Close admin drawer" }, "×")));

    var body = E("div", "ad-body");

    /* public url */
    body.appendChild(E("section", "ad-sec", null,
      E("div", "ad-label", null, icon("broadcast", 13), " Public URL"),
      E("div", "ad-urlrow", null,
        E("span", "ad-u", { id: "adUrl" }),
        E("button", "ad-icbtn", { type: "button", id: "adCopyUrl", "aria-label": "Copy public URL" }, icon("copy", 13))),
      E("p", "ad-hint", null, "Agents reach the relay here. Each key below authenticates one agent into one room.")));

    /* admin token */
    var tokenInput = E("input", "ad-field ad-grow", {
      id: "adToken", type: "password", autocomplete: "off",
      placeholder: "paste admin token", "aria-label": "Admin token", value: S.token
    });
    body.appendChild(E("section", "ad-sec", null,
      E("div", "ad-label", null, icon("key", 13), " Admin token"),
      E("div", "ad-frow", null, tokenInput,
        E("button", "ad-btn", { type: "button", id: "adSaveToken" }, "Save")),
      E("p", "ad-hint", null, "Sent as ", E("code", null, null, "X-Admin-Token"),
        " on every write. Stored only in this browser.")));

    /* mint */
    var roomSel = E("select", "ad-field", { id: "adRoom", "aria-label": "Room" });
    roomSel.style.width = "108px";
    var expSel = E("select", "ad-field", { id: "adExpiry", "aria-label": "Expiry" });
    expSel.style.width = "120px";
    EXPIRY_OPTIONS.forEach(function (o) {
      expSel.appendChild(E("option", null, { value: o[0], text: o[1] }));
    });
    body.appendChild(E("section", "ad-sec", null,
      E("h2", "ad-label", null, icon("key", 13), " Mint a key"),
      E("div", "ad-frow", null,
        E("input", "ad-field ad-grow", { id: "adName", autocomplete: "off", placeholder: "agent name", "aria-label": "Agent name" }),
        roomSel),
      E("div", "ad-frow", null, expSel,
        E("input", "ad-field ad-grow", { id: "adCap", autocomplete: "off", placeholder: "capabilities (optional)", "aria-label": "Capabilities" })),
      E("div", null, { style: "display:flex;justify-content:flex-end" },
        E("button", "ad-btn primary", { type: "button", id: "adMint" }, "Mint key")),
      E("div", null, { id: "adMintOut" })));

    /* keys */
    body.appendChild(E("section", "ad-sec", { "aria-label": "Access keys", "data-testid": "admin-keys" },
      E("h2", "ad-label", null, icon("usersThree", 13), " Access keys ",
        E("span", "mono", { id: "adKeyCount" })),
      E("div", null, { id: "adKeys" })));

    /* danger */
    body.appendChild(E("section", "ad-sec", null,
      E("div", "ad-label danger", null, "Danger"),
      E("button", "ad-btn danger", { type: "button", id: "adRegen" },
        icon("arrowClockwise", 13), " Regenerate admin token"),
      E("p", "ad-hint", null,
        "Invalidates the current token for every dashboard session. Agent keys keep working."),
      E("div", null, { id: "adRegenOut" })));

    root.appendChild(body);
    wrap.textContent = "";
    wrap.appendChild(root);
    syncRoomSelect();
  }
  function syncRoomSelect() {
    var sel = document.getElementById("adRoom");
    if (!sel) { return; }
    var want = sel.value;
    var rooms = roomList();
    if (!rooms.length) { rooms = ["default"]; }
    sel.textContent = "";
    rooms.forEach(function (r) { sel.appendChild(E("option", null, { value: r, text: "#" + r })); });
    if (want && rooms.indexOf(want) >= 0) { sel.value = want; }
  }
  function renderKeys() {
    var box = document.getElementById("adKeys");
    if (!box) { return; }
    syncRoomSelect();
    var codes = (S.data && S.data.codes) || [];
    var hash = !!(S.data && S.data.hash_codes);
    var cnt = document.getElementById("adKeyCount");
    if (cnt) { cnt.textContent = "· " + codes.length; }
    box.textContent = "";
    if (!codes.length) {
      box.appendChild(E("p", "ad-hint", null, "No keys minted yet."));
      return;
    }
    codes.forEach(function (c) {
      var online = S.agents.some(function (a) { return a.name === c.name && a.online; });
      var row = E("div", "ad-krow");
      var line = E("div", "ad-kline", null,
        E("span", "ad-kdot" + (online ? " on" : "")),
        E("span", "ad-kname", { text: c.name }),
        E("span", "ad-kmeta", { text: "#" + (c.room || "default") + " · " + (c.expires || "never") }));
      var acts = E("span", "ad-kacts");
      if (!hash) {
        acts.appendChild(E("button", "ad-icbtn" + (S.copied["k" + c.name] ? " ok" : ""),
          { type: "button", "data-copykey": c.code, "aria-label": "Copy key for " + c.name },
          icon(S.copied["k" + c.name] ? "check" : "copy", 13)));
      }
      acts.appendChild(E("button", "ad-kkill" + (S.confirmKill[c.name] ? " confirm" : ""),
        { type: "button", "data-revoke": c.name },
        S.confirmKill[c.name] ? "Sure?" : "Revoke"));
      line.appendChild(acts);
      row.appendChild(line);
      if (!hash) { row.appendChild(E("div", "ad-kcode", { text: c.code })); }
      if (c.capabilities) { row.appendChild(E("div", "ad-kcap", { text: c.capabilities })); }
      box.appendChild(row);
    });
  }

  /* ------------------------------------------------------------------- net */
  function api(path, body) {
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Admin-Token": S.token },
      body: JSON.stringify(body)
    }).then(function (r) {
      if (!r.ok) { throw new Error(path + " failed: " + r.status); }
      return r.json();
    });
  }
  function poll() {
    return fetch("/admin/state", { headers: { "X-Admin-Token": S.token } })
      .then(function (r) {
        if (!r.ok) { S.conn = "error"; renderAll(); return; }
        return r.json().then(function (j) {
          S.data = j;
          S.agents = reconcile(j);
          S.conn = "live";
          var rooms = roomList();
          if (rooms.length && S.view.kind === "room" && rooms.indexOf(S.view.room) < 0) {
            S.view = { kind: "room", room: rooms[0], agent: null };
          }
          renderAll();
        });
      })
      .catch(function () { S.conn = "error"; renderAll(); });
  }

  /* ---------------------------------------------------------------- render */
  function renderAll() {
    renderSidebar();
    renderHeader();
    renderTimeline();
    renderComposer();
    renderDrawer();
    var navWrap = document.getElementById("navWrap");
    var navScrim = document.getElementById("navScrim");
    if (navWrap) {
      navWrap.className = "fixed inset-y-0 left-0 z-30 w-[min(82vw,300px)] transform " +
        "border-[var(--border-strong)] border-r transition-transform duration-200 ease-in-out " +
        "sm:static sm:z-auto sm:w-64 sm:shrink-0 sm:translate-x-0 sm:border-[var(--border)] sm:border-r " +
        (S.navOpen ? "translate-x-0" : "-translate-x-full sm:translate-x-0");
    }
    if (navScrim) { navScrim.hidden = !S.navOpen; }
  }
  /* Cheap 1s tick: only the live timers/last-seen need it. */
  function tick() {
    S.now = Date.now();
    renderSidebar();
    renderHeader();
    var stamps = document.querySelectorAll(".badge-pill__timer");
    if (stamps.length) { renderTimeline(); }
  }

  /* ----------------------------------------------------------------- theme */
  function applyTheme(t) {
    localStorage.setItem(THEME_KEY, t);
    document.documentElement.setAttribute("data-theme", t);
    ["auto", "light", "dark"].forEach(function (o) {
      var b = document.getElementById("theme-" + o);
      if (b) { b.className = o === t ? "on" : ""; }
    });
  }

  /* ---------------------------------------------------------------- shell */
  function shell() {
    var app = document.getElementById("app");
    var root = E("div", "flex h-dvh min-h-0 w-full overflow-hidden bg-[var(--bg)] text-[var(--text)]");

    root.appendChild(E("button", "fixed inset-0 z-30 bg-[var(--scrim)] sm:hidden",
      { id: "navScrim", type: "button", "aria-label": "Close navigation", hidden: true }));

    var navWrap = E("div", "", { id: "navWrap" });
    var aside = E("aside", "sb-root", { "aria-label": "Workspace", "data-testid": "sidebar" });
    aside.appendChild(E("div", "sb-head", null,
      E("span", "sb-wsname", null, "argybargy"),
      E("span", "sb-conn idle", { id: "connDot", role: "status" }),
      E("span", "sb-wsurl mono", null, "mesh")));
    aside.appendChild(E("nav", "sb-nav", { id: "sbNav", "aria-label": "Rooms and agents" }));
    var seg = E("fieldset", "sb-seg", { "aria-label": "Theme" });
    [["auto", "circleHalf"], ["light", "sun"], ["dark", "moon"]].forEach(function (p) {
      seg.appendChild(E("button", "", {
        type: "button", id: "theme-" + p[0], "data-theme-pick": p[0],
        "aria-label": p[0] + " theme", title: "Theme: " + p[0], "data-testid": "theme-" + p[0]
      }, icon(p[1], 13)));
    });
    aside.appendChild(E("div", "sb-foot", null,
      E("button", "sb-iconbtn", { type: "button", id: "openDrawer", "aria-label": "Open admin drawer", title: "Admin" },
        icon("gear", 17)), seg));
    navWrap.appendChild(aside);
    root.appendChild(navWrap);

    var col = E("div", "flex min-h-0 min-w-0 flex-1 flex-col");
    col.appendChild(E("div", "flex items-center border-[var(--border)] border-b px-3 py-2 sm:hidden", null,
      E("button", "rounded-md px-2 py-1 text-[var(--muted)] text-xs",
        { type: "button", id: "navOpen", "aria-label": "Open navigation", "data-testid": "nav-trigger" }, "Menu")));

    var main = E("main", "conv-pane", { "aria-label": "Conversation", "data-testid": "conversation-pane" });
    main.appendChild(E("header", "conv-header", { id: "convHeader" }));
    main.appendChild(E("div", "conv-timeline", { id: "timeline", "data-testid": "timeline" }));

    var composer = E("div", "conv-composer", { "data-testid": "composer" });
    composer.appendChild(E("div", "conv-composer__error", { id: "composerError", role: "alert", "data-testid": "composer-error", hidden: true }));
    var framebox = E("div", "conv-composer__frame");
    framebox.appendChild(E("input", "conv-composer__input", {
      id: "composerInput", autocomplete: "off", spellcheck: "false", placeholder: "Message"
    }));
    var row = E("div", "conv-composer__row");
    row.appendChild(E("button", "conv-pill", { type: "button", id: "asPill", title: "Send-as identity — click to edit" }, "as "));
    var toWrap = E("div", "conv-composer__to-wrap", null,
      E("button", "conv-pill", { type: "button", id: "toPill", title: "Target — maps to the 'to' field" }, "→ everyone"),
      E("div", "conv-menu", { id: "toMenu", "data-testid": "to-menu", hidden: true }));
    row.appendChild(toWrap);
    row.appendChild(E("button", "conv-pill", { type: "button", id: "expectsPill", "data-testid": "expects-pill", title: "expects_reply — click to cycle" }, "expects · —"));
    row.appendChild(E("button", "conv-send", {
      type: "button", id: "sendBtn", "data-testid": "send-button",
      title: "Send (Enter)", "aria-label": "Send message"
    }, icon("paperPlane", 15, "ph")));
    framebox.appendChild(row);
    composer.appendChild(framebox);
    main.appendChild(composer);
    col.appendChild(main);
    root.appendChild(col);

    root.appendChild(E("button", "fixed inset-0 z-40 bg-[var(--scrim)]",
      { id: "drawerScrim", type: "button", "aria-label": "Close admin drawer", hidden: true }));
    root.appendChild(E("div", "fixed inset-y-0 right-0 z-50 w-[min(430px,100vw)] border-[var(--border-strong)] border-l",
      { id: "drawerWrap", hidden: true }));

    app.appendChild(root);
  }

  /* ---------------------------------------------------------------- events */
  function flash(key) {
    S.copied[key] = true;
    renderAll();
    setTimeout(function () { delete S.copied[key]; renderAll(); }, 1200);
  }
  function copyText(s, key) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(s).then(function () { flash(key); }, function () {});
    }
  }
  function doSend() {
    var input = document.getElementById("composerInput");
    var text = (input.value || "").trim();
    if (!text) { return; }
    var dm = S.view.kind === "dm" ? S.view.agent : null;
    api("/admin/say", {
      room: S.view.room, sender: (S.sendAs || "operator").trim() || "operator",
      to: dm || S.to, text: text, expects_reply: S.expects
    }).then(function () {
      input.value = ""; S.expects = null; S.sendError = null; S.stick = true;
      return poll();
    }).catch(function () {
      S.sendError = "Send failed — the relay rejected that message. Try again.";
      renderComposer();
    });
  }
  function wire() {
    document.addEventListener("click", function (ev) {
      var t = ev.target.closest ? ev.target.closest("button,[data-room],[data-agent]") : null;
      if (!t) { return; }
      var id = t.id;

      if (t.hasAttribute("data-room")) {
        S.view = { kind: "room", room: t.getAttribute("data-room"), agent: null };
        S.navOpen = false; S.stick = true; renderAll(); return;
      }
      if (t.hasAttribute("data-agent")) {
        S.view = { kind: "dm", room: S.view.room, agent: t.getAttribute("data-agent") };
        S.navOpen = false; S.stick = true; renderAll(); return;
      }
      if (t.hasAttribute("data-theme-pick")) { applyTheme(t.getAttribute("data-theme-pick")); return; }
      if (t.hasAttribute("data-to")) {
        var pick = t.getAttribute("data-to");
        S.to = pick;
        if (S.expects && S.expects !== "anyone" && S.expects !== pick) { S.expects = null; }
        S.menuOpen = false; renderComposer(); return;
      }
      if (t.hasAttribute("data-copykey")) { copyText(t.getAttribute("data-copykey"), "k" + t.getAttribute("aria-label")); return; }
      if (t.hasAttribute("data-revoke")) {
        var name = t.getAttribute("data-revoke");
        if (!S.confirmKill[name]) {
          S.confirmKill[name] = true; renderKeys();
          setTimeout(function () { delete S.confirmKill[name]; renderKeys(); }, 2500);
          return;
        }
        delete S.confirmKill[name];
        api("/admin/revoke", { target: name }).then(poll).catch(function () {});
        return;
      }

      switch (id) {
        case "navOpen": S.navOpen = true; renderAll(); break;
        case "navScrim": S.navOpen = false; renderAll(); break;
        case "openDrawer": S.drawerOpen = true; renderDrawer(); break;
        case "adClose": case "drawerScrim": S.drawerOpen = false; renderDrawer(); break;
        case "recentToggle": S.recentOpen = !S.recentOpen; renderSidebar(); break;
        case "backToRoom": S.view = { kind: "room", room: S.view.room, agent: null }; S.stick = true; renderAll(); break;
        case "toPill": S.menuOpen = !S.menuOpen; renderComposer(); break;
        case "expectsPill": {
          var dm = S.view.kind === "dm" ? S.view.agent : null;
          var target = dm || S.to;
          var cycle = [null, "anyone"];
          if (target !== "all") { cycle.push(target); }
          S.expects = cycle[(cycle.indexOf(S.expects) + 1) % cycle.length];
          renderComposer(); break;
        }
        case "sendBtn": doSend(); break;
        case "asPill": startEditAs(); break;
        case "adSaveToken": {
          var v = document.getElementById("adToken").value.trim();
          S.token = v; localStorage.setItem(TOKEN_KEY, v); poll(); break;
        }
        case "adCopyUrl": copyText((S.data && S.data.public_url) || "", "url"); break;
        case "adMint": doMint(); break;
        case "adRegen": doRegen(); break;
        default: break;
      }
    });

    document.addEventListener("input", function (ev) {
      if (ev.target.id === "composerInput") { renderComposer(); }
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.target.id === "composerInput" && ev.key === "Enter") { ev.preventDefault(); doSend(); }
    });
    document.addEventListener("scroll", function (ev) {
      var el = ev.target;
      if (el && el.id === "timeline") {
        S.stick = el.scrollHeight - el.scrollTop - el.clientHeight <= BOTTOM_SLOP_PX;
      }
    }, true);
  }
  function startEditAs() {
    var pill = document.getElementById("asPill");
    if (!pill || S.editingAs) { return; }
    S.editingAs = true;
    var inp = E("input", "conv-composer__as-input", {
      id: "asInput", maxlength: "16", spellcheck: "false", value: S.sendAs
    });
    pill.replaceWith(inp);
    inp.focus(); inp.select();
    function done() {
      S.sendAs = (inp.value || "").trim() || S.sendAs;
      S.editingAs = false;
      var back = E("button", "conv-pill", { type: "button", id: "asPill", title: "Send-as identity — click to edit" });
      inp.replaceWith(back);
      renderComposer();
    }
    inp.addEventListener("blur", done);
    inp.addEventListener("keydown", function (e) {
      e.stopPropagation();
      if (e.key === "Enter") { inp.blur(); }
    });
  }
  function doMint() {
    var name = document.getElementById("adName").value.trim();
    var out = document.getElementById("adMintOut");
    if (!name) { return; }
    api("/admin/invite", {
      name: name,
      room: document.getElementById("adRoom").value,
      expires: document.getElementById("adExpiry").value,
      capabilities: document.getElementById("adCap").value.trim() || null
    }).then(function (r) {
      out.textContent = "";
      var box = E("div", "ad-resultbox", null,
        "Key for ", E("b", null, { text: r.name || name }), " in ",
        E("b", null, { text: "#" + (r.room || "default") }),
        E("div", "ad-code", { text: r.code }),
        E("div", null, { style: "margin-top:7px" },
          E("button", "ad-btn", { type: "button", "data-copykey": r.code, "aria-label": "minted" },
            icon("copy", 12), " Copy code")),
        E("p", "ad-hint", null, "Copy it now — with hashing on it will not be shown again."));
      out.appendChild(box);
      document.getElementById("adName").value = "";
      document.getElementById("adCap").value = "";
      return poll();
    }).catch(function () {
      out.textContent = "";
      out.appendChild(E("div", "ad-errorbox", null, "Mint failed — check the admin token."));
    });
  }
  function doRegen() {
    var btn = document.getElementById("adRegen");
    var out = document.getElementById("adRegenOut");
    if (!S.regen.armed) {
      S.regen.armed = true;
      btn.textContent = ""; btn.appendChild(icon("arrowClockwise", 13));
      btn.appendChild(document.createTextNode(" Really regenerate?"));
      btn.className = "ad-btn danger confirm";
      setTimeout(function () {
        if (!S.regen.armed) { return; }
        S.regen.armed = false;
        btn.textContent = ""; btn.appendChild(icon("arrowClockwise", 13));
        btn.appendChild(document.createTextNode(" Regenerate admin token"));
        btn.className = "ad-btn danger";
      }, 3000);
      return;
    }
    S.regen.armed = false;
    api("/admin/regenerate-token", {}).then(function (r) {
      S.token = r.admin_token;
      localStorage.setItem(TOKEN_KEY, r.admin_token);
      var f = document.getElementById("adToken");
      if (f) { f.value = r.admin_token; }
      out.textContent = "";
      out.appendChild(E("div", "ad-resultbox", null, "New admin token",
        E("div", "ad-code", { text: r.admin_token }),
        E("p", "ad-hint", null, "Saved to this browser. Anyone else on the dashboard must re-enter it.")));
      btn.textContent = ""; btn.appendChild(icon("arrowClockwise", 13));
      btn.appendChild(document.createTextNode(" Regenerate admin token"));
      btn.className = "ad-btn danger";
      return poll();
    }).catch(function () {
      out.textContent = "";
      out.appendChild(E("div", "ad-errorbox", null, "Regenerate failed."));
    });
  }

  /* Test seam — the pure helpers, so the suite can unit-test them directly.
     Read-only maths on strings/numbers: no state, no network, no DOM writes. */
  window.__argy = {
    hueFor: hueFor, glyphFor: glyphFor, brandAccent: brandAccent,
    lastSeen: lastSeen, elapsedSince: elapsedSince, dedupe: dedupe
  };

  /* ------------------------------------------------------------------ boot */
  var stored = localStorage.getItem(THEME_KEY);
  applyTheme(stored === "light" || stored === "dark" ? stored : "auto");
  shell();
  wire();
  renderAll();
  poll();
  setInterval(poll, POLL_MS);
  setInterval(tick, 1000);
})();
</script>
</body>
</html>
"""
