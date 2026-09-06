/**
 * Script and subtitle review embedded in the Pipeline feed (tasks 11.5, 12.3).
 *
 * Kept separate from PipelineFeed.test.tsx, which covers the pre-existing
 * research/approve/publish flow, so a failure points at one feature.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PipelineFeed from "@/components/PipelineFeed";
import * as api from "@/lib/api";

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return {
    __esModule: true,
    ...actual,
    fetchPendingChapters: jest.fn(),
    fetchPendingScripts: jest.fn(),
    fetchCheckpointSummary: jest.fn(),
    fetchSourceUrls: jest.fn(),
    fetchSubtitles: jest.fn(),
    fetchChapterVideos: jest.fn(),
    generateSubtitles: jest.fn(),
    updateSubtitleTrack: jest.fn(),
    approveScript: jest.fn(),
    rejectScript: jest.fn(),
    updateScript: jest.fn(),
  };
});
const mockedApi = api as jest.Mocked<typeof api>;

const chapter: api.PendingChapter = {
  id: "chapter-1",
  title: "Part 1",
  script: "A pilot reported an unidentified radar contact.",
  visual_notes: "Show the radar log on screen.",
  source_citation: "AARO, report, 2024-03-01",
  story_summary: "A radar contact goes unexplained.",
  document: {
    id: "doc-1",
    title: "AARO 2024 Annual Report",
    agency: "AARO",
    doc_type: "report",
    published_date: "2024-03-01",
    source_url: null,
  },
  platform_versions: [
    { id: "pv-tiktok", platform: "tiktok", content: "{}", status: "pending_review" },
  ],
};

function script(approved: boolean): api.PendingScript {
  return {
    id: "chapter-1",
    title: "Part 1",
    script: "A pilot reported an unidentified radar contact.",
    visual_notes: "Show the radar log on screen.",
    source_citation: "AARO, report, 2024-03-01",
    script_approved: approved,
    script_approved_at: approved ? "2026-09-06T10:00:00Z" : null,
    created_at: "2026-09-06T09:00:00Z",
    word_count: 7,
  };
}

const spanishTrack: api.SubtitleTrack = {
  lang: "es",
  edited: false,
  updated_at: null,
  segments: [{ index: 1, start: "00:00:00,000", end: "00:00:02,000", text: "Primera." }],
};

beforeEach(() => {
  jest.resetAllMocks();
  mockedApi.fetchPendingChapters.mockResolvedValue([chapter]);
  mockedApi.fetchCheckpointSummary.mockResolvedValue({ pending: 0, failed: 0 });
  mockedApi.fetchSourceUrls.mockResolvedValue([]);
  mockedApi.fetchSubtitles.mockResolvedValue([]);
  mockedApi.fetchChapterVideos.mockResolvedValue([]);
});

async function openPreview() {
  render(<PipelineFeed />);
  await waitFor(() =>
    expect(screen.getByText("AARO 2024 Annual Report")).toBeInTheDocument(),
  );
  await userEvent.click(screen.getByRole("button", { name: "Vista previa" }));
}

test("shows the script review section for a chapter that has one", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([script(false)]);

  await openPreview();

  expect(screen.getByTestId("script-card-chapter-1")).toBeInTheDocument();
  expect(screen.getByText("Guion pendiente")).toBeInTheDocument();
});

test("omits the script section when no script matches the chapter", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([]);

  await openPreview();

  expect(screen.queryByTestId("script-card-chapter-1")).not.toBeInTheDocument();
});

test("approving from the feed updates the stamp in place", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([script(false)]);
  mockedApi.approveScript.mockResolvedValue({
    chapter_id: "chapter-1",
    script_approved: true,
    script_approved_at: "2026-09-06T12:00:00Z",
    platform_versions_updated: 4,
  });

  await openPreview();
  await userEvent.click(screen.getByRole("button", { name: "Aprobar guion" }));

  await waitFor(() => expect(screen.getByText("Guion aprobado")).toBeInTheDocument());
  expect(mockedApi.approveScript).toHaveBeenCalledWith("chapter-1");
});

test("hides subtitles until the script is approved", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([script(false)]);

  await openPreview();

  expect(screen.queryByTestId("subtitles-chapter-1")).not.toBeInTheDocument();
});

test("shows subtitles once the script is approved", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([script(true)]);

  await openPreview();

  expect(screen.getByTestId("subtitles-chapter-1")).toBeInTheDocument();
});

test("fetches subtitles lazily, once, on first expand", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([script(true)]);
  mockedApi.fetchSubtitles.mockResolvedValue([spanishTrack]);

  render(<PipelineFeed />);
  await waitFor(() =>
    expect(screen.getByText("AARO 2024 Annual Report")).toBeInTheDocument(),
  );
  // Nothing fetched while the card is collapsed.
  expect(mockedApi.fetchSubtitles).not.toHaveBeenCalled();

  await userEvent.click(screen.getByRole("button", { name: "Vista previa" }));
  await waitFor(() => expect(mockedApi.fetchSubtitles).toHaveBeenCalledWith("chapter-1"));

  await userEvent.click(screen.getByRole("button", { name: "Ocultar guion" }));
  await userEvent.click(screen.getByRole("button", { name: "Vista previa" }));

  expect(mockedApi.fetchSubtitles).toHaveBeenCalledTimes(1);
});

test("generating subtitles renders the returned tracks", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([script(true)]);
  mockedApi.generateSubtitles.mockResolvedValue([spanishTrack]);

  await openPreview();
  await userEvent.click(screen.getByRole("button", { name: "Generar subtítulos" }));

  await waitFor(() =>
    expect(screen.getByLabelText("Subtítulos en Español")).toBeInTheDocument(),
  );
});

test("a 409 from generation shows the server's reason", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([script(true)]);
  mockedApi.generateSubtitles.mockRejectedValue(
    new api.ApiError(
      'POST /chapters/chapter-1/subtitles/generate failed (409): {"detail": "Script must be approved before subtitle generation."}',
      409,
    ),
  );

  await openPreview();
  await userEvent.click(screen.getByRole("button", { name: "Generar subtítulos" }));

  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent(/Script must be approved/),
  );
});

test("saving an edited subtitle track replaces only that language", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([script(true)]);
  mockedApi.fetchSubtitles.mockResolvedValue([spanishTrack]);
  mockedApi.updateSubtitleTrack.mockResolvedValue({
    ...spanishTrack,
    edited: true,
    segments: [{ ...spanishTrack.segments[0], text: "Corregida." }],
  });

  await openPreview();
  await waitFor(() =>
    expect(screen.getByLabelText("Subtítulos en Español")).toBeInTheDocument(),
  );

  await userEvent.click(screen.getByRole("button", { name: "Editar Español" }));
  const field = screen.getByLabelText("00:00:00,000 → 00:00:02,000");
  await userEvent.clear(field);
  await userEvent.type(field, "Corregida.");
  await userEvent.click(screen.getByRole("button", { name: "Guardar Español" }));

  await waitFor(() =>
    expect(mockedApi.updateSubtitleTrack).toHaveBeenCalledWith("chapter-1", "es", [
      { index: 1, text: "Corregida." },
    ]),
  );
  const section = screen.getByLabelText("Subtítulos en Español");
  expect(within(section).getByText("Editado")).toBeInTheDocument();
});

test("the feed still renders when the script layer fails to load", async () => {
  // Degrading to "no review section" is better than blanking the pipeline.
  mockedApi.fetchPendingScripts.mockRejectedValue(new Error("boom"));

  await openPreview();

  expect(screen.getByText("AARO 2024 Annual Report")).toBeInTheDocument();
  expect(screen.queryByTestId("script-card-chapter-1")).not.toBeInTheDocument();
});
