import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ApprovalQueue from "@/components/ApprovalQueue";
import * as api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

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
    { id: "pv-tiktok", platform: "tiktok", content: "TikTok script", status: "pending_review" },
    { id: "pv-instagram", platform: "instagram", content: "Carousel content", status: "pending_review" },
    { id: "pv-x", platform: "x", content: "Thread content", status: "pending_review" },
    { id: "pv-facebook", platform: "facebook", content: "Facebook post", status: "pending_review" },
  ],
};

beforeEach(() => {
  jest.resetAllMocks();
});

test("shows the source document, story summary, chapter script, and all platform versions", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([pendingChapter]);

  render(<ApprovalQueue />);

  await waitFor(() => expect(screen.getByText("AARO 2024 Annual Report")).toBeInTheDocument());
  expect(screen.getByText(/AARO — report — 2024-03-01/)).toBeInTheDocument();
  expect(screen.getByText("A radar contact goes unexplained.")).toBeInTheDocument();
  expect(screen.getByText("A pilot reported an unidentified radar contact.")).toBeInTheDocument();
  expect(screen.getByText("TikTok script")).toBeInTheDocument();
  expect(screen.getByText("Carousel content")).toBeInTheDocument();
  expect(screen.getByText("Thread content")).toBeInTheDocument();
  expect(screen.getByText("Facebook post")).toBeInTheDocument();
});

test("shows an empty state when nothing is pending", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([]);

  render(<ApprovalQueue />);

  await waitFor(() => expect(screen.getByText(/nothing pending/i)).toBeInTheDocument());
});

test("approving a platform version calls the API and removes it from the queue", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([pendingChapter]);
  mockedApi.approvePlatformVersion.mockResolvedValue({
    id: "pv-tiktok",
    status: "approved",
    publish_outcome: { published: false, external_post_id: null, error_message: null, proposed_time: "12:00" },
  });
  const user = userEvent.setup();

  render(<ApprovalQueue />);
  await waitFor(() => expect(screen.getByText("TikTok script")).toBeInTheDocument());

  await user.click(screen.getByRole("button", { name: /approve tiktok/i }));

  expect(mockedApi.approvePlatformVersion).toHaveBeenCalledWith("pv-tiktok");
  await waitFor(() =>
    expect(screen.queryByRole("button", { name: /approve tiktok/i })).not.toBeInTheDocument()
  );
});

test("rejecting a platform version calls the API and removes it from the queue", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([pendingChapter]);
  mockedApi.rejectPlatformVersion.mockResolvedValue({ id: "pv-x", status: "rejected" });
  const user = userEvent.setup();

  render(<ApprovalQueue />);
  await waitFor(() => expect(screen.getByText("Thread content")).toBeInTheDocument());

  await user.click(screen.getByRole("button", { name: /reject x/i }));

  expect(mockedApi.rejectPlatformVersion).toHaveBeenCalledWith("pv-x");
  await waitFor(() =>
    expect(screen.queryByRole("button", { name: /reject x/i })).not.toBeInTheDocument()
  );
});

test("shows the publish outcome after approving", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([pendingChapter]);
  mockedApi.approvePlatformVersion.mockResolvedValue({
    id: "pv-tiktok",
    status: "approved",
    publish_outcome: { published: true, external_post_id: "postiz-123", error_message: null, proposed_time: null },
  });
  const user = userEvent.setup();

  render(<ApprovalQueue />);
  await waitFor(() => expect(screen.getByText("TikTok script")).toBeInTheDocument());
  await user.click(screen.getByRole("button", { name: /approve tiktok/i }));

  await waitFor(() => expect(screen.getByText(/postiz-123/)).toBeInTheDocument());
});
