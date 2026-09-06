import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SubtitleReviewCard from "@/components/SubtitleReviewCard";
import type { SubtitleTrack } from "@/lib/api";

const spanish: SubtitleTrack = {
  lang: "es",
  edited: false,
  updated_at: "2026-09-06T10:00:00Z",
  segments: [
    { index: 1, start: "00:00:00,000", end: "00:00:02,000", text: "Primera frase." },
    { index: 2, start: "00:00:02,000", end: "00:00:04,000", text: "Segunda frase." },
  ],
};

const english: SubtitleTrack = {
  lang: "en",
  edited: true,
  updated_at: "2026-09-06T11:00:00Z",
  segments: [
    { index: 1, start: "00:00:00,000", end: "00:00:02,000", text: "First sentence." },
    { index: 2, start: "00:00:02,000", end: "00:00:04,000", text: "Second sentence." },
  ],
};

function renderCard(overrides: Partial<React.ComponentProps<typeof SubtitleReviewCard>> = {}) {
  const onGenerate = jest.fn();
  const onSave = jest.fn();
  render(
    <SubtitleReviewCard
      chapterId="chapter-1"
      scriptApproved
      tracks={[spanish, english]}
      onGenerate={onGenerate}
      onSave={onSave}
      {...overrides}
    />,
  );
  return { onGenerate, onSave };
}

test("offers generation when no subtitles exist yet", () => {
  const { onGenerate } = renderCard({ tracks: null });

  const button = screen.getByRole("button", { name: "Generar subtítulos" });
  expect(button).toBeEnabled();

  button.click();
  expect(onGenerate).toHaveBeenCalledWith("chapter-1");
});

test("blocks generation until the script is approved", () => {
  renderCard({ tracks: null, scriptApproved: false });

  expect(screen.getByRole("button", { name: "Generar subtítulos" })).toBeDisabled();
  expect(screen.getByText(/Aprueba el guion/)).toBeInTheDocument();
});

test("renders both languages with their timings", () => {
  renderCard();

  const spanishSection = screen.getByLabelText("Subtítulos en Español");
  expect(within(spanishSection).getByText(/Primera frase\./)).toBeInTheDocument();
  expect(within(spanishSection).getByText("00:00:00,000 → 00:00:02,000")).toBeInTheDocument();

  const englishSection = screen.getByLabelText("Subtítulos en Inglés");
  expect(within(englishSection).getByText(/First sentence\./)).toBeInTheDocument();
});

test("marks a track that an editor has already corrected", () => {
  renderCard();

  const englishSection = screen.getByLabelText("Subtítulos en Inglés");
  expect(within(englishSection).getByText("Editado")).toBeInTheDocument();

  const spanishSection = screen.getByLabelText("Subtítulos en Español");
  expect(within(spanishSection).queryByText("Editado")).not.toBeInTheDocument();
});

test("language toggle narrows to a single track and back", async () => {
  renderCard();

  await userEvent.click(screen.getByRole("button", { name: "Inglés" }));
  expect(screen.queryByLabelText("Subtítulos en Español")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Subtítulos en Inglés")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Ambos" }));
  expect(screen.getByLabelText("Subtítulos en Español")).toBeInTheDocument();
});

test("editing exposes text fields but never the timings", async () => {
  renderCard();

  await userEvent.click(screen.getByRole("button", { name: "Editar Español" }));

  const first = screen.getByLabelText("00:00:00,000 → 00:00:02,000");
  expect(first).toHaveValue("Primera frase.");
  // The timecode is a label, not an input: the API preserves timing, so
  // offering to edit it would promise something it will not do.
  expect(screen.queryByRole("textbox", { name: /00:00:00,000$/ })).not.toBeInTheDocument();
  expect(screen.getByText(/Los tiempos no se modifican/)).toBeInTheDocument();
});

test("saving sends every segment in order with its original index", async () => {
  const { onSave } = renderCard();

  await userEvent.click(screen.getByRole("button", { name: "Editar Español" }));
  const first = screen.getByLabelText("00:00:00,000 → 00:00:02,000");
  await userEvent.clear(first);
  await userEvent.type(first, "Corregida.");
  await userEvent.click(screen.getByRole("button", { name: "Guardar Español" }));

  expect(onSave).toHaveBeenCalledWith("chapter-1", "es", [
    { index: 1, text: "Corregida." },
    { index: 2, text: "Segunda frase." },
  ]);
});

test("saving is blocked while any segment is blank", async () => {
  renderCard();

  await userEvent.click(screen.getByRole("button", { name: "Editar Español" }));
  await userEvent.clear(screen.getByLabelText("00:00:00,000 → 00:00:02,000"));

  // Mirrors the API's 422 rather than letting the request fail.
  expect(screen.getByRole("button", { name: "Guardar Español" })).toBeDisabled();
});

test("cancelling an edit discards the draft", async () => {
  const { onSave } = renderCard();

  await userEvent.click(screen.getByRole("button", { name: "Editar Español" }));
  await userEvent.clear(screen.getByLabelText("00:00:00,000 → 00:00:02,000"));
  await userEvent.type(screen.getByLabelText("00:00:00,000 → 00:00:02,000"), "descartar");
  await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));

  expect(onSave).not.toHaveBeenCalled();
  expect(screen.getByText(/Primera frase\./)).toBeInTheDocument();
});

test("surfaces an error from the parent", () => {
  renderCard({ error: "Script must be approved before subtitle generation." });

  expect(screen.getByRole("alert")).toHaveTextContent(/Script must be approved/);
});
