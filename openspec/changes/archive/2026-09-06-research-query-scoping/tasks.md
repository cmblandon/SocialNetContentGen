## 0. Setup: Create Feature Branch (MANDATORY - FIRST STEP)

- [x] 0.1 Create feature branch `feature/research-query-scoping` from the current branch (`feature/enhance-admin-panel-ui` — not yet merged to `main`, and holds the Pipeline feed this change extends)
- [x] 0.2 Verify branch creation and current branch status

## 1. Backend: Scraper adapters accept an optional query

- [x] 1.1 Write failing tests for `JinaScraperAdapter.fetch(source_url, query=None)`: accepts the new `query` keyword without error; the outbound request (URL, headers) is identical whether `query` is `None` or a non-empty string (Jina's reader has no query mode — this is a documented no-op, not a bug)
- [x] 1.2 Add the `query: Optional[str] = None` parameter to `JinaScraperAdapter.fetch` (accepted, intentionally unused) to make 1.1 pass; add a one-line docstring note on why
- [x] 1.3 Write failing tests for `FirecrawlScraperAdapter.fetch(source_url, query=None)`: when `query` is a non-empty string, the POST payload includes `"prompt": query`; when `query` is `None` (or omitted), the payload has no `prompt` key and matches exactly today's `{"urls": [source_url]}` shape (existing tests asserting this must keep passing unmodified)
- [x] 1.4 Implement the conditional `prompt` field in `FirecrawlScraperAdapter.fetch` to make 1.3 pass
- [x] 1.5 Update `ISourceScraper.fetch`'s signature and docstring in `src/editorial/core/ports.py` to include the optional `query` parameter, documenting that not every implementation uses it

## 2. Backend: query-aware scraper ordering in ResearchAgentUseCase

- [x] 2.1 Write failing tests for `ResearchAgentUseCase.discover(source_urls, query=None)`: (a) with no query, behavior/order is byte-for-byte identical to today (primary tried first, fallback on `None`) — this must include re-running all 6 existing tests in `test_research_agent_use_case.py` unmodified as a regression guard; (b) with a query and both scrapers configured, the fallback scraper is tried first and receives the query, falling through to the primary scraper (which also receives the query) only if the fallback returns `None`; (c) with a query but no fallback scraper configured, the primary scraper is used and receives the query
- [x] 2.2 Implement the query-aware try-order in `discover()` to make 2.1 pass without breaking any existing test
- [x] 2.3 Update `ResearchAgentUseCase`'s module docstring and `get_research_agent()` (`src/editorial/presentation/routers/research.py`) with a comment documenting the primary/fallback role assumption this ordering relies on (design.md Decision 2's noted coupling)

## 3. Backend: thread the query through orchestration and the endpoint

- [x] 3.1 Write failing tests for `run_research_cycle(..., query=None)` (`src/editorial/application/orchestrator.py`): the `query` argument is forwarded to `research_agent.discover()` unchanged; omitting it preserves today's call exactly
- [x] 3.2 Implement the `query` parameter and forwarding in `run_research_cycle` to make 3.1 pass
- [x] 3.3 Write failing tests for `POST /research/run`: an optional `query` field in the request body is accepted and forwarded through to `run_research_cycle`; omitting `query` from the request body behaves exactly as before (existing `test_research_endpoint.py` tests must keep passing unmodified)
- [x] 3.4 Add the optional `query: Optional[str] = None` field to `ResearchRunRequest` and thread it through the `run_research` handler (`src/editorial/presentation/routers/research.py`) to make 3.3 pass

## 4. Backend: Mandatory closing steps

- [x] 4.1 Review and Update Existing Unit Tests (MANDATORY)
- [x] 4.2 Run Unit Tests and Verify Database State (MANDATORY) — capture pre/post baseline, run targeted then full suite, create report at `openspec/changes/research-query-scoping/reports/<YYYY-MM-DD>-step-4.2-unit-test-and-db-verification.md`
- [x] 4.3 Manual Endpoint Testing with curl (MANDATORY — AGENT MUST EXECUTE): call `POST /research/run` with a `query` field and without one against a live backend (fake scrapers wired via a throwaway script if real `JINA_API_KEY`/`FIRECRAWL_API_KEY` aren't configured in this environment — document whichever path was used); confirm the response shape is unchanged either way; restore any DB/memory-file state after; document in the phase report

## 5. Frontend: query input in the Pipeline view

- [x] 5.1 Write failing tests for `PipelineFeed.tsx`: a "topic/query" text input is rendered near "Ejecutar pipeline"; clicking the button with text entered calls `runResearch(sourceUrls, query)` with the entered text; clicking with the input empty calls `runResearch(sourceUrls)` (no query argument/field sent — an empty string is normalized away, not sent as `""`)
- [x] 5.2 Update `runResearch()` in `frontend/src/lib/api.ts` to accept an optional second `query` parameter, included in the request body only when it's a non-empty string
- [x] 5.3 Implement the input and wiring in `PipelineFeed.tsx` to make 5.1 pass

## 6. Final mandatory closing steps

- [x] 6.1 Review and Update Existing Unit Tests (MANDATORY) — both backend and frontend
- [x] 6.2 Run Unit Tests and Verify Database State (MANDATORY) — report at `openspec/changes/research-query-scoping/reports/<YYYY-MM-DD>-step-6.2-unit-test-and-db-verification.md`
- [x] 6.3 E2E Testing (MANDATORY — AGENT MUST EXECUTE): re-run both existing Playwright specs (`approval-to-calendar.spec.ts`, `covered-cases.spec.ts`) against real, running frontend + backend servers to confirm the new query input introduces no regression to the Pipeline feed's existing DOM/selectors; seed data as needed; restore all test data afterward; document in the phase report. No new E2E spec is added for "Ejecutar pipeline" itself — exercising it end-to-end requires live LLM/scraper API calls, which is out of scope for this environment's E2E data-hygiene constraints (`docs/frontend-standards.md`)
- [x] 6.4 Update Technical Documentation (MANDATORY): `README.md` (`POST /research/run`'s new optional `query` field), `docs/backend-standards.md` if the scraper-adapter pattern note needs updating, `docs/frontend-standards.md` (Pipeline feed section: mention the query input)
