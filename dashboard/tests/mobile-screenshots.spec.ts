import { expect, test } from "@playwright/test";

// Full-page screenshots at 390px for a human (Nick) to eyeball — room view,
// a DM view, and the open admin drawer. Only meaningful on the `mobile`
// Playwright project (390px viewport, see playwright.config.ts); skipped
// elsewhere so desktop runs don't produce a redundant/misleading set.
//
//   pnpm exec playwright test tests/mobile-screenshots.spec.ts --project=mobile
//
// Screenshots land in test-results/mobile-screenshots/ (gitignored — this is
// a human-review artifact, not a pixel-diff assertion).

declare global {
  interface Window {
    __openDrawer?: () => void;
    __setView?: (v: {
      kind: "room" | "dm";
      room: string;
      agent?: string;
    }) => void;
  }
}

const CODEX_TITLE_RE = /codex/i;

test.describe("mobile screenshots (390px)", () => {
  // biome-ignore lint/suspicious/noSkippedTests: conditional guard (non-mobile project), not a disabled test
  test.skip(
    ({ isMobile }) => !isMobile,
    "screenshot gate only meaningful on the mobile (390px) project"
  );

  test("room view", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("conversation-pane")).toBeVisible();
    await page.screenshot({
      fullPage: true,
      path: "test-results/mobile-screenshots/room-view.png",
    });
  });

  test("dm view", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => {
      window.__setView?.({ agent: "codex", kind: "dm", room: "build" });
    });
    await expect(page.getByTestId("channel-title")).toContainText(
      CODEX_TITLE_RE
    );
    await page.screenshot({
      fullPage: true,
      path: "test-results/mobile-screenshots/dm-view.png",
    });
  });

  test("open drawer", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => {
      window.__openDrawer?.();
    });
    await expect(page.getByTestId("admin-drawer")).toBeVisible();
    await page.screenshot({
      fullPage: true,
      path: "test-results/mobile-screenshots/drawer-open.png",
    });
  });
});
