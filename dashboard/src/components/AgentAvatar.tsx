/**
 * Shared agent avatar, used by BOTH the sidebar rows and every
 * conversation-pane author chip (timeline groups, DM header, to-menu) so
 * the two surfaces can't drift.
 *
 * Renders the agent's vendor mark (agent-logos.ts) when the name maps to a
 * known vendor, the human seat as a person glyph, and everything else as
 * the original hued monogram — unknown mesh agents look exactly like they
 * did before.
 *
 * Treatment: the chip itself (15% hue fill, 40% hue border, squircle) is
 * unchanged from the monogram era, and the mark is filled with
 * currentColor so it inherits the same per-agent hue the initials had.
 * Identity stays in the hue; only the glyph got smarter. Presence dot,
 * join-pulse, and fading all key off the chip/dot classes, which are
 * preserved verbatim (.sb-av/.sb-pdot, .conv-avatar/.conv-avatar__dot).
 */

import { User } from "@phosphor-icons/react";
import { hueFor } from "../state/presence";
import { glyphFor } from "./agent-logos";
import "./AgentAvatar.css";

/** "row" = 26px sidebar rail chip; "lg" = 30px timeline author chip;
 * "sm" = 20px header / to-menu chip. */
export type AgentAvatarSize = "row" | "lg" | "sm";

function monogram(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

function Glyph({ name }: { name: string }) {
  const glyph = glyphFor(name);
  if (!glyph) {
    return <>{monogram(name)}</>;
  }
  if (glyph.kind === "person") {
    return <User className="agent-logo agent-logo--person" weight="fill" />;
  }
  return (
    <svg aria-hidden="true" className="agent-logo" viewBox="0 0 24 24">
      <path d={glyph.path} fill="currentColor" />
    </svg>
  );
}

export function AgentAvatar({
  name,
  size,
  dot,
  round = false,
}: {
  name: string;
  size: AgentAvatarSize;
  /** Presence dot; omit on surfaces without presence (timeline, to-menu). */
  dot?: "on" | "off";
  /** Round chip (DM header). The operator is always round off the rail. */
  round?: boolean;
}) {
  const isOperator = name === "operator";

  if (size === "row") {
    return (
      <span className={`sb-av ${isOperator ? "hop" : `h${hueFor(name) % 5}`}`}>
        <Glyph name={name} />
        {dot ? (
          <span className={dot === "on" ? "sb-pdot" : "sb-pdot off"} />
        ) : null}
      </span>
    );
  }

  const classes = [
    "conv-avatar",
    size === "sm" ? "conv-avatar--sm" : "",
    round || isOperator ? "conv-avatar--round" : "",
    isOperator ? "hue-op" : `hue-${hueFor(name) % 5}`,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <span className={classes}>
      <Glyph name={name} />
      {dot ? (
        <span
          className={
            dot === "on"
              ? "conv-avatar__dot"
              : "conv-avatar__dot conv-avatar__dot--off"
          }
        />
      ) : null}
    </span>
  );
}
