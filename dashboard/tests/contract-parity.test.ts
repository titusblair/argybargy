import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Reads the SHIPPED, BUILT artifact (argybargy/dashboard.html) and asserts
// every /admin/... path string baked into it is one of the five frozen
// admin endpoints from src/state/contract.ts. Catches an accidental new
// endpoint (or a typo'd one) making it into the client bundle.

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const builtHtmlPath = path.resolve(
  __dirname,
  "..",
  "..",
  "argybargy",
  "dashboard.html"
);

const ALLOWED_ADMIN_PATHS = new Set([
  "/admin/state",
  "/admin/invite",
  "/admin/say",
  "/admin/revoke",
  "/admin/regenerate-token",
]);

describe("contract parity (built artifact)", () => {
  it("built dashboard.html exists (run `pnpm run build && node scripts/emit-dashboard.mjs` first)", () => {
    expect(existsSync(builtHtmlPath)).toBe(true);
  });

  it("only ever calls the five frozen admin endpoints", () => {
    const html = readFileSync(builtHtmlPath, "utf8");
    const found = [...html.matchAll(/\/admin\/[a-z-]+/g)].map((m) => m[0]);

    expect(found.length).toBeGreaterThan(0);

    const unexpected = [...new Set(found)].filter(
      (p) => !ALLOWED_ADMIN_PATHS.has(p)
    );
    expect(unexpected).toEqual([]);
  });
});
