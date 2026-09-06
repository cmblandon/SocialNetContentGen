import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SourceUrlManager from "@/components/SourceUrlManager";
import * as api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

beforeEach(() => {
  jest.resetAllMocks();
});

test("lists the currently configured source URLs", async () => {
  mockedApi.fetchSourceUrls.mockResolvedValue(["https://www.aaro.mil/reports/2024.pdf"]);

  render(<SourceUrlManager />);

  await waitFor(() =>
    expect(screen.getByText("https://www.aaro.mil/reports/2024.pdf")).toBeInTheDocument()
  );
});

test("shows an empty state when no source URLs are configured", async () => {
  mockedApi.fetchSourceUrls.mockResolvedValue([]);

  render(<SourceUrlManager />);

  await waitFor(() => expect(screen.getByText(/no hay fuentes/i)).toBeInTheDocument());
});

test("adding a URL calls the API and shows it in the list", async () => {
  mockedApi.fetchSourceUrls.mockResolvedValue([]);
  mockedApi.addSourceUrl.mockResolvedValue(["https://example.com/a"]);
  const user = userEvent.setup();

  render(<SourceUrlManager />);
  await waitFor(() => expect(screen.getByText(/no hay fuentes/i)).toBeInTheDocument());

  await user.type(screen.getByLabelText(/url/i), "https://example.com/a");
  await user.click(screen.getByRole("button", { name: /agregar/i }));

  expect(mockedApi.addSourceUrl).toHaveBeenCalledWith("https://example.com/a");
  await waitFor(() => expect(screen.getByText("https://example.com/a")).toBeInTheDocument());
});

test("removing a URL calls the API and drops it from the list", async () => {
  mockedApi.fetchSourceUrls.mockResolvedValue(["https://example.com/a"]);
  mockedApi.removeSourceUrl.mockResolvedValue([]);
  const user = userEvent.setup();

  render(<SourceUrlManager />);
  await waitFor(() => expect(screen.getByText("https://example.com/a")).toBeInTheDocument());

  await user.click(screen.getByRole("button", { name: /eliminar/i }));

  expect(mockedApi.removeSourceUrl).toHaveBeenCalledWith("https://example.com/a");
  await waitFor(() => expect(screen.queryByText("https://example.com/a")).not.toBeInTheDocument());
});
