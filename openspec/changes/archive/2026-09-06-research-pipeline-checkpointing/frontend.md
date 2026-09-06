# Frontend Implementation Plan — `research-pipeline-checkpointing` (tasks 5.1–5.3 only)

Scope: tasks 5.1–5.3 of `tasks.md` — `frontend/src/lib/api.ts`, `frontend/src/components/PipelineFeed.tsx`, its test file, and `frontend/src/app/globals.css`. Backend (sections 1–4) is already merged onto this branch; both new endpoints are live. Do not touch any backend file. Do not touch `docs/frontend-standards.md` (covered by task 6.4). Do not modify the body/assertions of any of the 13 existing tests in `PipelineFeed.test.tsx` — only add new tests, extending shared `beforeEach` setup if needed in a backward-compatible way.

Read this whole plan before starting — the ordering below **is** the TDD ordering (write the failing test, confirm it fails for the right reason, then implement to make it pass).

## Important corrections / things that would trip up someone with stale knowledge

- **This is not the React-Bootstrap/`src/services/` project.** This codebase (`frontend/`) is a Next.js 16 App Router + TypeScript project. Components are plain Client Components (`"use client"`) using `useState`/`useEffect`/`useCallback`. There is no service layer directory, no axios, no React Bootstrap. All API calls go through the single hand-written `request<T>()` helper in `frontend/src/lib/api.ts`, which wraps plain `fetch`. Styling is hand-written CSS classes in `frontend/src/app/globals.css`, not a component library. Follow this file's own conventions exactly, not generic React/Next boilerplate.
- All UI copy must be Spanish, matching this file's existing convention (`"Ejecutar pipeline"`, `"Vista previa"`, `"Aprobar"`, etc.). All code/comments/test names must be English.
- `frontend/AGENTS.md` warns this Next.js version may have breaking changes vs. training data and to check `node_modules/next/dist/docs/` before writing code — not relevant here since this task only adds a plain client-side fetch call and JSX/state to an existing Client Component; no Next.js routing/server APIs are touched.
- The repo uses Jest + React Testing Library (`npm test` inside `frontend/`), with `jest.mock("@/lib/api")` mocking the whole module. There is no MSW/network mocking — every API function used by a rendered component must have a default mock value set somewhere reachable by `beforeEach`, or the component's `useEffect` will throw on an unmocked function returning `undefined` (calling `.then` on `undefined` blows up) or produce an unhandled rejection that can make unrelated assertions flaky.
- Colors: reuse tokens already defined in `frontend/src/app/globals.css` `:root` — do not invent new colors. Relevant existing tokens: `--pending` (`#b6432f`, used today for the "Pendiente" stamp and error status pill — appropriate for "needs attention" since failed/pending checkpoints are exactly that), `--pending-soft` (`rgba(182, 67, 47, 0.14)`, a soft background tint of the same hue), `--accent` (`#c98a2e`, used for the primary `.btn-run` action and the "working" status pill), `--ink-panel-2`, `--ink-border`, `--text`, `--text-muted`.

## Baseline

Current full suite (verified before this section per the task description): **22 tests, 4 suites, all passing**. After 5.1–5.3, expect **22 + 3 = 25 tests, still 4 suites** (no new test file — all new tests are additive in the existing `PipelineFeed.test.tsx`). The 3 new tests correspond exactly to the three bullets in task 5.2. Do not treat the exact new-test count as a hard requirement if you find a natural reason to split one of the three bullets into two assertions/tests — just confirm nothing existing breaks and no existing test is removed or edited beyond the shared `beforeEach`.

---

## 5.1 — `frontend/src/lib/api.ts`: add `fetchCheckpointSummary` and `resumePipeline`

Add a new interface and two new exported functions. Place them near the other `/research/*` functions for locality (after `removeSourceUrl`, before `fetchCases`, is a reasonable spot — grouping all `/research/*` endpoints together) — exact position doesn't matter functionally, just keep related endpoints visually grouped as the file already does.

```ts
export interface CheckpointSummary {
  pending: number;
  failed: number;
}

export function fetchCheckpointSummary(): Promise<CheckpointSummary> {
  return request<CheckpointSummary>("/research/checkpoints/summary");
}

export function resumePipeline(): Promise<ResearchRunResult> {
  return request<ResearchRunResult>("/research/resume", { method: "POST" });
}
```

Notes:
- `ResearchRunResult` already exists in this file (used by `runResearch`) and has the exact same shape the backend returns from `POST /research/resume` per the task description — reuse it, do not redeclare a new interface for the resume response.
- No new imports needed. `request<T>()` already handles the `Content-Type: application/json` header, non-2xx throwing, and JSON parsing — both new functions follow the exact same call pattern as `fetchPendingChapters` (GET, no body) and `approvePlatformVersion`/`publishPlatformVersion` (POST, no body). `resumePipeline` takes no request body per the task spec, so no `body: JSON.stringify(...)` — same shape as `approvePlatformVersion(id)`'s call (`{ method: "POST" }` only).
- This is a pure additive change to the file — nothing existing is modified.

There is no dedicated `api.test.ts` in this codebase (verify this assumption before starting — if one exists, it wasn't mentioned in the task and probably just re-exercises `request()` shape indirectly through component tests; do not add one for this task since it wasn't asked for and the task's own "what to plan" section only lists `PipelineFeed.test.tsx` changes). The two new functions are exercised indirectly through the `PipelineFeed.test.tsx` tests added in 5.2 via the mocked module.

## 5.2 — Failing tests in `frontend/src/components/__tests__/PipelineFeed.test.tsx`

### Extend the shared `beforeEach` (required for the 13 existing tests to keep passing)

Current `beforeEach`:
```ts
beforeEach(() => {
  jest.resetAllMocks();
  mockedApi.fetchSourceUrls.mockResolvedValue(["https://www.aaro.mil/reports/2024.pdf"]);
});
```

Once `PipelineFeed.tsx` calls `fetchCheckpointSummary()` in its effect (task 5.3), every existing test that renders `<PipelineFeed />` will trigger that call. Since `jest.resetAllMocks()` clears all mock implementations before each test, `mockedApi.fetchCheckpointSummary` (auto-mocked as `jest.fn()` returning `undefined` by `jest.mock("@/lib/api")`) would resolve to `undefined` unless given a default — and per the 5.3 plan below, the component's `.then(setCheckpointSummary)` would then set state to `undefined`, and the `checkpointSummary && (...)` guard in JSX would just skip rendering (falsy), so no crash — but that relies on the exact implementation choice below and is fragile to rely on implicitly. Set an explicit default so the 13 existing tests are unambiguously unaffected and the new "zero counts" test's initial-state assumption is explicit rather than incidental:

```ts
beforeEach(() => {
  jest.resetAllMocks();
  mockedApi.fetchSourceUrls.mockResolvedValue(["https://www.aaro.mil/reports/2024.pdf"]);
  mockedApi.fetchCheckpointSummary.mockResolvedValue({ pending: 0, failed: 0 });
});
```

This is the "extend shared setup, don't touch existing test bodies" move the task explicitly allows. All 13 existing tests are unaffected in behavior (no banner renders under `{pending: 0, failed: 0}`, matching current DOM output exactly) — this only prevents them from exercising an unmocked function.

### New test 1 — zero counts render neither banner nor button

This is largely already covered by the `beforeEach` default, but per task 5.2 it should be an explicit assertion, not just an implicit non-regression. Add:

```ts
test("shows no checkpoint banner or resume button when nothing is pending or failed", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([]);
  // fetchCheckpointSummary defaults to { pending: 0, failed: 0 } via beforeEach

  render(<PipelineFeed />);

  await waitFor(() =>
    expect(screen.getByRole("button", { name: /ejecutar pipeline/i })).toBeInTheDocument()
  );
  expect(screen.queryByTestId("checkpoint-banner")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /reanudar pipeline/i })).not.toBeInTheDocument();
});
```

Note the `waitFor` on the "Ejecutar pipeline" button existing first — this is the existing pattern used throughout the file to let the initial effects settle before asserting on absence, avoiding a false negative from asserting too early.

### New test 2 — non-zero counts render the banner with both numbers and the resume button

```ts
test("shows a checkpoint banner with pending/failed counts and a resume button when checkpoints are outstanding", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([]);
  mockedApi.fetchCheckpointSummary.mockResolvedValue({ pending: 2, failed: 1 });

  render(<PipelineFeed />);

  const banner = await screen.findByTestId("checkpoint-banner");
  expect(banner.textContent).toContain("2");
  expect(banner.textContent).toContain("1");
  expect(screen.getByRole("button", { name: /reanudar pipeline/i })).toBeInTheDocument();
});
```

This deliberately asserts on the numbers appearing in the banner's text content rather than over-fitting to exact Spanish wording, per the task's explicit instruction. `data-testid="checkpoint-banner"` is a new test hook added in 5.3 (matching this file's existing convention of `data-testid="bulk-bar"` on the analogous `.bulk-bar` div).

### New test 3 — clicking "Reanudar pipeline" calls `resumePipeline()` and reloads the chapter feed

```ts
test("clicking the resume button calls resumePipeline and reloads the pipeline feed", async () => {
  mockedApi.fetchPendingChapters.mockResolvedValue([]);
  mockedApi.fetchCheckpointSummary.mockResolvedValue({ pending: 2, failed: 1 });
  mockedApi.resumePipeline.mockResolvedValue({
    documents_reviewed: 2,
    stories_created: 1,
    chapters_generated: 1,
    pending_approval_platform_version_ids: [],
    discarded_document_ids: [],
  });
  const user = userEvent.setup();

  render(<PipelineFeed />);
  await screen.findByTestId("checkpoint-banner");

  await user.click(screen.getByRole("button", { name: /reanudar pipeline/i }));

  await waitFor(() => expect(mockedApi.resumePipeline).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(mockedApi.fetchPendingChapters.mock.calls.length).toBeGreaterThanOrEqual(2));
});
```

Rationale for `toBeGreaterThanOrEqual(2)` rather than an exact count: `fetchPendingChapters` is already called once on mount (existing `loadChapters` in the initial `useEffect`); the resume handler must call `loadChapters()` again afterward, so total calls by the end of the test must be at least 2. This matches the task's own suggested assertion style ("assert `fetchPendingChapters` was called at least twice by the end") and avoids coupling the test to whether `handleRunPipeline`-style effects introduce any other incidental calls.

Optional, not required by the task but worth considering if it reads cleanly during implementation: also assert `mockedApi.fetchCheckpointSummary` was called at least twice (once on mount, once after resume) — this is what makes the banner disappear post-resume in real usage. Not strictly required by 5.2's three bullets, so treat as a nice-to-have, not a blocker.

## 5.3 — Implement in `frontend/src/components/PipelineFeed.tsx`

### Imports

Add `fetchCheckpointSummary` and `resumePipeline` to the existing `@/lib/api` import block (alphabetical-ish grouping already used in the file — insert near `fetchPendingChapters`/`fetchSourceUrls`):

```ts
import {
  approvePlatformVersion,
  fetchCheckpointSummary,
  fetchPendingChapters,
  fetchSourceUrls,
  publishPlatformVersion,
  resumePipeline,
  runResearch,
  type PendingChapter,
  type PlatformVersionSummary,
} from "@/lib/api";
```

No need to import the `CheckpointSummary` type explicitly if using an inline object type for local state (per the task's own suggested state shape), but importing and using `type CheckpointSummary` is equally fine and slightly more consistent with how `PendingChapter`/`PlatformVersionSummary` are already imported as types — either is acceptable; using the imported type is marginally preferable for consistency:

```ts
import {
  ...
  type CheckpointSummary,
  type PendingChapter,
  type PlatformVersionSummary,
} from "@/lib/api";
```

### New state

```ts
const [checkpointSummary, setCheckpointSummary] = useState<CheckpointSummary | null>(null);
```

(Or the inline `{ pending: number; failed: number } | null` shape from the task description — functionally identical; prefer the imported `CheckpointSummary` type for consistency with the rest of the file's typing style.)

### Loading the summary

Factor the checkpoint-summary fetch into its own `useCallback`, mirroring how `loadChapters` is already factored out — this makes it reusable both from the mount effect and from the resume handler without duplicating the `.then`/`.catch` pair:

```ts
const loadCheckpointSummary = useCallback(async () => {
  try {
    setCheckpointSummary(await fetchCheckpointSummary());
  } catch {
    setCheckpointSummary({ pending: 0, failed: 0 });
  }
}, []);
```

Update the existing mount `useEffect` to also call it:

```ts
useEffect(() => {
  loadChapters();
  loadCheckpointSummary();
  fetchSourceUrls()
    .then(setSourceUrls)
    .catch(() => setSourceUrls([]));
}, [loadChapters, loadCheckpointSummary]);
```

This keeps the same defensive-catch pattern already used for `fetchSourceUrls` (never leave the UI in a broken state if the summary endpoint errors — just treat it as "nothing outstanding"), per the task's explicit instruction.

### Resume handler

```ts
async function handleResumePipeline() {
  await resumePipeline();
  await loadChapters();
  await loadCheckpointSummary();
}
```

Note: unlike `handleRunPipeline`, this task's spec doesn't ask for a separate running/done/error status indicator for resume — keep it minimal (no new `RunStatus`-like state) unless you judge during implementation that an unguarded double-click or a thrown error from `resumePipeline()` would produce a confusing UX. If added for robustness, keep it a small, local concern (e.g., a `resuming` boolean disabling the button while in flight) — do not entangle it with the existing `runStatus` state, which is specifically about the "Ejecutar pipeline" flow and has its own status pill semantics. This is a judgment call left to whoever implements — the three tests in 5.2 do not require it, so treat it as optional polish, not a requirement to satisfy the tests.

### JSX — banner placement

Insert a new block between the existing `topbar` div and the `bulk-bar` div (per the task's explicit placement suggestion), guarded so it renders nothing when there's nothing outstanding:

```tsx
{checkpointSummary && (checkpointSummary.pending > 0 || checkpointSummary.failed > 0) && (
  <div className="checkpoint-banner" data-testid="checkpoint-banner">
    <span className="checkpoint-banner-text">
      {checkpointSummary.pending} documento(s) pendiente(s) de curación
      {checkpointSummary.failed > 0 && `, ${checkpointSummary.failed} fallido(s)`}
    </span>
    <button className="btn-resume" onClick={handleResumePipeline}>
      Reanudar pipeline
    </button>
  </div>
)}
```

Exact copy is left to the implementer's judgment per the task (the test only asserts the numbers appear in the banner's text, not exact wording) — the above is a reasonable default consistent with `proposal.md`'s own example phrasing ("N documentos pendientes de curación, N fallido — Reanudar pipeline"). Keep singular/plural handling simple (no need for a full pluralization helper for a single-operator internal tool) — "documento(s)"/"fallido(s)" parenthetical-plural shorthand is fine and consistent with this codebase's low-ceremony style, or just always use the plural form ("documentos", "fallidos") since a count of exactly 1 reading as "1 documentos" is a minor, acceptable rough edge for this UI — implementer's call.

Do not alter the existing `.topbar` or `.bulk-bar` divs' structure, class names, or test selectors — this is strictly a new sibling block inserted between them.

### CSS — `frontend/src/app/globals.css`

Add a new rule block near `.bulk-bar` (visually and semantically the closest existing precedent — a horizontal bar with text + action button sitting above the feed), but with its own class names since the semantics differ (this is an alert/warning, not a selection-count bar) — reuse the `--pending`/`--pending-soft` tokens already used for the "needs attention" stamp/status-pill elsewhere in this file, rather than introducing new colors:

```css
/* ---------- Checkpoint banner ---------- */
.checkpoint-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  background: var(--pending-soft);
  border: 1px solid var(--pending);
  border-radius: 10px;
  padding: 12px 16px;
  margin-bottom: 18px;
}
.checkpoint-banner-text {
  font-size: 13px;
  color: var(--pending);
  font-weight: 600;
  margin-right: auto;
}
.btn-resume {
  background: var(--accent);
  color: #1a1305;
  border: none;
  padding: 8px 14px;
  border-radius: 7px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}
.btn-resume:hover:not(:disabled) {
  filter: brightness(1.08);
}
```

Notes on this choice:
- `.checkpoint-banner` mirrors `.bulk-bar`'s layout (flex row, `margin-right: auto` on the text so the button sits flush right) but uses the pending/warning color pair instead of the neutral `ink-panel-2` used by `.bulk-bar`, since this banner is specifically flagging something that needs attention (unlike the bulk bar, which is neutral until something is selected).
- `.btn-resume` mirrors `.btn-run`'s look (solid `--accent` fill, dark text, same padding/radius scale) since both are the "primary action in this cluster" button — reusing `--accent` here (not `--pending`) keeps the button itself inviting to click rather than looking like an error state; the surrounding banner already carries the "attention" signaling via its border/background.
- No `position: sticky` (unlike `.bulk-bar`) — the checkpoint banner is not meant to persist while scrolling through the feed the way the bulk-selection bar is; it's an informational/one-off action banner near the top. Implementer may reconsider if it feels wrong in practice, but this is not exercised by any test either way.
- Deliberately not reusing `.bulk-bar`'s class name even though the layout is similar, per the task's explicit instruction not to "just copy its class wholesale if the semantics differ."

## Verification expectations (do not run yourself — for whoever implements)

- `npm test` inside `frontend/` should go from **22 tests / 4 suites / all passing** to **25 tests / 4 suites / all passing** (3 new tests added to the existing `PipelineFeed.test.tsx` suite; no new suite file).
- Confirm via `git diff` that none of the 13 pre-existing test bodies changed — only `beforeEach` gained one line, and three new `test(...)` blocks were appended.
- Confirm `frontend/src/lib/api.ts`'s diff is purely additive (one new interface, two new functions) with no changes to `request()` or any existing exported function.
- Confirm `PipelineFeed.tsx`'s diff does not alter the `topbar`, `bulk-bar`, or `feed` divs' existing markup/classes/test selectors — only inserts the new state, the new effect call, the new handler, and the new sibling JSX block plus updated import list.
- This plan does not cover task 6.1–6.4 (final mandatory closing steps, doc updates, E2E) — those are explicitly out of scope here per the task's own boundaries.
