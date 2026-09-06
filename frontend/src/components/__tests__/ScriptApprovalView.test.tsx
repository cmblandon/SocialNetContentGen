import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ScriptApprovalView from "@/components/ScriptApprovalView";
import * as api from "@/lib/api";

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return {
    __esModule: true,
    ...actual,
    fetchPendingScripts: jest.fn(),
    approveScript: jest.fn(),
    rejectScript: jest.fn(),
    updateScript: jest.fn(),
  };
});
const mockedApi = api as jest.Mocked<typeof api>;

const pendingScript: api.PendingScript = {
  id: "chapter-1",
  title: "Contacto de radar",
  script: "Primera frase del guion. Segunda frase del guion.",
  visual_notes: "material de archivo de radar militar",
  source_citation: "AARO, report, 2024-03-01",
  script_approved: false,
  script_approved_at: null,
  created_at: "2026-09-06T10:00:00Z",
  word_count: 8,
};

const approvedScript: api.PendingScript = {
  ...pendingScript,
  id: "chapter-2",
  title: "Segunda parte",
  visual_notes: "documento desclasificado en pantalla",
  source_citation: "CIA, memo, 1985-02-01",
  script_approved: true,
  script_approved_at: "2026-09-06T11:00:00Z",
  word_count: 12,
};

function actionResult(approved: boolean): api.ScriptActionResult {
  return {
    chapter_id: "chapter-1",
    script_approved: approved,
    script_approved_at: approved ? "2026-09-06T12:00:00Z" : null,
    platform_versions_updated: 4,
  };
}

beforeEach(() => {
  jest.resetAllMocks();
});

test("renders one card per pending script with its review context", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([pendingScript, approvedScript]);

  render(<ScriptApprovalView />);

  await waitFor(() => expect(screen.getByText("Contacto de radar")).toBeInTheDocument());
  expect(screen.getByText("Segunda parte")).toBeInTheDocument();
  expect(screen.getByText(/material de archivo de radar militar/)).toBeInTheDocument();
  expect(screen.getByText("AARO, report, 2024-03-01")).toBeInTheDocument();
  expect(screen.getByText("8 palabras")).toBeInTheDocument();
});

test("shows an approved stamp only for approved scripts", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([pendingScript, approvedScript]);

  render(<ScriptApprovalView />);

  await waitFor(() => expect(screen.getByText("Guion aprobado")).toBeInTheDocument());
  expect(screen.getByText("Guion pendiente")).toBeInTheDocument();
});

test("offers approve for a pending script and reject for an approved one", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([pendingScript, approvedScript]);

  render(<ScriptApprovalView />);

  await waitFor(() => expect(screen.getByText("Contacto de radar")).toBeInTheDocument());
  expect(screen.getAllByRole("button", { name: "Aprobar guion" })).toHaveLength(1);
  expect(screen.getAllByRole("button", { name: "Rechazar guion" })).toHaveLength(1);
});

test("approving updates the card without refetching the whole list", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([pendingScript]);
  mockedApi.approveScript.mockResolvedValue(actionResult(true));

  render(<ScriptApprovalView />);
  await waitFor(() => expect(screen.getByText("Contacto de radar")).toBeInTheDocument());

  await userEvent.click(screen.getByRole("button", { name: "Aprobar guion" }));

  await waitFor(() => expect(screen.getByText("Guion aprobado")).toBeInTheDocument());
  expect(mockedApi.approveScript).toHaveBeenCalledWith("chapter-1");
  expect(mockedApi.fetchPendingScripts).toHaveBeenCalledTimes(1);
});

test("surfaces the server's reason when approval conflicts", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([pendingScript]);
  mockedApi.approveScript.mockRejectedValue(
    new api.ApiError(
      'POST /chapters/chapter-1/script/approve failed (409): {"detail": "Chapter chapter-1 has no platform versions, so its script approval cannot be recorded."}',
      409,
    ),
  );

  render(<ScriptApprovalView />);
  await waitFor(() => expect(screen.getByText("Contacto de radar")).toBeInTheDocument());

  await userEvent.click(screen.getByRole("button", { name: "Aprobar guion" }));

  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent(/no platform versions/),
  );
  expect(screen.getByText("Guion pendiente")).toBeInTheDocument();
});

test("search filters cards by title and citation", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([pendingScript, approvedScript]);

  render(<ScriptApprovalView />);
  await waitFor(() => expect(screen.getByText("Contacto de radar")).toBeInTheDocument());

  await userEvent.type(screen.getByLabelText("Buscar"), "CIA");

  expect(screen.queryByText("Contacto de radar")).not.toBeInTheDocument();
  expect(screen.getByText("Segunda parte")).toBeInTheDocument();
});

test("editing warns that saving resets approval, before saving", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([approvedScript]);

  render(<ScriptApprovalView />);
  await waitFor(() => expect(screen.getByText("Segunda parte")).toBeInTheDocument());

  await userEvent.click(screen.getByRole("button", { name: "Editar" }));

  expect(screen.getByRole("note")).toHaveTextContent(/reiniciará la aprobación/);
});

test("shows live word and character counts while editing", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([pendingScript]);

  render(<ScriptApprovalView />);
  await waitFor(() => expect(screen.getByText("Contacto de radar")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: "Editar" }));

  const textarea = screen.getByLabelText("Guion");
  await userEvent.clear(textarea);
  await userEvent.type(textarea, "una dos tres");

  expect(screen.getByText(/3 palabras · 12 caracteres/)).toBeInTheDocument();
});

test("saving an edit sends the new text and flips the stamp back to pending", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([approvedScript]);
  mockedApi.updateScript.mockResolvedValue({
    chapter_id: "chapter-2",
    script_approved: false,
    script_approved_at: null,
    platform_versions_updated: 4,
  });

  render(<ScriptApprovalView />);
  await waitFor(() => expect(screen.getByText("Segunda parte")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: "Editar" }));

  const textarea = screen.getByLabelText("Guion");
  await userEvent.clear(textarea);
  await userEvent.type(textarea, "texto corregido");
  await userEvent.click(screen.getByRole("button", { name: "Guardar" }));

  await waitFor(() =>
    expect(mockedApi.updateScript).toHaveBeenCalledWith("chapter-2", "texto corregido"),
  );
  expect(screen.getByText("Guion pendiente")).toBeInTheDocument();
});

test("saving is blocked while the draft is blank", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([pendingScript]);

  render(<ScriptApprovalView />);
  await waitFor(() => expect(screen.getByText("Contacto de radar")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: "Editar" }));
  await userEvent.clear(screen.getByLabelText("Guion"));

  expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled();
});

test("bulk approve calls approve for every selected pending script", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([pendingScript, approvedScript]);
  mockedApi.approveScript.mockResolvedValue(actionResult(true));

  render(<ScriptApprovalView />);
  await waitFor(() => expect(screen.getByText("Contacto de radar")).toBeInTheDocument());

  await userEvent.click(screen.getByLabelText("Seleccionar Contacto de radar"));
  await userEvent.click(screen.getByRole("button", { name: "Aprobar seleccionados" }));

  await waitFor(() => expect(mockedApi.approveScript).toHaveBeenCalledWith("chapter-1"));
  expect(mockedApi.approveScript).toHaveBeenCalledTimes(1);
});

test("bulk approve skips already-approved selections", async () => {
  mockedApi.fetchPendingScripts.mockResolvedValue([approvedScript]);

  render(<ScriptApprovalView />);
  await waitFor(() => expect(screen.getByText("Segunda parte")).toBeInTheDocument());

  await userEvent.click(screen.getByLabelText("Seleccionar Segunda parte"));
  await userEvent.click(screen.getByRole("button", { name: "Aprobar seleccionados" }));

  await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument());
  expect(mockedApi.approveScript).not.toHaveBeenCalled();
});

test("reports a load failure instead of rendering an empty queue", async () => {
  mockedApi.fetchPendingScripts.mockRejectedValue(new Error("boom"));

  render(<ScriptApprovalView />);

  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudieron cargar los guiones."),
  );
});
