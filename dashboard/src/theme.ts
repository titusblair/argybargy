/**
 * Theme engine — auto / light / dark.
 *
 * Mirrors the locked mockup's theme logic (argy-dashboard-mockup.html):
 *  - "auto" resolves from `prefers-color-scheme` at render time (handled by
 *    the CSS `@media (prefers-color-scheme: light)` block in styles.css —
 *    dark is the `:root` default, so only the light override is needed).
 *  - The manual toggle cycles auto -> light -> dark -> auto.
 *  - Preference persists to `localStorage` under "cc_theme".
 *  - Preference is applied via `data-theme` on `<html>` (not a "light"
 *    class, per Task 4 brief — the CSS keys off `:root[data-theme="dark"]`
 *    / `:root[data-theme="light"]`, and "auto" leaves resolution to the
 *    prefers-color-scheme media query).
 */

export type Theme = "auto" | "light" | "dark";

const STORAGE_KEY = "cc_theme";
const CYCLE: readonly Theme[] = ["auto", "light", "dark"];

function isTheme(value: string | null): value is Theme {
  return value === "auto" || value === "light" || value === "dark";
}

/** Reads the persisted theme preference, defaulting to "auto". */
export function currentTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY);
  return isTheme(stored) ? stored : "auto";
}

/** Persists `theme` and applies it to `<html data-theme>`. */
export function applyTheme(theme: Theme): void {
  localStorage.setItem(STORAGE_KEY, theme);
  document.documentElement.setAttribute("data-theme", theme);
}

/** Cycles auto -> light -> dark -> auto, applying and persisting each step. */
export function cycleTheme(): Theme {
  const next = CYCLE[(CYCLE.indexOf(currentTheme()) + 1) % CYCLE.length];
  applyTheme(next);
  return next;
}
