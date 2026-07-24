import { expect, type Page, test } from "@playwright/test";

const ACTIVE_CLASS_RE = /active/;
const RECENTLY_OFFLINE_RE = /Recently offline/;

/** On the mobile project the sidebar is the off-canvas drawer (<640px, see
 * app.tsx's `navOpen`-gated wrapper) — open it first so sidebar content is
 * actually in-viewport and clickable. No-op on desktop, where the nav
 * trigger doesn't render. */
async function openSidebarIfOffCanvas(page: Page) {
  // The trigger is always in the DOM (app.tsx hides it above the sm
  // breakpoint with a Tailwind class rather than unmounting it), so a mere
  // .count() check passes on desktop too and then hangs waiting to click a
  // hidden element — isVisible() actually reflects the CSS display state.
  const navTrigger = page.getByTestId("nav-trigger");
  if (await navTrigger.isVisible()) {
    await navTrigger.click();
  }
}

test.describe("Sidebar", () => {
  test("renders rooms and online agents with presence dots", async ({
    page,
  }) => {
    await page.goto("/");
    await openSidebarIfOffCanvas(page);

    const roomList = page.getByTestId("room-list");
    await expect(roomList.locator("[data-room]")).not.toHaveCount(0);
    // FIXTURE seeds a "build" room with online peers.
    await expect(roomList.locator('[data-room="build"]')).toBeVisible();

    const agentList = page.getByTestId("agent-list");
    const agentRows = agentList.locator("[data-agent]");
    await expect(agentRows).not.toHaveCount(0);

    // Every visible row carries a presence dot (on or off state).
    const dotCount = await agentList.locator(".sb-pdot").count();
    expect(dotCount).toBe(await agentRows.count());
  });

  test("clicking the gear opens the admin drawer", async ({ page }) => {
    await page.goto("/");
    await openSidebarIfOffCanvas(page);

    await expect(page.getByTestId("admin-drawer")).toHaveCount(0);
    await page.getByRole("button", { name: "Open admin drawer" }).click();
    await expect(page.getByTestId("admin-drawer")).toBeVisible();
  });

  test("clicking a room switches the active view", async ({ page }) => {
    await page.goto("/");
    await openSidebarIfOffCanvas(page);

    const defaultRoom = page.locator('[data-room="default"]');
    await defaultRoom.click();
    await expect(defaultRoom).toHaveClass(ACTIVE_CLASS_RE);
  });

  test("recently-offline agents collapse into a disclosure", async ({
    page,
  }) => {
    await page.goto("/");
    await openSidebarIfOffCanvas(page);

    const head = page.getByRole("button", { name: RECENTLY_OFFLINE_RE });
    if (await head.count()) {
      await expect(page.getByTestId("recent-offline-list")).toHaveCount(0);
      await head.click();
      await expect(page.getByTestId("recent-offline-list")).toBeVisible();
    }
  });

  test("no horizontal scroll at 390px with sidebar content mounted", async ({
    page,
  }) => {
    await page.setViewportSize({ height: 844, width: 390 });
    await page.goto("/");

    // Open the off-canvas drawer (mobile nav trigger lives in app.tsx) so
    // the sidebar's own content is actually laid out/visible, then assert
    // the document still doesn't overflow horizontally.
    await openSidebarIfOffCanvas(page);
    await expect(page.getByTestId("sidebar")).toBeVisible();

    const { clientWidth, scrollWidth } = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
  });
});
