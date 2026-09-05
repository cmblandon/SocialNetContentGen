import { render, screen, waitFor } from "@testing-library/react";
import Calendar from "@/components/Calendar";
import * as api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

const publishedRecord: api.PublishRecord = {
  id: "pr-1",
  platform_version_id: "pv-1",
  platform: "tiktok",
  status: "published",
  external_post_id: "postiz-123",
  scheduled_at: "2026-09-05T18:00:00+00:00",
  published_at: "2026-09-05T18:00:05+00:00",
  error_message: null,
};

const failedRecord: api.PublishRecord = {
  id: "pr-2",
  platform_version_id: "pv-2",
  platform: "x",
  status: "failed",
  external_post_id: null,
  scheduled_at: "2026-09-05T19:00:00+00:00",
  published_at: null,
  error_message: "account limit reached",
};

beforeEach(() => {
  jest.resetAllMocks();
});

test("lists published/scheduled items by network and time", async () => {
  mockedApi.fetchPublishRecords.mockResolvedValue([publishedRecord, failedRecord]);

  render(<Calendar />);

  await waitFor(() => expect(screen.getByText(/tiktok/i)).toBeInTheDocument());
  expect(screen.getByText(/2026-09-05T18:00:00\+00:00/)).toBeInTheDocument();
  expect(screen.getByText(/postiz-123/)).toBeInTheDocument();
  expect(screen.getByText(/x/i)).toBeInTheDocument();
  expect(screen.getByText(/account limit reached/)).toBeInTheDocument();
});

test("shows an empty state when nothing has been published or scheduled", async () => {
  mockedApi.fetchPublishRecords.mockResolvedValue([]);

  render(<Calendar />);

  await waitFor(() => expect(screen.getByText(/nothing published or scheduled/i)).toBeInTheDocument());
});
