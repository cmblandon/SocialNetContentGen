import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import VideoGenerationCard, {
  MAX_POLL_ATTEMPTS,
  POLL_INTERVAL_MS,
} from "@/components/VideoGenerationCard";
import type { VideoGeneration } from "@/lib/api";

function video(overrides: Partial<VideoGeneration> = {}): VideoGeneration {
  return {
    id: "vg-1",
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

function renderCard(
  overrides: Partial<React.ComponentProps<typeof VideoGenerationCard>> = {},
) {
  const onGenerate = jest.fn();
  const onRetry = jest.fn();
  const onPoll = jest.fn();
  const result = render(
    <VideoGenerationCard
      chapterId="chapter-1"
      scriptApproved
      videos={null}
      onGenerate={onGenerate}
      onRetry={onRetry}
      onPoll={onPoll}
      {...overrides}
    />,
  );
  return { onGenerate, onRetry, onPoll, ...result };
}

test("blocks generation until the script is approved", () => {
  renderCard({ scriptApproved: false });

  expect(screen.getByRole("button", { name: "Generar video" })).toBeDisabled();
  expect(screen.getByText(/Aprueba el guion/)).toBeInTheDocument();
});

test("generates for all platforms in Spanish by default", async () => {
  const { onGenerate } = renderCard();

  await userEvent.click(screen.getByRole("button", { name: "Generar video" }));

  expect(onGenerate).toHaveBeenCalledWith("chapter-1", {
    platforms: ["tiktok", "instagram", "facebook", "x"],
    languages: ["es"],
  });
});

test("honours platform and language selection", async () => {
  const { onGenerate } = renderCard();

  await userEvent.click(screen.getByLabelText("instagram"));
  await userEvent.click(screen.getByLabelText("facebook"));
  await userEvent.click(screen.getByLabelText("x"));
  await userEvent.click(screen.getByLabelText("Inglés"));
  await userEvent.click(screen.getByRole("button", { name: "Generar video" }));

  expect(onGenerate).toHaveBeenCalledWith("chapter-1", {
    platforms: ["tiktok"],
    languages: ["es", "en"],
  });
});

test("refuses to submit an empty platform or language selection", async () => {
  renderCard();

  for (const platform of ["tiktok", "instagram", "facebook", "x"]) {
    await userEvent.click(screen.getByLabelText(platform));
  }

  expect(screen.getByRole("button", { name: "Generar video" })).toBeDisabled();
});

test("renders one row per video with its status", () => {
  renderCard({
    videos: [
      video({ id: "a", status: "generated" }),
      video({ id: "b", platform: "instagram", status: "pending", size_mb: null }),
      video({ id: "c", platform: "x", status: "failed", error_message: "tts step failed" }),
    ],
  });

  expect(screen.getByText("Listo")).toBeInTheDocument();
  expect(screen.getByText("Generando…")).toBeInTheDocument();
  expect(screen.getByText("Falló")).toBeInTheDocument();
  expect(screen.getByText("tts step failed")).toBeInTheDocument();
});

test("offers retry only on failed rows", () => {
  renderCard({
    videos: [video({ id: "a", status: "generated" }), video({ id: "b", status: "failed" })],
  });

  expect(screen.getAllByRole("button", { name: "Reintentar" })).toHaveLength(1);
});

test("retrying passes the specific generation id", async () => {
  const { onRetry } = renderCard({ videos: [video({ id: "b", status: "failed" })] });

  await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));

  expect(onRetry).toHaveBeenCalledWith("chapter-1", "b");
});

test("plays and downloads through the file endpoint, not the server path", async () => {
  renderCard({ videos: [video()] });

  const download = screen.getByRole("link", { name: "Descargar" });
  expect(download).toHaveAttribute("href", expect.stringContaining("/videos/vg-1/file"));
  // The stored path is a server filesystem location and must never be a src.
  expect(download.getAttribute("href")).not.toContain("data/videos_generated");

  await userEvent.click(screen.getByRole("button", { name: "Ver" }));
  expect(screen.getByTestId("player-vg-1")).toHaveAttribute(
    "src",
    expect.stringContaining("/videos/vg-1/file"),
  );
});

test("distinguishes a generated file that is missing on disk", () => {
  renderCard({ videos: [video({ size_mb: null })] });

  expect(screen.getByText("Archivo faltante en disco")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Ver" })).toBeInTheDocument();
});

describe("polling", () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  test("polls while a row is pending", () => {
    const { onPoll } = renderCard({ videos: [video({ status: "pending" })] });

    act(() => {
      jest.advanceTimersByTime(POLL_INTERVAL_MS);
    });

    expect(onPoll).toHaveBeenCalledWith("chapter-1");
  });

  test("does not poll when nothing is pending", () => {
    const { onPoll } = renderCard({ videos: [video({ status: "generated" })] });

    act(() => {
      jest.advanceTimersByTime(POLL_INTERVAL_MS * 3);
    });

    expect(onPoll).not.toHaveBeenCalled();
  });

  test("stops polling once the row leaves pending", () => {
    const onPoll = jest.fn();
    const { rerender } = render(
      <VideoGenerationCard
        chapterId="chapter-1"
        scriptApproved
        videos={[video({ status: "pending" })]}
        onGenerate={jest.fn()}
        onRetry={jest.fn()}
        onPoll={onPoll}
      />,
    );

    act(() => {
      jest.advanceTimersByTime(POLL_INTERVAL_MS);
    });
    expect(onPoll).toHaveBeenCalledTimes(1);

    rerender(
      <VideoGenerationCard
        chapterId="chapter-1"
        scriptApproved
        videos={[video({ status: "generated" })]}
        onGenerate={jest.fn()}
        onRetry={jest.fn()}
        onPoll={onPoll}
      />,
    );
    act(() => {
      jest.advanceTimersByTime(POLL_INTERVAL_MS * 5);
    });

    expect(onPoll).toHaveBeenCalledTimes(1);
  });

  test("stops polling on unmount", () => {
    const { onPoll, unmount } = renderCard({ videos: [video({ status: "pending" })] });

    act(() => {
      jest.advanceTimersByTime(POLL_INTERVAL_MS);
    });
    unmount();
    act(() => {
      jest.advanceTimersByTime(POLL_INTERVAL_MS * 5);
    });

    expect(onPoll).toHaveBeenCalledTimes(1);
  });

  test("gives up after the cap and offers a manual refresh", () => {
    const { onPoll } = renderCard({ videos: [video({ status: "pending" })] });

    act(() => {
      jest.advanceTimersByTime(POLL_INTERVAL_MS * MAX_POLL_ATTEMPTS);
    });

    expect(screen.getByRole("status")).toHaveTextContent(/tardando más de lo esperado/);
    const callsAtCap = onPoll.mock.calls.length;

    act(() => {
      jest.advanceTimersByTime(POLL_INTERVAL_MS * 10);
    });
    expect(onPoll).toHaveBeenCalledTimes(callsAtCap);
  });

  test("manual refresh resumes polling after the cap", () => {
    const { onPoll } = renderCard({ videos: [video({ status: "pending" })] });

    act(() => {
      jest.advanceTimersByTime(POLL_INTERVAL_MS * MAX_POLL_ATTEMPTS);
    });
    const callsAtCap = onPoll.mock.calls.length;

    act(() => {
      screen.getByRole("button", { name: "Actualizar estado" }).click();
    });

    expect(onPoll).toHaveBeenCalledTimes(callsAtCap + 1);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    act(() => {
      jest.advanceTimersByTime(POLL_INTERVAL_MS);
    });
    expect(onPoll).toHaveBeenCalledTimes(callsAtCap + 2);
  });
});
