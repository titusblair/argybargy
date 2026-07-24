import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

// Loads the SHIPPED, BUILT artifact (argybargy/dashboard.html) directly over
// file:// — no dev server, no fixture seeding, all network aborted. This is
// the offline self-containment guarantee: the file that ships must render
// its shell with zero external requests. Distinct from the *.spec.ts specs
// in this directory, which exercise the vite dev server against FIXTURE data.

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const builtHtmlPath = path.resolve(
  __dirname,
  "..",
  "..",
  "argybargy",
  "dashboard.html"
);
const builtHtmlUrl = `file://${builtHtmlPath}`;

// biome-ignore lint/suspicious/noSkippedTests: conditional guard (missing build artifact), not a disabled test
test.skip(
  !existsSync(builtHtmlPath),
  `built artifact not found at ${builtHtmlPath} — run \`pnpm run build && node scripts/emit-dashboard.mjs\` first`
);

test("built file renders offline with network fully blocked", async ({
  page,
}) => {
  const nonFileRequests: string[] = [];

  await page.route("**/*", (route) => {
    const url = route.request().url();
    if (url.startsWith("file:")) {
      route.continue();
      return;
    }
    nonFileRequests.push(url);
    route.abort();
  });

  await page.goto(builtHtmlUrl);

  // Prod build with no relay behind it won't have fixture/live data — that's
  // expected. Assert the shell/chrome mounted, not that it's populated.
  const app = page.locator("#app");
  await expect(app).not.toBeEmpty();

  expect(nonFileRequests).toEqual([]);
});
