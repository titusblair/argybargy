import { test, expect } from "@playwright/test";

test("renders the hello shell", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#app")).toContainText("argybargy shell");
});
