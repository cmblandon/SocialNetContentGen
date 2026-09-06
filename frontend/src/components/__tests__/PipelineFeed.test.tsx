import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PipelineFeed from "@/components/PipelineFeed";
import * as api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

function tiktokContent(hashtags: string[] = ["#a", "#b", "#c"]) {
  return JSON.stringify({
    script: "TikTok script",
    on_screen_hook_lines: ["a", "b"],
    hashtags,
    description: "d",
  });
}

const pendingChapter: api.PendingChapter = {
  id: "chapter-1",
  title: "Part 1: The Radar Contact",
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
    source_url: "https://www.aaro.mil/reports/2024.pdf",
  },
  platform_versions: [
    { id: "pv-tiktok", platform: "tiktok", content: tiktokContent(), status: "pending_review" },
    { id: "pv-instagram", platform: "instagram", content: "{}", status: "pending_review" },
    { id: "pv-x", platform: "x", content: "{}", status: "pending_review" },
    { id: "pv-facebook", platform: "facebook", content: "{}", status: "pending_review" },
  ],
};

const approvedChapter: api.PendingChapter = {
  ...pendingChapter,
  id: "chapter-2",
  document: { ...pendingChapter.document, id: "doc-2", title: "CIA Reading Room File" },
  platform_versions: [
    { id: "pv2-tiktok", platform: "tiktok", content: tiktokContent(), status: "published" },
    { id: "pv2-instagram", platform: "instagram", content: "{}", status: "approved" },
    { id: "pv2-x", platform: "x", content: "{}", status: "approved" },
    { id: "pv2-facebook", platform: "facebook", content: "{}", status: "rejected" },
  ],
};

beforeEach(() => {
  jest.resetAllMocks();
  mockedApi.fetchSourceUrls.mockResolvedValue(["https://www.aaro.mil/reports/2024.pdf"]);
});

test("shows the document header, hook, pending stamp, and metadata", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([pendingChapter]);

  const { container } = render(<PipelineFeed />);

  await waitFor(() => expect(screen.getByText("AARO 2024 Annual Report")).toBeInTheDocument());
  expect(screen.getByText("A radar contact goes unexplained.")).toBeInTheDocument();
  expect(container.querySelector(".stamp")?.textContent).toMatch(/pendiente/i);
  const meta = container.querySelector(".doc-meta")?.textContent ?? "";
  expect(meta).toContain("Procedencia:");
  expect(meta).toContain("AARO");
  expect(meta).toContain("report");
  expect(meta).toContain("2024-03-01");
  expect(screen.getByText("Part 1: The Radar Contact")).toBeInTheDocument();
});

test("shows the approved stamp once no platform version is still pending review", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([approvedChapter]);

  const { container } = render(<PipelineFeed />);

  await waitFor(() => expect(screen.getByText("CIA Reading Room File")).toBeInTheDocument());
  expect(container.querySelector(".stamp")?.textContent).toMatch(/aprobado/i);
});

test("expanding the preview shows the chapter script and hashtags", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([pendingChapter]);
  const user = userEvent.setup();

  render(<PipelineFeed />);
  await waitFor(() => expect(screen.getByText("AARO 2024 Annual Report")).toBeInTheDocument());

  expect(screen.queryByText("A pilot reported an unidentified radar contact.")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /vista previa/i }));

  expect(screen.getByText("A pilot reported an unidentified radar contact.")).toBeInTheDocument();
  expect(screen.getByText("#a")).toBeInTheDocument();
  expect(screen.getByText("#b")).toBeInTheDocument();
  expect(screen.getByText("#c")).toBeInTheDocument();
});

test("approving a pending case approves every one of its platform versions", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([pendingChapter]);
  mockedApi.approvePlatformVersion.mockResolvedValue({ id: "any", status: "approved" });
  const user = userEvent.setup();

  render(<PipelineFeed />);
  await waitFor(() => expect(screen.getByText("AARO 2024 Annual Report")).toBeInTheDocument());

  await user.click(screen.getByRole("button", { name: /^aprobar$/i }));

  await waitFor(() => {
    expect(mockedApi.approvePlatformVersion).toHaveBeenCalledWith("pv-tiktok");
    expect(mockedApi.approvePlatformVersion).toHaveBeenCalledWith("pv-instagram");
    expect(mockedApi.approvePlatformVersion).toHaveBeenCalledWith("pv-x");
    expect(mockedApi.approvePlatformVersion).toHaveBeenCalledWith("pv-facebook");
  });
});

test("bulk selection checkbox is disabled for a case that still has a pending platform version", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([pendingChapter]);

  render(<PipelineFeed />);
  await waitFor(() => expect(screen.getByText("AARO 2024 Annual Report")).toBeInTheDocument());

  expect(screen.getByRole("checkbox", { name: /seleccionar/i })).toBeDisabled();
});

test("bulk selection checkbox is enabled for a fully approved case", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([approvedChapter]);

  render(<PipelineFeed />);
  await waitFor(() => expect(screen.getByText("CIA Reading Room File")).toBeInTheDocument());

  expect(screen.getByRole("checkbox", { name: /seleccionar/i })).toBeEnabled();
});

test("clicking the individual Publicar action for an approved platform version publishes it", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([approvedChapter]);
  mockedApi.publishPlatformVersion.mockResolvedValue({
    published: true,
    external_post_id: "postiz-123",
    error_message: null,
    proposed_time: null,
  });
  const user = userEvent.setup();

  render(<PipelineFeed />);
  await waitFor(() => expect(screen.getByText("CIA Reading Room File")).toBeInTheDocument());

  await user.click(screen.getByRole("button", { name: /publicar en instagram/i }));

  expect(mockedApi.publishPlatformVersion).toHaveBeenCalledWith("pv2-instagram");
});

test("selecting an approved case and using the bulk bar publishes that network for every selected case", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([approvedChapter]);
  mockedApi.publishPlatformVersion.mockResolvedValue({
    published: true,
    external_post_id: "postiz-456",
    error_message: null,
    proposed_time: null,
  });
  const user = userEvent.setup();

  render(<PipelineFeed />);
  await waitFor(() => expect(screen.getByText("CIA Reading Room File")).toBeInTheDocument());

  await user.click(screen.getByRole("checkbox", { name: /seleccionar/i }));

  const bulkBar = screen.getByTestId("bulk-bar");
  await user.click(within(bulkBar).getByRole("button", { name: /publicar en instagram/i }));

  expect(mockedApi.publishPlatformVersion).toHaveBeenCalledWith("pv2-instagram");
});

test("the run-pipeline trigger is disabled when no source URLs are configured", async () => {
  mockedApi.fetchSourceUrls.mockResolvedValue([]);
  mockedApi.fetchPendingChapters.mockResolvedValue([]);

  render(<PipelineFeed />);

  await waitFor(() => expect(screen.getByRole("button", { name: /ejecutar pipeline/i })).toBeDisabled());
});

test("the run-pipeline trigger is enabled and runs research when source URLs are configured", async () => {
  mockedApi.fetchSourceUrls.mockResolvedValue(["https://www.aaro.mil/reports/2024.pdf"]);
  mockedApi.fetchPendingChapters.mockResolvedValue([]);
  mockedApi.runResearch.mockResolvedValue({
    documents_reviewed: 1,
    stories_created: 1,
    chapters_generated: 1,
    pending_approval_platform_version_ids: ["pv-tiktok"],
    discarded_document_ids: [],
  });
  const user = userEvent.setup();

  render(<PipelineFeed />);
  await waitFor(() =>
    expect(screen.getByRole("button", { name: /ejecutar pipeline/i })).toBeEnabled()
  );

  await user.click(screen.getByRole("button", { name: /ejecutar pipeline/i }));

  expect(mockedApi.runResearch).toHaveBeenCalledWith(["https://www.aaro.mil/reports/2024.pdf"]);
});

test("renders a topic input next to the run-pipeline trigger", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([]);

  render(<PipelineFeed />);

  await waitFor(() =>
    expect(screen.getByRole("button", { name: /ejecutar pipeline/i })).toBeInTheDocument()
  );
  expect(screen.getByLabelText(/tema/i)).toBeInTheDocument();
});

test("typing a topic and running the pipeline sends it as the query", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([]);
  mockedApi.runResearch.mockResolvedValue({
    documents_reviewed: 1,
    stories_created: 1,
    chapters_generated: 1,
    pending_approval_platform_version_ids: [],
    discarded_document_ids: [],
  });
  const user = userEvent.setup();

  render(<PipelineFeed />);
  await waitFor(() =>
    expect(screen.getByRole("button", { name: /ejecutar pipeline/i })).toBeEnabled()
  );

  await user.type(screen.getByLabelText(/tema/i), "Malmstrom missile incidents");
  await user.click(screen.getByRole("button", { name: /ejecutar pipeline/i }));

  expect(mockedApi.runResearch).toHaveBeenCalledWith(
    ["https://www.aaro.mil/reports/2024.pdf"],
    "Malmstrom missile incidents"
  );
});

test("running the pipeline with a whitespace-only topic omits the query argument", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([]);
  mockedApi.runResearch.mockResolvedValue({
    documents_reviewed: 1,
    stories_created: 1,
    chapters_generated: 1,
    pending_approval_platform_version_ids: [],
    discarded_document_ids: [],
  });
  const user = userEvent.setup();

  render(<PipelineFeed />);
  await waitFor(() =>
    expect(screen.getByRole("button", { name: /ejecutar pipeline/i })).toBeEnabled()
  );

  await user.type(screen.getByLabelText(/tema/i), "   ");
  await user.click(screen.getByRole("button", { name: /ejecutar pipeline/i }));

  expect(mockedApi.runResearch).toHaveBeenCalledWith(["https://www.aaro.mil/reports/2024.pdf"]);
});
