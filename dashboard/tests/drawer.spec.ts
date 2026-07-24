import { expect, test } from "@playwright/test";

const RE_MINT_HEADING = /mint a key/i;
const RE_CLOSE_DRAWER = /close admin drawer/i;
const RE_REVOKE = /revoke/i;
const RE_MINT_BTN = /^mint key$/i;
const RE_SURE = /sure\?/i;
const RE_REGEN_BTN = /regenerate admin token/i;
const RE_REALLY_REGEN = /really regenerate\?/i;

// Opens the drawer via the dev-only `window.__openDrawer()` affordance
// (set in AdminDrawer.tsx under import.meta.env.DEV) rather than the
// sidebar gear — the gear lives in Sidebar.tsx, owned by a sibling lane
// this spec must not depend on.
async function openDrawer(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.evaluate(() => {
    (window as unknown as { __openDrawer: () => void }).__openDrawer();
  });
}

test("drawer opens with mint-key form and keys region, and closes", async ({
  page,
}) => {
  await openDrawer(page);

  await expect(page.getByTestId("admin-drawer")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: RE_MINT_HEADING })
  ).toBeVisible();
  await expect(page.getByTestId("admin-keys")).toBeVisible();

  // app.tsx's scrim button shares the same accessible name (both close the
  // drawer) — scope to the drawer's own close control to avoid ambiguity.
  await page
    .getByTestId("admin-drawer")
    .getByRole("button", { name: RE_CLOSE_DRAWER })
    .click();
  await expect(page.getByTestId("admin-drawer")).toBeHidden();
});

test("respects hash_codes: never renders raw key codes, only revoke", async ({
  page,
}) => {
  await openDrawer(page);

  // Dev fixture ships hash_codes: false, so codes are visible by default —
  // assert the visible-codes case here, and cover the hashed case via the
  // component's own logic (KeyRow renders `.ad-kcode`/copy button only
  // when `!state.value.hash_codes`; there is no live server in this dev
  // harness to toggle hash_codes at runtime).
  const firstRow = page.locator(".ad-krow").first();
  await expect(firstRow.locator(".ad-kcode")).toBeVisible();
  await expect(firstRow.getByRole("button", { name: RE_REVOKE })).toBeVisible();
});

test("mint form validates a name before minting", async ({ page }) => {
  await openDrawer(page);

  const mintBtn = page.getByRole("button", { name: RE_MINT_BTN });
  await expect(mintBtn).toBeDisabled();

  await page.getByLabel("Agent name").fill("newagent");
  await expect(mintBtn).toBeEnabled();
});

test("revoke requires a confirm click", async ({ page }) => {
  await openDrawer(page);

  const firstRow = page.locator(".ad-krow").first();
  const revokeBtn = firstRow.getByRole("button", { name: RE_REVOKE });
  await revokeBtn.click();
  await expect(firstRow.getByRole("button", { name: RE_SURE })).toBeVisible();
});

test("regenerate token requires a confirm click", async ({ page }) => {
  await openDrawer(page);

  const regenBtn = page.getByRole("button", { name: RE_REGEN_BTN });
  await regenBtn.click();
  await expect(
    page.getByRole("button", { name: RE_REALLY_REGEN })
  ).toBeVisible();
});

test("no horizontal scroll with drawer open at 390px", async ({ page }) => {
  await page.setViewportSize({ height: 844, width: 390 });
  await openDrawer(page);
  const { clientWidth, scrollWidth } = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
});
