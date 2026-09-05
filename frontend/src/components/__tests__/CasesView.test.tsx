import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CasesView from "@/components/CasesView";
import * as api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

const caseA: api.CaseEntry = {
  id: "1",
  date: "2026-09-01",
  identifier: "AARO Radar Report",
  outcome: "advanced",
  reason: "score 18/25",
};

const caseB: api.CaseEntry = {
  id: "2",
  date: "2026-09-02",
  identifier: "CIA Reading Room File",
  outcome: "discarded",
  reason: "score 9/25",
};

beforeEach(() => {
  jest.resetAllMocks();
});

test("browses all covered cases", async () => {
  mockedApi.fetchCases.mockResolvedValue([caseA, caseB]);

  render(<CasesView />);

  await waitFor(() => expect(screen.getByText("AARO Radar Report")).toBeInTheDocument());
  expect(screen.getByText("CIA Reading Room File")).toBeInTheDocument();
  expect(screen.getByText("advanced")).toBeInTheDocument();
  expect(screen.getByText("discarded")).toBeInTheDocument();
});

test("searching calls the API with the query and shows filtered results", async () => {
  mockedApi.fetchCases.mockResolvedValue([caseA, caseB]);
  const user = userEvent.setup();

  render(<CasesView />);
  await waitFor(() => expect(screen.getByText("AARO Radar Report")).toBeInTheDocument());

  mockedApi.fetchCases.mockResolvedValue([caseA]);
  await user.type(screen.getByLabelText(/search/i), "radar");
  await user.click(screen.getByRole("button", { name: /search/i }));

  await waitFor(() => expect(mockedApi.fetchCases).toHaveBeenCalledWith("radar"));
  await waitFor(() => expect(screen.queryByText("CIA Reading Room File")).not.toBeInTheDocument());
});

test("editing a case's reason calls the API and shows the updated value", async () => {
  mockedApi.fetchCases.mockResolvedValue([caseA]);
  mockedApi.updateCaseReason.mockResolvedValue({ ...caseA, reason: "corrected reason" });
  const user = userEvent.setup();

  render(<CasesView />);
  await waitFor(() => expect(screen.getByText("score 18/25")).toBeInTheDocument());

  await user.click(screen.getByRole("button", { name: /edit/i }));
  const input = screen.getByRole("textbox", { name: /reason/i });
  await user.clear(input);
  await user.type(input, "corrected reason");
  await user.click(screen.getByRole("button", { name: /save/i }));

  expect(mockedApi.updateCaseReason).toHaveBeenCalledWith("1", "corrected reason");
  await waitFor(() => expect(screen.getByText("corrected reason")).toBeInTheDocument());
});
