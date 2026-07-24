import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  fullyParallel: true,
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { height: 800, width: 1280 },
      },
    },
    {
      name: "mobile",
      use: {
        ...devices["Pixel 7"],
        viewport: { height: 844, width: 390 },
      },
    },
  ],
  reporter: [["list"]],
  testDir: "./tests",
  // Scope to *.spec.ts only — tests/ also holds vitest *.test.ts files
  // (contract/filters/format/presence/store/theme), and Playwright's
  // default matcher would otherwise try to collect those too.
  testMatch: "**/*.spec.ts",
  use: {
    baseURL: "http://localhost:4321",
    trace: "on-first-retry",
  },
  webServer: {
    // Dev server, not build+preview: import.meta.env.DEV must be true so
    // main.tsx seeds FIXTURE and the shell/component specs see real data.
    // The offline/self-contained check on the BUILT file lands separately
    // (T9).
    command: "pnpm exec vite dev --port 4321 --strictPort",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    url: "http://localhost:4321",
  },
});
