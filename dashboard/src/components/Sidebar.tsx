/**
 * Sidebar — workspace header, ROOMS, AGENTS (presence-first), footer admin
 * trigger + theme toggle. Prop-less: reads `agents`, `view`, `state`,
 * `connection` from `state/store.ts` and `drawerOpen` from `state/ui.ts`
 * directly; sets `view.value` to switch rooms/DMs. Ported from the locked
 * mockup's sidebar region (argy-dashboard-mockup.html: #sidebar).
 *
 * Mobile off-canvas positioning (<640px) is handled by the wrapper in
 * app.tsx — this component only renders its own content, full height/width
 * of whatever box it's placed in.
 */

import {
  CaretRight,
  CircleHalf,
  Gear,
  Hash,
  Moon,
  Sun,
} from "@phosphor-icons/react";
import { useEffect, useMemo, useState } from "preact/hooks";
import "./Sidebar.css";
import { roomList } from "../state/filters";
import type { AgentView } from "../state/presence";
import { agents, connection, state, view } from "../state/store";
import { drawerOpen } from "../state/ui";
import { applyTheme, currentTheme, type Theme } from "../theme";
import { SidebarAgentRow } from "./SidebarAgentRow";

const THEME_OPTIONS: readonly Theme[] = ["auto", "light", "dark"];

/** Union of `agents` (one AgentView per room the peer belongs to) into one
 * row per name — online in any room counts as online; the freshest
 * (lowest) secondsSinceSeen and the most "alive" life win the merge. */
function dedupeAgents(views: AgentView[]): AgentView[] {
  const byName = new Map<string, AgentView>();
  const lifeRank: Record<AgentView["life"], number> = {
    fading: 1,
    offline: 0,
    online: 2,
  };
  for (const v of views) {
    const existing = byName.get(v.name);
    if (!existing) {
      byName.set(v.name, v);
      continue;
    }
    const better =
      lifeRank[v.life] > lifeRank[existing.life] ||
      (lifeRank[v.life] === lifeRank[existing.life] &&
        v.secondsSinceSeen < existing.secondsSinceSeen);
    byName.set(v.name, {
      ...existing,
      justJoined: existing.justJoined || v.justJoined,
      life: better ? v.life : existing.life,
      online: existing.online || v.online,
      secondsSinceSeen: better ? v.secondsSinceSeen : existing.secondsSinceSeen,
    });
  }
  return [...byName.values()];
}

function openDrawer() {
  drawerOpen.value = true;
}

function selectRoom(room: string) {
  view.value = { kind: "room", room };
}

function selectAgent(name: string, room: string) {
  view.value = { agent: name, kind: "dm", room };
}

/** Per-key stable callback cache: JSX handlers built from a list (one per
 * room / one per agent) need a stable function *reference* across renders
 * to satisfy lint/performance/noJsxPropsBind — a `useCallback` per list
 * item isn't possible (hooks can't run in a loop), so this caches one
 * closure per key and reuses it as long as the key and its captured
 * dependency haven't changed. The cache Map itself is created once (empty
 * dependency array — `useMemo` only needs to survive re-renders, it does
 * not need to be recreated when `dep` changes) and staleness is handled
 * per-entry by comparing `cached.dep === dep` on lookup. */
function useKeyedCallbacks<Dep>(
  dep: Dep,
  make: (key: string, dep: Dep) => () => void
): (key: string) => () => void {
  const cache = useMemo(
    () => new Map<string, { dep: Dep; fn: () => void }>(),
    []
  );
  return (key: string) => {
    const cached = cache.get(key);
    if (cached && cached.dep === dep) {
      return cached.fn;
    }
    const fn = () => make(key, dep)();
    cache.set(key, { dep, fn });
    return fn;
  };
}

export function Sidebar() {
  // Ticking clock: recomputes displayed lastSeen text once a second without
  // waiting on the next /admin/state poll. `baseline` anchors wall-clock
  // elapsed time to whichever agents snapshot is current, so a fresh poll
  // (new secondsSinceSeen from the server) doesn't get double-counted.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const [recentOpen, setRecentOpen] = useState(false);

  const s = state.value;
  const rooms = s ? roomList(s) : [];
  const currentView = view.value;
  const roster = dedupeAgents(agents.value);
  const [baseline, setBaseline] = useState(() => ({ now, roster }));

  // Re-anchor the baseline whenever the underlying roster snapshot changes
  // (a fresh poll landed) so ticking resumes from the new numbers instead
  // of drifting off the previous baseline forever.
  const rosterKey = roster
    .map((r) => `${r.name}:${r.secondsSinceSeen}:${r.life}`)
    .join("|");
  const baselineKey = baseline.roster
    .map((r) => `${r.name}:${r.secondsSinceSeen}:${r.life}`)
    .join("|");
  if (rosterKey !== baselineKey) {
    setBaseline({ now, roster });
  }

  const elapsedSeconds = Math.max(0, (now - baseline.now) / 1000);
  const displaySecondsFor = (agent: AgentView) =>
    agent.life === "online" ? 0 : agent.secondsSinceSeen + elapsedSeconds;

  const visible = roster
    .filter((r) => r.life !== "offline")
    .sort((a, b) => {
      const rank = (r: AgentView) => (r.life === "online" ? 0 : 1);
      return rank(a) - rank(b) || a.name.localeCompare(b.name);
    });
  const recentlyOffline = roster
    .filter((r) => r.life === "offline")
    .sort((a, b) => a.secondsSinceSeen - b.secondsSinceSeen);
  const onlineCount = roster.filter((r) => r.life === "online").length;

  const { room } = currentView;
  const activeAgent = currentView.kind === "dm" ? currentView.agent : null;

  const roomClick = useKeyedCallbacks(null, (r) => () => selectRoom(r));
  const agentClick = useKeyedCallbacks(
    room,
    (name, r) => () => selectAgent(name, r)
  );
  const toggleRecentOpen = useMemo(() => () => setRecentOpen((v) => !v), []);

  return (
    <aside aria-label="Workspace" className="sb-root" data-testid="sidebar">
      <div className="sb-head">
        <span className="sb-wsname">argybargy</span>
        <span
          className={`sb-conn ${connection.value}`}
          role="status"
          title={
            connection.value === "live"
              ? "relay reachable — /admin/state answering"
              : `connection: ${connection.value}`
          }
        />
        <span className="sb-wsurl mono">mesh</span>
      </div>

      <nav aria-label="Rooms and agents" className="sb-nav">
        <div className="sb-label">Rooms</div>
        <div data-testid="room-list">
          {rooms.map((r) => {
            const active =
              currentView.kind === "room" && currentView.room === r;
            return (
              <button
                className={active ? "sb-room active" : "sb-room"}
                data-room={r}
                key={r}
                onClick={roomClick(r)}
                type="button"
              >
                <Hash className="sb-ph" size={14} weight="regular" />
                <span>{r}</span>
              </button>
            );
          })}
        </div>

        <div className="sb-label">
          Agents <span className="sb-n">· {onlineCount}</span>
        </div>
        <div data-testid="agent-list">
          {visible.map((agent) => (
            <SidebarAgentRow
              active={activeAgent === agent.name}
              agent={agent}
              displaySeconds={displaySecondsFor(agent)}
              key={agent.name}
              onSelect={agentClick(agent.name)}
            />
          ))}
        </div>

        {recentlyOffline.length > 0 ? (
          <>
            <button
              aria-expanded={recentOpen}
              className={recentOpen ? "sb-recent-head open" : "sb-recent-head"}
              onClick={toggleRecentOpen}
              type="button"
            >
              <CaretRight className="sb-ph" size={12} weight="regular" />
              Recently offline · {recentlyOffline.length}
            </button>
            {recentOpen ? (
              <div data-testid="recent-offline-list">
                {recentlyOffline.map((agent) => (
                  <SidebarAgentRow
                    active={activeAgent === agent.name}
                    agent={agent}
                    displaySeconds={displaySecondsFor(agent)}
                    key={agent.name}
                    onSelect={agentClick(agent.name)}
                    recent
                  />
                ))}
              </div>
            ) : null}
          </>
        ) : null}
      </nav>

      <div className="sb-foot">
        <button
          aria-label="Open admin drawer"
          className="sb-iconbtn"
          onClick={openDrawer}
          title="Admin"
          type="button"
        >
          <Gear size={17} weight="regular" />
        </button>
        <ThemeToggle />
      </div>
    </aside>
  );
}

// Mirrors the mockup's #themeSeg: a 3-way picker calling applyTheme(pref)
// directly rather than stepping a cycle (argy-dashboard-mockup.html lines
// 1025-1034).
function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => currentTheme());
  const pick = useKeyedCallbacks(null, (t) => () => {
    applyTheme(t as Theme);
    setTheme(t as Theme);
  });

  return (
    <fieldset aria-label="Theme" className="sb-seg">
      {THEME_OPTIONS.map((t) => (
        <button
          aria-label={`${t} theme`}
          className={theme === t ? "on" : ""}
          data-testid={`theme-${t}`}
          key={t}
          onClick={pick(t)}
          title={`Theme: ${t}`}
          type="button"
        >
          {themeIcon(t)}
        </button>
      ))}
    </fieldset>
  );
}

function themeIcon(t: Theme) {
  if (t === "auto") {
    return <CircleHalf size={13} weight="regular" />;
  }
  if (t === "light") {
    return <Sun size={13} weight="regular" />;
  }
  return <Moon size={13} weight="regular" />;
}
