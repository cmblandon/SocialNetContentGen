# Frontend Implementation Plan — research-query-scoping (tasks 5.1–5.3)

Scope: add an optional "topic/query" text input to the Pipeline view, threaded into
`runResearch()`. Strictly frontend, strictly tasks 5.1–5.3. No backend files touched.

Stack reminder (this repo, not the generic template): Next.js 16 App Router + TypeScript,
`src/` layout, `@/*` → `src/*`. Plain Client Components with hooks, plain `fetch` (no axios/SWR),
hand-written CSS classes in `frontend/src/app/globals.css` (no component library). Tests: Jest +
React Testing Library, `jest.mock("@/lib/api")`.

## Files touched

1. `frontend/src/components/__tests__/PipelineFeed.test.tsx` — add 3 new tests (5.1)
2. `frontend/src/lib/api.ts` — extend `runResearch()` (5.2)
3. `frontend/src/components/PipelineFeed.tsx` — add state + input + wiring (5.3)
4. `frontend/src/app/globals.css` — small additive CSS for the new input (needed to satisfy
   "reuse existing styling conventions"; not a numbered task but required to implement 5.3 cleanly)

Do NOT touch: `docs/frontend-standards.md` (later mandatory-docs task, 6.4), any file under
`src/editorial/` or other backend paths, `SourceUrlManager.tsx` (referenced only as a styling
precedent, not modified).

---

## 5.1 — New tests in `PipelineFeed.test.tsx`

Current file has 10 tests (all passing today). Add 3 more, immediately after the existing last
test ("the run-pipeline trigger is enabled and runs research when source URLs are configured",
lines 184–204) — do not change that test's body or assertion at all; it currently asserts
`runResearch` is called with exactly one argument when the query field is left empty, and must
keep passing byte-for-byte.

Pick the label text **"Tema (opcional)"** for the new `<label htmlFor="research-query">` (Spanish
UI copy, consistent with this file's existing convention: "Ejecutar pipeline", "Vista previa",
etc.). This makes the field discoverable via `screen.getByLabelText(/tema/i)`.

Append these three tests:

```tsx
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
```

Notes on why these are shaped this way:
- All three reuse the `beforeEach` default (`mockedApi.fetchSourceUrls.mockResolvedValue([...])`),
  so `sourceUrls` is populated and the button is enabled — no new mock setup needed there.
- `mockedApi.fetchPendingChapters.mockResolvedValue([])` is required in every test that reaches
  `loadChapters()` (the component calls it on mount and again after a successful run); omitting it
  leaves the mock returning `undefined` by default under `jest.resetAllMocks()`, which would throw
  inside `.map` elsewhere in the component. Follow the same pattern the existing "enabled and runs
  research" test already uses.
- The whitespace test is the literal one requested by task 5.1's last bullet — trimming must
  happen before deciding whether to include `query` at all, not just before sending it.
- `toHaveBeenCalledWith(["..."])` (one expected arg) fails if the actual call passed a second
  argument, even `undefined` — so 5.3's `handleRunPipeline` must branch into two distinct call
  shapes, not always call `runResearch(sourceUrls, query || undefined)`. See exact code in the 5.3
  section below.

These 3 tests bring `PipelineFeed.test.tsx` from 10 → 13 tests. All must go from failing (red) to
passing only after 5.2 + 5.3 land — do 5.1 first and confirm they fail for the *expected* reason
(no such label / `runResearch` not called with 2 args), not some unrelated crash.

---

## 5.2 — `frontend/src/lib/api.ts`

Replace the current `runResearch` (lines 106–111):

```ts
export function runResearch(sourceUrls: string[]): Promise<ResearchRunResult> {
  return request<ResearchRunResult>("/research/run", {
    method: "POST",
    body: JSON.stringify({ source_urls: sourceUrls }),
  });
}
```

with:

```ts
export function runResearch(sourceUrls: string[], query?: string): Promise<ResearchRunResult> {
  const body: { source_urls: string[]; query?: string } = { source_urls: sourceUrls };
  const trimmedQuery = query?.trim();
  if (trimmedQuery) {
    body.query = trimmedQuery;
  }
  return request<ResearchRunResult>("/research/run", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
```

Notes:
- Matches design.md Decision 4/5 exactly: omit the `query` key entirely rather than sending
  `query: ""` or `query: null` — the backend's `Optional[str] = None` default is what should run
  for "no query" (this is a request-body concern, independent of how many JS args `runResearch`
  itself receives — that's handled in `PipelineFeed.tsx`, not here).
  the request-body shape is what matters here.
- Trimming happens in the service layer too (not just the component) so this function is correct
  in isolation regardless of caller discipline — defensive, matches "services are pure async
  functions" principle already followed by every other function in this file.
- No new import needed; `request<T>` already handles the POST/JSON/error-throw plumbing.
- `ResearchRunResult` interface is unchanged (response shape unaffected, per design.md).

---

## 5.3 — `frontend/src/components/PipelineFeed.tsx`

### State

Add one line near the other `useState` declarations (after `selectedIds`, line 67):

```ts
const [query, setQuery] = useState("");
```

### `handleRunPipeline`

Replace (lines 89–99):

```ts
  async function handleRunPipeline() {
    if (!sourceUrls || sourceUrls.length === 0) return;
    setRunStatus("running");
    try {
      await runResearch(sourceUrls);
      setRunStatus("done");
      await loadChapters();
    } catch {
      setRunStatus("error");
    }
  }
```

with:

```ts
  async function handleRunPipeline() {
    if (!sourceUrls || sourceUrls.length === 0) return;
    setRunStatus("running");
    try {
      const trimmedQuery = query.trim();
      if (trimmedQuery) {
        await runResearch(sourceUrls, trimmedQuery);
      } else {
        await runResearch(sourceUrls);
      }
      setRunStatus("done");
      await loadChapters();
    } catch {
      setRunStatus("error");
    }
  }
```

**Critical detail** (re-stated from 5.1): this must be an `if/else` that calls `runResearch` with
either one or two arguments — never `runResearch(sourceUrls, trimmedQuery || undefined)`. Jest's
`toHaveBeenCalledWith(["..."])` checks arity as well as values; a call made with an explicit
second `undefined` argument does **not** match a one-argument expectation. The existing test at
line 184–204 (must not be touched) relies on exactly this.

### JSX — the input

Inside `run-cluster` (lines 164–182), add a new wrapper before the status pill:

```tsx
        <div className="run-cluster">
          <div className="query-field">
            <label htmlFor="research-query">Tema (opcional)</label>
            <input
              id="research-query"
              className="query-input"
              placeholder="Ej. incidentes de radar en Malmstrom"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <span className={`status-pill${...}`}>
            {...}
          </span>
          <button
            className="btn-run"
            onClick={handleRunPipeline}
            disabled={!sourceUrls || sourceUrls.length === 0 || runStatus === "running"}
            title={sourceUrls && sourceUrls.length === 0 ? "Configura al menos una fuente en Configuración" : undefined}
          >
            Ejecutar pipeline
          </button>
        </div>
```

(The `status-pill` span and `btn-run` button are unchanged — only the new `query-field` div is
inserted before them. Do not alter the status-pill class-building ternary or the button's
`disabled`/`title` logic — those are out of scope and already covered by two existing passing
tests.)

Do not disable the input while `runStatus === "running"`; leaving it editable is harmless (the
value is only read at click time) and keeps this change purely additive, matching the "additive
only" instruction and the design.md rollback note ("every change here is additive").

### CSS — `frontend/src/app/globals.css`

Two small, additive changes, following exactly the visual language already used for
`.settings-form`/`.search-form` inputs (`var(--ink-panel-2)` background, `var(--ink-border)`
border, `var(--text)` color — all tokens already defined in `:root`, no new colors introduced).

1. Extend the existing shared input-styling selector (around line 630) to also cover the new
   input, instead of duplicating its rules:

```css
.search-form input,
.settings-form input,
.query-field input,
textarea {
  background: var(--ink-panel-2);
  border: 1px solid var(--ink-border);
  border-radius: 7px;
  padding: 8px 12px;
  color: var(--text);
  font-size: 13.5px;
  font-family: inherit;
}
```

2. Add a new rule block near `.run-cluster` (around line 211, right after the `.run-cluster` rule)
   for the label + spacing + a sane fixed width so it doesn't crowd the status pill/button in the
   topbar's flex row:

```css
.query-field {
  display: flex;
  align-items: center;
  gap: 8px;
}
.query-field label {
  font-size: 12.5px;
  color: var(--text-muted);
  white-space: nowrap;
}
.query-field input {
  width: 220px;
}
```

3. Optional but recommended (matches the file's existing responsive pattern): inside the existing
   `@media (max-width: 720px)` block (line 687 area, which already restyles `.topbar`), add:

```css
  .query-field {
    width: 100%;
  }
  .query-field input {
    width: 100%;
  }
```

`.topbar` is already `flex-wrap: wrap`, so `.run-cluster` (and thus `.query-field`) will wrap onto
its own line on narrow viewports without further changes; this just lets the input fill that line
instead of staying pinned to 220px.

---

## Why this label/placeholder choice

- Label "Tema (opcional)" — short, matches the existing terse Spanish labels in this file ("URL"
  in `SourceUrlManager.tsx`), and "(opcional)" communicates the field is not required without
  needing a separate helper-text element.
- Placeholder "Ej. incidentes de radar en Malmstrom" — echoes the exact example used in
  `proposal.md` ("Malmstrom missile incidents"), giving the operator a concrete sense of the kind
  of input expected (a topic/case phrase, not a URL or a full sentence).
- `getByLabelText(/tema/i)` is the RTL query the new tests use; an explicit `<label htmlFor>` +
  matching `id` (not `aria-label`) was chosen because it's the pattern `SourceUrlManager.tsx`
  already establishes for a single labeled input next to a button, and it stays visible (no need
  to invent a `visually-hidden` utility class, which doesn't currently exist anywhere in
  `globals.css`).

## What NOT to change

- `ResearchRunResult`, `PendingChapter`, `PlatformVersionSummary` interfaces — untouched, response
  shape is unaffected.
- The `status-pill` ternary, `.btn-run` disabled/title logic, bulk-bar, case-card rendering,
  approve/publish handlers — all untouched, purely additive change.
- No new imports needed in `PipelineFeed.tsx` beyond what's already imported (`useState` is
  already imported from `"react"` at line 3).
- Do not add a `<form>`/`onSubmit` wrapper around the new input — "Ejecutar pipeline" is a
  standalone `<button onClick>`, not a submit button, and there's no Enter-to-submit requirement
  in tasks.md; keep the input as a plain controlled `<input>` to avoid introducing new event
  semantics (e.g. accidental page reload) not asked for by this change.

## Expected test outcome after 5.1–5.3 are fully implemented

Current full-suite baseline (before this change): 4 test files, 19 tests total, all passing
(`PipelineFeed.test.tsx`: 10, `CasesView.test.tsx`: 3, `Calendar.test.tsx`: 2,
`SourceUrlManager.test.tsx`: 4).

After 5.1–5.3: `PipelineFeed.test.tsx` goes from 10 → 13 tests (3 new). No other test file is
touched by this scope. Full `npm test` should report **4 suites passed, 22 tests passed, 0
failed** — the pre-existing 19 plus these 3, with the specific pre-existing test at
`PipelineFeed.test.tsx` line 184–204 ("the run-pipeline trigger is enabled and runs research when
source URLs are configured") passing unmodified and asserting a single-argument `runResearch`
call.

If any of the other 3 test files fail after this change, that indicates an unintended regression
(e.g. a CSS/DOM change bleeding into a shared layout test) — investigate before considering 5.1–5.3
complete, since this scope should have zero effect outside `PipelineFeed.tsx`/`api.ts`.
