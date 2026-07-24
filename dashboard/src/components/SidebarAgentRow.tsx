/**
 * A single agent row in the Sidebar's AGENTS section (or the "recently
 * offline" disclosure). Owned by the sidebar lane — see Sidebar.tsx.
 */

import { lastSeen } from "../state/format";
import type { AgentView } from "../state/presence";
import { AgentAvatar } from "./AgentAvatar";

export function SidebarAgentRow({
  agent,
  active,
  displaySeconds,
  onSelect,
  recent,
}: {
  agent: AgentView;
  active: boolean;
  /** secondsSinceSeen ticked forward by wall-clock elapsed since the last
   * poll snapshot — see Sidebar.tsx's `now` signal. */
  displaySeconds: number;
  /** Stable callback — see Sidebar.tsx's useKeyedCallbacks. */
  onSelect: () => void;
  recent?: boolean;
}) {
  const classes = [
    recent ? "sb-arow sb-recent-row" : "sb-arow",
    !recent && agent.life === "fading" ? "fading" : "",
    !recent && agent.justJoined ? "join-pulse" : "",
    active ? "active" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      className={classes}
      data-agent={agent.name}
      onClick={onSelect}
      style={{ "--hue": agent.hue } as never}
      type="button"
    >
      <AgentAvatar
        dot={agent.life === "online" ? "on" : "off"}
        name={agent.name}
        size="row"
      />
      <span className="sb-aname">{agent.name}</span>
      <span className="sb-alast mono" data-testid="last-seen">
        {agent.life === "online" ? "online" : `${lastSeen(displaySeconds)} ago`}
      </span>
    </button>
  );
}
