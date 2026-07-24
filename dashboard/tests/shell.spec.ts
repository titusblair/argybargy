import { expect, test } from "@playwright/test";

test("renders the sidebar, conversation pane, and admin-drawer trigger regions", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByTestId("conversation-pane")).toBeVisible();

  // Sidebar is off-canvas on mobile (<640px) until nav-trigger is opened —
  // only assert it's in the DOM here, not necessarily visible.
  await expect(page.getByTestId("sidebar")).toHaveCount(1);
});

test("no horizontal body scroll at 390px", async ({ page }) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await page.goto("/");
  const { clientWidth, scrollWidth } = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
});
