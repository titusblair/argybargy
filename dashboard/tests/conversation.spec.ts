import { expect, test } from "@playwright/test";

declare global {
  interface Window {
    __setView?: (v: {
      kind: "room" | "dm";
      room: string;
      agent?: string;
    }) => void;
  }
}

const MESSAGE_PLACEHOLDER = /message/i;
const CODEX_TITLE = /codex/i;

test("typing + Enter appends the message to the timeline", async ({ page }) => {
  await page.goto("/");
  await page
    .getByPlaceholder(MESSAGE_PLACEHOLDER)
    .fill("ping from the composer");
  await page.getByPlaceholder(MESSAGE_PLACEHOLDER).press("Enter");
  await expect(page.getByText("ping from the composer")).toBeVisible();
  await expect(page.getByPlaceholder(MESSAGE_PLACEHOLDER)).toHaveValue("");
});

test("setting view to a DM filters the timeline to that agent", async ({
  page,
}) => {
  await page.goto("/");
  await page.evaluate(() => {
    window.__setView?.({ agent: "codex", kind: "dm", room: "build" });
  });
  await expect(page.getByTestId("channel-title")).toContainText(CODEX_TITLE);
});

test("an expecting message shows an expects badge", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("[data-badge='expects']").first()).toBeVisible();
});

test("no horizontal scroll in the conversation pane at 390px", async ({
  page,
}) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await page.goto("/");
  const { clientWidth, scrollWidth } = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
});
