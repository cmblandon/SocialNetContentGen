import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import VideoLibraryView from "@/components/VideoLibraryView";
import * as api from "@/lib/api";

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return {
    __esModule: true,
    ...actual,
    fetchVideoLibrary: jest.fn(),
    fetchVideoStats: jest.fn(),
    deleteVideo: jest.fn(),
  };
});
const mockedApi = api as jest.Mocked<typeof api>;

function libraryVideo(overrides: Partial<api.LibraryVideo> = {}): api.LibraryVideo {
  return {
    id: "vg-1",
    chapter_id: "chapter-1",
    chapter_title: "Contacto de radar",
    platform_version_id: "pv-1",
    platform: "tiktok",
    language: "es",
    status: "generated",
    video_file_path: "data/videos_generated/tiktok/es/chapter-1.mp4",
    subtitle_file_path: "data/videos_generated/tiktok/es/chapter-1.srt",
    error_message: null,
    retry_of_id: null,
    created_at: "2026-09-06T10:00:00Z",
    generated_at: "2026-09-06T10:01:00Z",
    size_mb: 4.2,
    ...overrides,
  };
}

function stats(overrides: Partial<api.VideoStats> = {}): api.VideoStats {
  return {
    total_storage_mb: 12.5,
    count_by_status: { generated: 2, pending: 0, failed: 1 },
    largest_videos: [],
    missing_on_disk: 0,
    disk_free_mb: 100_000,
    disk_total_mb: 500_000,
    ...overrides,
  };
}

beforeEach(() => {
  jest.resetAllMocks();
  mockedApi.fetchVideoStats.mockResolvedValue(stats());
  jest.spyOn(window, "confirm").mockReturnValue(true);
});

afterEach(() => jest.restoreAllMocks());

test("lists videos with their metadata", async () => {
  mockedApi.fetchVideoLibrary.mockResolvedValue([libraryVideo()]);

  render(<VideoLibraryView />);

  await waitFor(() => expect(screen.getByText("Contacto de radar")).toBeInTheDocument());
  const row = screen.getByRole("row", { name: /Contacto de radar/ });
  expect(within(row).getByText("tiktok")).toBeInTheDocument();
  expect(within(row).getByText("Listo")).toBeInTheDocument();
  expect(within(row).getByText("4.2 MB")).toBeInTheDocument();
});

test("shows storage usage and free disk space", async () => {
  mockedApi.fetchVideoLibrary.mockResolvedValue([libraryVideo()]);

  render(<VideoLibraryView />);

  await waitFor(() => expect(screen.getByText(/12.5 MB/)).toBeInTheDocument());
  expect(screen.getByText(/97.7 GB de 488.3 GB/)).toBeInTheDocument();
});

test("warns when free disk space is low", async () => {
  mockedApi.fetchVideoLibrary.mockResolvedValue([libraryVideo()]);
  mockedApi.fetchVideoStats.mockResolvedValue(
    stats({ disk_free_mb: 1_000, disk_total_mb: 500_000 }),
  );

  render(<VideoLibraryView />);

  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent(/queda poco espacio/),
  );
});

test("reports unknown capacity as unknown, not as a full disk", async () => {
  mockedApi.fetchVideoLibrary.mockResolvedValue([libraryVideo()]);
  mockedApi.fetchVideoStats.mockResolvedValue(
    stats({ disk_free_mb: null, disk_total_mb: null }),
  );

  render(<VideoLibraryView />);

  await waitFor(() => expect(screen.getByText(/desconocido/)).toBeInTheDocument());
  expect(screen.queryByText(/queda poco espacio/)).not.toBeInTheDocument();
});

test("surfaces files missing on disk separately from failures", async () => {
  mockedApi.fetchVideoLibrary.mockResolvedValue([libraryVideo()]);
  mockedApi.fetchVideoStats.mockResolvedValue(stats({ missing_on_disk: 2 }));

  render(<VideoLibraryView />);

  await waitFor(() =>
    expect(screen.getByText(/2 video\(s\) marcados como listos no tienen archivo/)).toBeInTheDocument(),
  );
});

test("distinguishes a generated row whose file is gone", async () => {
  mockedApi.fetchVideoLibrary.mockResolvedValue([libraryVideo({ size_mb: null })]);

  render(<VideoLibraryView />);

  await waitFor(() => expect(screen.getByText("Archivo faltante")).toBeInTheDocument());
  // No download offered for a file that is not there.
  expect(screen.queryByRole("link", { name: "Descargar" })).not.toBeInTheDocument();
});

test("filters by platform, language and status", async () => {
  mockedApi.fetchVideoLibrary.mockResolvedValue([
    libraryVideo({ id: "a", chapter_title: "Uno", platform: "tiktok", language: "es" }),
    libraryVideo({ id: "b", chapter_title: "Dos", platform: "instagram", language: "en" }),
  ]);

  render(<VideoLibraryView />);
  await waitFor(() => expect(screen.getByText("Uno")).toBeInTheDocument());

  await userEvent.selectOptions(screen.getByLabelText("Plataforma"), "instagram");
  expect(screen.queryByText("Uno")).not.toBeInTheDocument();
  expect(screen.getByText("Dos")).toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText("Plataforma"), "");
  await userEvent.selectOptions(screen.getByLabelText("Idioma"), "es");
  expect(screen.getByText("Uno")).toBeInTheDocument();
  expect(screen.queryByText("Dos")).not.toBeInTheDocument();
});

test("filters by date range", async () => {
  mockedApi.fetchVideoLibrary.mockResolvedValue([
    libraryVideo({ id: "a", chapter_title: "Viejo", created_at: "2026-01-01T00:00:00Z" }),
    libraryVideo({ id: "b", chapter_title: "Nuevo", created_at: "2026-09-06T00:00:00Z" }),
  ]);

  render(<VideoLibraryView />);
  await waitFor(() => expect(screen.getByText("Viejo")).toBeInTheDocument());

  await userEvent.type(screen.getByLabelText("Desde"), "2026-06-01");

  expect(screen.queryByText("Viejo")).not.toBeInTheDocument();
  expect(screen.getByText("Nuevo")).toBeInTheDocument();
});

test("downloads through the file endpoint, never the server path", async () => {
  mockedApi.fetchVideoLibrary.mockResolvedValue([libraryVideo()]);

  render(<VideoLibraryView />);
  await waitFor(() => expect(screen.getByText("Contacto de radar")).toBeInTheDocument());

  const link = screen.getByRole("link", { name: "Descargar" });
  expect(link.getAttribute("href")).toContain("/videos/vg-1/file");
  expect(link.getAttribute("href")).not.toContain("data/videos_generated");
});

test("download all only counts rows that actually have a file", async () => {
  mockedApi.fetchVideoLibrary.mockResolvedValue([
    libraryVideo({ id: "a" }),
    libraryVideo({ id: "b", status: "failed", size_mb: null }),
    libraryVideo({ id: "c", size_mb: null }),
  ]);

  render(<VideoLibraryView />);

  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Descargar todos (1)" })).toBeEnabled(),
  );
});

test("deleting removes the row and refreshes stats", async () => {
  mockedApi.fetchVideoLibrary.mockResolvedValue([libraryVideo()]);
  mockedApi.deleteVideo.mockResolvedValue({
    video_generation_id: "vg-1",
    video_file_deleted: true,
    subtitle_file_deleted: true,
    video_file_retained_reason: null,
    subtitle_file_retained_reason: null,
  });

  render(<VideoLibraryView />);
  await waitFor(() => expect(screen.getByText("Contacto de radar")).toBeInTheDocument());

  await userEvent.click(screen.getByRole("button", { name: "Eliminar" }));

  await waitFor(() => expect(mockedApi.deleteVideo).toHaveBeenCalledWith("vg-1"));
  expect(screen.queryByText("Contacto de radar")).not.toBeInTheDocument();
  expect(mockedApi.fetchVideoStats).toHaveBeenCalledTimes(2);
});

test("deleting asks for confirmation first", async () => {
  jest.spyOn(window, "confirm").mockReturnValue(false);
  mockedApi.fetchVideoLibrary.mockResolvedValue([libraryVideo()]);

  render(<VideoLibraryView />);
  await waitFor(() => expect(screen.getByText("Contacto de radar")).toBeInTheDocument());

  await userEvent.click(screen.getByRole("button", { name: "Eliminar" }));

  expect(mockedApi.deleteVideo).not.toHaveBeenCalled();
  expect(screen.getByText("Contacto de radar")).toBeInTheDocument();
});

test("reports a retained file instead of dropping the row silently", async () => {
  mockedApi.fetchVideoLibrary.mockResolvedValue([libraryVideo()]);
  mockedApi.deleteVideo.mockResolvedValue({
    video_generation_id: "vg-1",
    video_file_deleted: false,
    subtitle_file_deleted: true,
    video_file_retained_reason: "still referenced by VideoGeneration vg-2",
    subtitle_file_retained_reason: null,
  });

  render(<VideoLibraryView />);
  await waitFor(() => expect(screen.getByText("Contacto de radar")).toBeInTheDocument());

  await userEvent.click(screen.getByRole("button", { name: "Eliminar" }));

  await waitFor(() =>
    expect(screen.getByRole("status")).toHaveTextContent(/still referenced by VideoGeneration vg-2/),
  );
});

test("reports a load failure rather than showing an empty library", async () => {
  mockedApi.fetchVideoLibrary.mockRejectedValue(new Error("boom"));

  render(<VideoLibraryView />);

  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo cargar la videoteca."),
  );
});
