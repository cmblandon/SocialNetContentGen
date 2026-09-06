## 0. Setup: Create Feature Branch (MANDATORY - FIRST STEP)

- [x] 0.1 Create feature branch `feature/research-pipeline-checkpointing` from the current branch (`feature/research-query-scoping` — not yet merged to `main`, and holds the `query`-aware discovery this change builds on)
- [x] 0.2 Verify branch creation and current branch status

## 1. Backend: `DiscoveredDocument` model and migration

- [x] 1.1 Write a failing test in `tests/unit/test_editorial_migrations.py`: add `"discovered_documents"` to `EXPECTED_TABLES` (the existing `test_upgrade_head_creates_all_editorial_tables`/`test_downgrade_base_removes_all_editorial_tables` tests then exercise it automatically)
- [x] 1.2 Add `CurationStatus` enum (`PENDING`, `ADVANCED`, `DISCARDED`, `FAILED`) and the `DiscoveredDocument` model (`title`, `agency`, `doc_type`, `extracted_text`, `published_date`, `source_url`, `extraction_confidence`, `status`, `error_message`, `narrative_angle`, `document_id` FK to `documents.id` nullable, `created_at`, `updated_at`) to `src/editorial/infrastructure/persistence/models.py`
- [x] 1.3 Add a new Alembic revision (`0002_discovered_documents.py`, `down_revision = "0001_initial_editorial_schema"`) creating the `discovered_documents` table, with a working `downgrade()`, to make 1.1 pass

## 2. Backend: checkpoint before curating, isolate curation failures

- [x] 2.1 Write failing tests for a new `discovered_documents_repo` (or equivalent small module) that persists a `ScrapedDocument` as a `PENDING` `DiscoveredDocument`, and can look up existing checkpoint rows by `source_url` and by `status`
- [x] 2.2 Implement the checkpoint persistence helper to make 2.1 pass
- [x] 2.3 Write failing tests for `run_research_cycle`: (a) every document `discover()` returns is checkpointed as `PENDING` before curation is attempted, verifiable even when curation subsequently fails; (b) when `case_curation.curate(...)` raises for one document, that document's checkpoint becomes `FAILED` with the exception's message recorded, and processing continues for the remaining documents in `research_result.documents`; (c) **the critical regression case**: with 3 documents where curation raises on the 2nd, the 1st document (which advanced before the crash) still has its `Story`/`Chapter`/`PlatformVersion` created — assert this explicitly by querying for a `Story` row linked to the 1st document's `Document.id`, since today's code would silently leave it Story-less (see design.md Decision 2's "second, subtler loss"); (d) a document that advances gets its checkpoint updated to `ADVANCED` with `document_id` set; a discarded one gets `DISCARDED`; (e) all existing `test_research_cycle.py` tests keep passing unmodified (they exercise the success path, which must remain unchanged in outcome); (f) all existing `test_orchestrator_cycle.py` tests keep passing unmodified (`run_cycle` itself is not being changed, only how often/when `run_research_cycle` calls it)
- [x] 2.4 Refactor `run_research_cycle`'s inner loop into a shared per-document helper (checkpoint lookup/creation → curate with try/except → on success, call `run_cycle(session, [(document, narrative_angle)], ...)` **immediately** for that one document, aggregating its returned `CycleSummary` into the running total — not accumulating a batch for one `run_cycle` call at the end; on exception, mark `FAILED`) that both `run_research_cycle` and the new resume path (section 3) will call, to make 2.3 pass without changing `run_research_cycle`'s public signature, `run_cycle`'s existing contract, or the final `CycleSummary` shape returned to callers

## 3. Backend: dedup against checkpoints, and the resume endpoint

- [x] 3.1 Write failing tests for `run_research_cycle`: a `source_url` with an existing `PENDING` or `FAILED` checkpoint is excluded from the list passed to `research_agent.discover(...)` (assert via a fake research agent recording which URLs it was actually asked to fetch)
- [x] 3.2 Implement the pre-`discover()` filter against non-terminal `DiscoveredDocument` rows to make 3.1 pass
- [x] 3.3 Write failing tests for a new `run_resume_cycle` (or equivalently-named) orchestrator function: processes every `PENDING`/`FAILED` `DiscoveredDocument` row through the shared helper from 2.4 (curate → write/adapt/persist if advanced), performs no scraping, and returns a `CycleSummary`-shaped result; with nothing pending/failed, returns an empty summary without error
- [x] 3.4 Implement `run_resume_cycle` to make 3.3 pass, reusing the section 2.4 helper
- [x] 3.5 Write failing tests for `POST /research/resume`: no request body needed (or an empty one), calls the resume orchestration, returns the same response shape as `POST /research/run`
- [x] 3.6 Implement the `POST /research/resume` endpoint in `src/editorial/presentation/routers/research.py` to make 3.5 pass
- [x] 3.7 Write failing tests for `GET /research/checkpoints/summary`: returns `{"pending": <count>, "failed": <count>}` counting `DiscoveredDocument` rows by status; zero/zero when none exist
- [x] 3.8 Implement `GET /research/checkpoints/summary` to make 3.7 pass

## 4. Backend: Mandatory closing steps

- [x] 4.1 Review and Update Existing Unit Tests (MANDATORY)
- [x] 4.2 Run Unit Tests and Verify Database State (MANDATORY) — capture pre/post baseline, run targeted then full suite, create report at `openspec/changes/research-pipeline-checkpointing/reports/<YYYY-MM-DD>-step-4.2-unit-test-and-db-verification.md`
- [x] 4.3 Manual Endpoint Testing with curl (MANDATORY — AGENT MUST EXECUTE): apply the new migration against a scratch/test DB copy (never the real `editorial.sqlite`) if verifying against a live server; exercise the checkpoint-then-fail-then-resume flow end to end using a deliberately-failing curation stub or by temporarily pointing at an invalid Anthropic key in an isolated test environment — NOT the live server holding real operator data — to confirm a curation failure leaves a retryable checkpoint and `POST /research/resume` successfully processes it afterward; document exact commands/results and how real data was kept isolated in the phase report

## 5. Frontend: checkpoint visibility and resume action

- [x] 5.1 Add `fetchCheckpointSummary()` and `resumePipeline()` to `frontend/src/lib/api.ts`, calling `GET /research/checkpoints/summary` (task 3.7/3.8) and `POST /research/resume` (task 3.5/3.6) respectively
- [x] 5.2 Write failing tests for `PipelineFeed.tsx`: when pending/failed checkpoint counts are non-zero, a banner and a "Reanudar pipeline" button appear; clicking it calls `resumePipeline()` and reloads the chapter feed; when both counts are zero, neither the banner nor the button render
- [x] 5.3 Implement the banner and resume action in `PipelineFeed.tsx` to make 5.2 pass

## 6. Final mandatory closing steps

- [x] 6.1 Review and Update Existing Unit Tests (MANDATORY) — both backend and frontend
- [x] 6.2 Run Unit Tests and Verify Database State (MANDATORY) — report at `openspec/changes/research-pipeline-checkpointing/reports/<YYYY-MM-DD>-step-6.2-unit-test-and-db-verification.md`
- [x] 6.3 E2E Testing (MANDATORY — AGENT MUST EXECUTE): re-run the existing Playwright specs against real, running frontend + backend servers to confirm no regression to the Pipeline feed; seed data as needed (including a deliberately-`FAILED` checkpoint row, to see the resume banner render); restore all test data afterward; document in the phase report — **outcome**: a near-miss with the user's already-running live dev servers (sharing the same hardcoded DB path) was caught and reverted before any confirmed impact; user explicitly chose to skip a new browser E2E run and accept existing coverage instead (247 backend + 25 frontend unit tests, plus step 4.3's live curl-based integration test) — see `reports/2026-09-06-step-6.3-e2e-testing.md`
- [x] 6.4 Update Technical Documentation (MANDATORY): `README.md` (new `discovered_documents` table, `POST /research/resume`, the checkpoint/dedup behavior), `docs/backend-standards.md` (new migration, new table pattern — already covered generically, no change needed since `CurationStatus`/`DiscoveredDocument` follow the exact existing enum/migration conventions), `docs/frontend-standards.md` (Pipeline feed's checkpoint banner/resume action, plus a new E2E gotcha note about hardcoded DB paths colliding with a live dev server), `docs/data-model.md` (new `DiscoveredDocument` section + updated ERD + Status section)
