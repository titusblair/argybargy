/**
 * A single agent row in the Sidebar's AGENTS section (or the "recently
 * offline" disclosure). Owned by the sidebar lane — see Sidebar.tsx.
 */

import { lastSeen } from "../state/format";
import type { AgentView } from "../state/presence";

/** Stable 0-4 bucket for the shared .h0-.h4 hue classes in styles.css,
 * derived from the presence layer's 0-359 `hue` value. The operator
 * (human) is special-cased to the neutral .hop hue, per the mockup. */
function hueClass(hue: number, isOperator: boolean): string {
  if (isOperator) {
    return "hop";
  }
  return `h${hue % 5}`;
}

function monogram(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

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
  const isOperator = agent.name === "operator";
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
      <span className={`sb-av ${hueClass(agent.hue, isOperator)}`}>
        {monogram(agent.name)}
        <span className={agent.life === "online" ? "sb-pdot" : "sb-pdot off"} />
      </span>
      <span className="sb-aname">{agent.name}</span>
      <span className="sb-alast mono" data-testid="last-seen">
        {agent.life === "online" ? "online" : `${lastSeen(displaySeconds)} ago`}
      </span>
    </button>
  );
}
