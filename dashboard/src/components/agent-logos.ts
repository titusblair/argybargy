/**
 * Agent name → vendor brand mark + official brand color. Case-insensitive
 * substring rules, first hit wins; any name that matches nothing keeps the
 * generated hue + monogram (see AgentAvatar / hueFor), so unknown mesh
 * agents look exactly as they did before logos landed.
 *
 * Path data comes from the `simple-icons` npm package (dev dependency —
 * the 24x24 path strings are compiled into the bundle, so the built
 * single-file artifact stays fully offline; no external URLs).
 *
 * Color note — we render each mark in the vendor's OFFICIAL brand color,
 * not a UI-matched hue. But several vendors' canonical mark is black or
 * near-black (Anthropic #191919, Cursor/OpenCode #000, OpenAI's knot),
 * which would vanish on our near-black chip. Those brands render their own
 * mark in white on a dark surface (see anthropic.com, openai.com, the
 * Cursor and OpenCode brand sheets), so on dark we use their dark-surface
 * treatment (near-white) and on light we use the true brand hex. Vendors
 * whose brand color already reads on both (Qwen purple, Gemini violet) use
 * the real hex on both. This is the official color, adapted to surface the
 * way the vendors themselves do — not themed to our palette.
 *
 * Deliberate gap: hermes has no honest vendor glyph (simple-icons' "Hermes"
 * is the fashion house's horse carriage) — it keeps the generated hue +
 * monogram. A wrong mark is worse than initials.
 */

import {
  siAnthropic,
  siCursor,
  siGooglegemini,
  siOpencode,
  siQwen,
} from "simple-icons";

/** A vendor brand color: `dark` used on the dark chip, `light` on the light
 * chip. Same value in both fields when the brand hue reads on either. */
export interface BrandColor {
  dark: string;
  light: string;
}

export type AgentGlyph =
  /** Monochrome 24x24 brand path, filled with the vendor's brand color. */
  | { kind: "brand"; path: string; title: string; color: BrandColor }
  /** The human seat — a Phosphor person glyph in the neutral operator tone. */
  | { kind: "person" };

/** OpenAI knot, verbatim from simple-icons 11.15.0 (`icons/openai.svg`;
 * the mark was dropped from simple-icons in a later major). */
const OPENAI_PATH =
  "M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z";

/** Near-white used on the dark chip for brands whose mark is black/near-black
 * (matching how those vendors render on a dark surface). */
const ON_DARK = "#ececf1";

function brand(
  icon: { path: string; title: string },
  color: BrandColor
): AgentGlyph {
  return { color, kind: "brand", path: icon.path, title: icon.title };
}

/** Same brand hue on both surfaces (already legible on either). */
function both(hex: string): BrandColor {
  return { dark: hex, light: hex };
}

/** Dark-surface (near-white) treatment + true brand hex on light. */
function onDark(lightHex: string): BrandColor {
  return { dark: ON_DARK, light: lightHex };
}

/** Ordered — first matching rule wins. */
const RULES: [RegExp, AgentGlyph][] = [
  [/claude|anthropic/i, brand(siAnthropic, onDark(`#${siAnthropic.hex}`))],
  [
    /codex|gpt|openai/i,
    brand({ path: OPENAI_PATH, title: "OpenAI" }, onDark("#000000")),
  ],
  [/qwen/i, brand(siQwen, both(`#${siQwen.hex}`))],
  [/gemini/i, brand(siGooglegemini, both(`#${siGooglegemini.hex}`))],
  [/cursor/i, brand(siCursor, onDark(`#${siCursor.hex}`))],
  [/opencode/i, brand(siOpencode, onDark(`#${siOpencode.hex}`))],
  [/operator|human|\byou\b/i, { kind: "person" }],
];

/** The vendor glyph for an agent name, or undefined → monogram fallback. */
export function glyphFor(name: string): AgentGlyph | undefined {
  return RULES.find(([re]) => re.test(name))?.[1];
}

/** The brand color for a known vendor's *name/accent* (sidebar rows, timeline
 * authors, header), or undefined if the name has no vendor mark. Uses the
 * real brand hue on both surfaces where it reads; for the black/near-black
 * brands, `dark` is near-white so the name stays legible on the dark rail.
 * Callers fall back to hueFor() when this returns undefined. */
export function brandAccent(name: string): BrandColor | undefined {
  const glyph = glyphFor(name);
  return glyph && glyph.kind === "brand" ? glyph.color : undefined;
}
