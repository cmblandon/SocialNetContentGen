import { test, expect } from "@playwright/test";

// Assumes: backend running at process.env.NEXT_PUBLIC_API_BASE_URL (or
// http://localhost:8000), with a pending chapter already seeded (via the
// scripts this Phase 6 verification run used — see the step 6.14 report)
// and an `optimal_time:tiktok=HH:MM` line in calendario.md so approving
// actually attempts a publish rather than just proposing a time.
const ADMIN_TOKEN = process.env.ADMIN_PANEL_TOKEN ?? "e2e-test-token";

test("approving a pending platform version surfaces it in the editorial calendar", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Access token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/approvals/);

  await expect(page.getByRole("heading", { name: "AARO 2024 Annual Report" })).toBeVisible();

  await page.getByRole("button", { name: /approve tiktok/i }).click();

  // The approval response is shown inline (published, proposed, or failed).
  await expect(page.getByText(/published \(post id|publish failed|proposed schedule/i)).toBeVisible();

  await page.goto("/calendar");
  await expect(page.getByRole("cell", { name: "tiktok" })).toBeVisible();
});
