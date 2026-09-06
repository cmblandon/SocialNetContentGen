import { test, expect } from "@playwright/test";

/**
 * Task 15.5 — script approval → subtitle review → video generation.
 *
 * Assumes a backend running with:
 *   - one curated chapter in the pipeline whose script is NOT yet approved
 *   - ELEVENLABS_* and (optionally) UNSPLASH_ACCESS_KEY configured, or the
 *     external clients stubbed; without them generation fails and the video
 *     assertions below will not pass
 *   - FFmpeg and ffprobe on PATH
 *
 * Read frontend-standards.md "Data hygiene" before running: the editorial DB
 * path is hardcoded, so seeding for this spec affects every process pointed
 * at data/knowledge_base/. Check `lsof -i :8000 -i :3000` first and use the
 * isolated-backend pattern if either is already bound.
 */
const ADMIN_TOKEN = process.env.ADMIN_PANEL_TOKEN ?? "e2e-test-token";

async function logIn(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByLabel("Access token").fill(ADMIN_TOKEN);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL("/");
}

test("an editor approves a script, reviews subtitles, and generates a video", async ({
  page,
}) => {
  await logIn(page);

  // --- Script approval, from the dedicated queue -----------------------------
  await page.goto("/scripts");
  const card = page.locator("[data-testid^='script-card-']").first();
  await expect(card).toBeVisible();
  await expect(card.getByText("Guion pendiente")).toBeVisible();

  await card.getByRole("button", { name: "Aprobar guion" }).click();
  // Wait for the state change rather than navigating: a goto() here can abort
  // the in-flight POST before the backend receives it (frontend-standards).
  await expect(card.getByText("Guion aprobado")).toBeVisible();

  // --- Subtitles and video, from the pipeline card ---------------------------
  await page.goto("/");
  await page.getByRole("button", { name: "Vista previa" }).first().click();

  const subtitles = page.locator("[data-testid^='subtitles-']").first();
  await expect(subtitles).toBeVisible();
  await subtitles.getByRole("button", { name: "Generar subtítulos" }).click();

  await expect(subtitles.getByLabel("Subtítulos en Español")).toBeVisible({
    timeout: 60_000,
  });
  await expect(subtitles.getByLabel("Subtítulos en Inglés")).toBeVisible();

  // Correcting a caption must survive into the composited video.
  await subtitles.getByRole("button", { name: "Editar Español" }).click();
  const firstSegment = subtitles.getByRole("textbox").first();
  await firstSegment.fill("Texto corregido en E2E");
  await subtitles.getByRole("button", { name: "Guardar Español" }).click();
  await expect(subtitles.getByText("Editado")).toBeVisible();

  const videos = page.locator("[data-testid^='videos-']").first();
  await expect(videos).toBeVisible();
  // One platform keeps the run short; the default would render four.
  await videos.getByLabel("instagram").uncheck();
  await videos.getByLabel("facebook").uncheck();
  await videos.getByLabel("x").uncheck();
  await videos.getByRole("button", { name: "Generar video" }).click();

  // Generation is asynchronous; the card polls every 5s until it settles.
  await expect(videos.getByText("Generando…")).toBeVisible();
  await expect(videos.getByText("Listo")).toBeVisible({ timeout: 180_000 });

  // --- The result is actually playable and listed ----------------------------
  const download = videos.getByRole("link", { name: "Descargar" });
  await expect(download).toBeVisible();
  const href = await download.getAttribute("href");
  expect(href).toContain("/file");
  // The stored path is a server filesystem location, never a browser URL.
  expect(href).not.toContain("data/videos_generated");

  await page.goto("/videos");
  await expect(page.getByRole("cell", { name: "tiktok" }).first()).toBeVisible();
  await expect(page.getByText(/Almacenamiento usado por videos/)).toBeVisible();
});

test("editing an approved script re-blocks video generation", async ({ page }) => {
  await logIn(page);
  await page.goto("/scripts");

  const card = page.locator("[data-testid^='script-card-']").first();
  await expect(card).toBeVisible();

  if (await card.getByRole("button", { name: "Aprobar guion" }).isVisible()) {
    await card.getByRole("button", { name: "Aprobar guion" }).click();
    await expect(card.getByText("Guion aprobado")).toBeVisible();
  }

  await card.getByRole("button", { name: "Editar" }).click();
  // The warning must be visible before saving, not discovered afterwards.
  await expect(card.getByRole("note")).toContainText("reiniciará la aprobación");

  await card.getByLabel("Guion").fill("Guion corregido durante la prueba E2E.");
  await card.getByRole("button", { name: "Guardar" }).click();

  await expect(card.getByText("Guion pendiente")).toBeVisible();
});
