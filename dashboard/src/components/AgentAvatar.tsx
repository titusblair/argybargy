/**
 * Shared agent avatar, used by BOTH the sidebar rows and every
 * conversation-pane author chip (timeline groups, DM header, to-menu) so
 * the two surfaces can't drift.
 *
 * Renders the agent's vendor mark (agent-logos.ts) in the vendor's OFFICIAL
 * brand color when the name maps to a known vendor, the human seat as a
 * neutral Phosphor person glyph, and everything else as the original hued
 * monogram — unknown mesh agents (and hermes) look exactly as before.
 *
 * Treatment: for a KNOWN vendor the chip drops the hue tint and goes
 * neutral (raised surface + faint border) so the full-color mark pops, and
 * the mark + the agent's NAME both read the brand color via one CSS var —
 * see brandVars() below and the `.is-brand` blocks in AgentAvatar.css. For
 * UNKNOWN agents the chip keeps the exact hued-monogram treatment (15% hue
 * fill, 40% hue border) it had before. Presence dot, join-pulse, and fading
 * all key off the preserved chip/dot classes (.sb-av/.sb-pdot,
 * .conv-avatar/.conv-avatar__dot).
 */

import { User } from "@phosphor-icons/react";
import { hueFor } from "../state/presence";
import { type BrandColor, glyphFor } from "./agent-logos";
import "./AgentAvatar.css";

/** "row" = 26px sidebar rail chip; "lg" = 30px timeline author chip;
 * "sm" = 20px header / to-menu chip. */
export type AgentAvatarSize = "row" | "lg" | "sm";

function monogram(name: string): string {
  return name.slice(0, 2).toUpperCase();
}

/** Inline custom props carrying a brand color's dark + light variants. The
 * `.is-brand` CSS blocks resolve `--agent` from these per active theme, so
 * one variable drives both the mark fill and the name color. Spread onto
 * every element that should read the brand accent. */
export function brandVars(color: BrandColor): Record<string, string> {
  return { "--brand-d": color.dark, "--brand-l": color.light };
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
      <path d={glyph.path} fill="var(--agent)" />
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
  const glyph = glyphFor(name);
  const brand = glyph?.kind === "brand" ? glyph.color : undefined;
  // Known vendor → neutral chip + brand-colored mark (.is-brand). Unknown or
  // operator → keep the existing hue class exactly as before.
  const hue = isOperator ? "hop" : `h${hueFor(name) % 5}`;
  const hueConv = isOperator ? "hue-op" : `hue-${hueFor(name) % 5}`;
  const style = brand ? (brandVars(brand) as never) : undefined;

  const presenceDot = (onClass: string, offClass: string) =>
    dot ? <span className={dot === "on" ? onClass : offClass} /> : null;

  if (size === "row") {
    return (
      <span className={`sb-av ${brand ? "is-brand" : hue}`} style={style}>
        <Glyph name={name} />
        {presenceDot("sb-pdot", "sb-pdot off")}
      </span>
    );
  }

  const classes = [
    "conv-avatar",
    size === "sm" ? "conv-avatar--sm" : "",
    round || isOperator ? "conv-avatar--round" : "",
    brand ? "is-brand" : hueConv,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <span className={classes} style={style}>
      <Glyph name={name} />
      {presenceDot(
        "conv-avatar__dot",
        "conv-avatar__dot conv-avatar__dot--off"
      )}
    </span>
  );
}
