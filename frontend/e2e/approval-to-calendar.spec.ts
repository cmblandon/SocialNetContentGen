import { test, expect } from "@playwright/test";

// Assumes: backend running at process.env.NEXT_PUBLIC_API_BASE_URL (or
// http://localhost:8000), with a pending chapter already seeded (via the
// scripts this Phase 6 verification run used — see the step 6.14 report)
// and an `optimal_time:tiktok=HH:MM` line in calendario.md so publishing
// actually attempts a publish rather than just proposing a time.
//
// enhance-admin-panel-ui: approve and publish are now two explicit,
// separate actions (design.md Decision 1) — approving a case only marks
// its platform versions eligible; the operator must then invoke the
// per-network "Publicar" action to actually attempt a publish.
const ADMIN_TOKEN = process.env.ADMIN_PANEL_TOKEN ?? "e2e-test-token";

test("approving then publishing a pending case surfaces it in the editorial calendar", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Access token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL("/");

  await expect(page.getByRole("heading", { name: "AARO 2024 Annual Report" })).toBeVisible();

  await page.getByRole("button", { name: /^aprobar$/i }).click();
  await expect(page.getByText(/aprobado/i)).toBeVisible();

  await page.getByRole("button", { name: /publicar en tiktok/i }).click();
  // Wait for the publish request to resolve (button is replaced by a
  // status chip either way) before navigating, since page.goto triggers a
  // full navigation that would otherwise abort the in-flight request.
  await expect(page.getByRole("button", { name: /publicar en tiktok/i })).not.toBeVisible();

  await page.goto("/calendar");
  await expect(page.getByRole("cell", { name: "tiktok" })).toBeVisible();
});
