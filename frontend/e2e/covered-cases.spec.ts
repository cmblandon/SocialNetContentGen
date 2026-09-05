import { test, expect } from "@playwright/test";

// Assumes: backend running with casos_cubiertos.md seeded with at least
// "AARO Radar Report" and "CIA Reading Room File" entries (see the step
// 6.14 report for the exact seed script used during verification).
const ADMIN_TOKEN = process.env.ADMIN_PANEL_TOKEN ?? "e2e-test-token";

test("searching and editing a covered case persists the change", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Access token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/approvals/);

  await page.goto("/cases");
  await expect(page.getByText("AARO Radar Report")).toBeVisible();
  await expect(page.getByText("CIA Reading Room File")).toBeVisible();

  await page.getByLabel(/search/i).fill("radar");
  await page.getByRole("button", { name: "Search" }).click();

  await expect(page.getByText("AARO Radar Report")).toBeVisible();
  await expect(page.getByText("CIA Reading Room File")).not.toBeVisible();

  await page.getByRole("button", { name: "Edit" }).click();
  const reasonField = page.getByLabel(/reason/i);
  await reasonField.fill("verified via E2E test");
  await page.getByRole("button", { name: "Save" }).click();

  await expect(page.getByText("verified via E2E test")).toBeVisible();

  // Reload to confirm the edit was persisted server-side, not just local state.
  await page.reload();
  await expect(page.getByText("verified via E2E test")).toBeVisible();
});
