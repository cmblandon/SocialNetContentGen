## 0. Setup: Create Feature Branch (MANDATORY - FIRST STEP)

- [x] 0.1 Create feature branch `feature/archivo-desclasificado-pipeline` from the current default branch
- [x] 0.2 Verify branch creation and current branch status

## 1. Phase 1 — Backend Foundation (data model, ports, FastAPI skeleton)

- [x] 1.1 Add new backend dependencies to `requirements.txt` (`fastapi`, `uvicorn`, `sqlalchemy`, `alembic`) needed for this phase only
- [x] 1.2 Write failing tests for the `Document`, `Story`, `Chapter`, `PlatformVersion`, `PublishRecord` SQLAlchemy models (fields, relationships, the `PlatformVersion.status` enum from design Decision 5, and `Document.source_ficha_id` reference from design Decision 3)
- [x] 1.3 Implement the SQLAlchemy models under `src/editorial/infrastructure/persistence/models.py` to make 1.2 pass
- [x] 1.4 Write failing tests validating an Alembic migration creates and reverts the new schema cleanly
- [x] 1.5 Add Alembic configuration and the initial migration for the editorial schema to make 1.4 pass
- [x] 1.6 Write failing tests (structural/typing) for the new `ISourceScraper`, `ISocialPublisher`, and editorial `ILLMClient` `Protocol` ports
- [x] 1.7 Define the new ports in `src/editorial/core/ports.py` to make 1.6 pass
- [x] 1.8 Write a failing test for a FastAPI health-check route (`GET /health`)
- [x] 1.9 Implement the FastAPI app skeleton with the health route to make 1.8 pass
- [x] 1.10 Review and Update Existing Unit Tests (MANDATORY)
- [x] 1.11 Run Unit Tests and Verify Database State (MANDATORY) — capture pre/post DB baseline for the new schema, run targeted then full suite, create report at `openspec/changes/archivo-desclasificado-pipeline/reports/<YYYY-MM-DD>-step-1.11-unit-test-and-db-verification.md`
- [x] 1.12 Manual Endpoint Testing with curl (MANDATORY — AGENT MUST EXECUTE): start the FastAPI server, `curl -X GET http://localhost:8000/health`, verify 200 response, document the command and response in the phase report
- [x] 1.13 Update Technical Documentation (MANDATORY): document the new `src/editorial/` module layout and how it relates to the existing ingestion pipeline

## 2. Phase 2 — story-writing & platform-adaptation use cases

- [x] 2.1 Write failing tests for `StoryWritingUseCase` covering: hook/development/close structure, chapter splitting into 150-220 word chapters with grounded cliffhangers, per-chapter delivery format (title/script/visuals/citation), and rejection of fabricated quotes/overstated claims — per `specs/story-writing/spec.md`
- [x] 2.2 Implement `StoryWritingUseCase` (using the new editorial `ILLMClient` cloud implementation) to make 2.1 pass
- [x] 2.3 Write failing tests for `PlatformAdaptationUseCase` covering all four platform formats (TikTok/Reels, Instagram carousel, X thread, Facebook) — per `specs/platform-adaptation/spec.md`
- [x] 2.4 Implement `PlatformAdaptationUseCase` to make 2.3 pass
- [x] 2.5 Write failing tests for a CLI entrypoint that feeds an existing manually-ingested `FichaEstructurada` (marked curated via a fixture/flag) into the two use cases above
- [x] 2.6 Implement the CLI entrypoint to make 2.5 pass (also added `AnthropicLLMClient`, the concrete editorial `ILLMClient`, so the CLI's `main()` is genuinely runnable — not itemized separately above but required for this task's own goal)
- [x] 2.7 Review and Update Existing Unit Tests (MANDATORY)
- [x] 2.8 Run Unit Tests and Verify Database State (MANDATORY) — report at `openspec/changes/archivo-desclasificado-pipeline/reports/<YYYY-MM-DD>-step-2.8-unit-test-and-db-verification.md`
- [x] 2.9 Update Technical Documentation (MANDATORY): document how to run the manual story+adaptation CLI against an existing ingested document
- [x] 2.10 Confirm no new HTTP endpoints were introduced in this phase (curl testing not applicable — use cases are exercised via the CLI fixture only)

## 3. Phase 3 — editorial-orchestration (deepagents/LangGraph)

- [x] 3.1 Add `deepagents` (LangChain/LangGraph) and its Anthropic client dependency to `requirements.txt`
- [x] 3.2 Write failing tests for the virtual-filesystem memory files (`/casos_cubiertos.md`, `/calendario.md`, `/manual_de_marca.md`) being read at cycle start and updated at cycle end (implemented as directly-tested file I/O rather than deepagents' internal backend — see task 3.3 note)
- [x] 3.3 Implement the memory-file read/update logic to make 3.2 pass
- [x] 3.4 Write failing tests for the orchestrator graph delegating to the Phase 2 use cases as subagents/tools rather than executing them inline — per `specs/editorial-orchestration/spec.md`
- [x] 3.5 Implement the orchestrator graph wiring (writer + platform-adapter subagents) to make 3.4 pass
- [x] 3.6 Write failing tests for the approval-gate interrupt: the graph pauses before the publisher node, persists `PlatformVersion.status = pending_review`, and only resumes toward publishing when status observes `approved` (also added `persist_story`, bridging Phase 2's in-memory drafts into the Phase 1 SQLAlchemy schema — required to have real status to gate on, not itemized separately above)
- [x] 3.7 Implement the approval-gate node (`PlatformVersion` status persistence + `run_if_approved` gate) to make 3.6 pass — scoped to the application-layer status check rather than LangGraph's `interrupt()` primitive, since there is no publisher node yet to pause before (Phase 5); the design's own Decision 5 treats this persisted status as the authoritative enforcement regardless
- [x] 3.8 Write failing tests for `POST /platform-versions/{id}/approve` and `POST /platform-versions/{id}/reject` stub endpoints that flip a pending item's status (stand-in for the real admin panel until Phase 6) — renamed from tasks.md's placeholder `/cycles/{id}/...` since there is no `Cycle` entity in the schema; the thing actually approved/rejected is a `PlatformVersion`
- [x] 3.9 Implement the approve/reject endpoints to make 3.8 pass
- [x] 3.10 Write failing tests for the ambiguous/incomplete-document handling rule (discard or request more research, never fabricate) — per `specs/editorial-orchestration/spec.md` (bundled with `run_cycle`, the top-level orchestration function tying together readiness-checking, delegation, persistence, and memory bookkeeping — this and 3.12 share one function so their tests share one file)
- [x] 3.11 Implement that handling in the orchestrator to make 3.10 pass
- [x] 3.12 Write failing tests for the end-of-cycle summary (documents reviewed, stories created, chapters generated, pending approvals) — covered by the same `test_orchestrator_cycle.py` / `run_cycle` as 3.10 (one function, one `CycleSummary` return value)
- [x] 3.13 Implement the end-of-cycle summary to make 3.12 pass — same implementation as 3.11
- [x] 3.14 Review and Update Existing Unit Tests (MANDATORY)
- [x] 3.15 Run Unit Tests and Verify Database State (MANDATORY) — report at `openspec/changes/archivo-desclasificado-pipeline/reports/<YYYY-MM-DD>-step-3.15-unit-test-and-db-verification.md`
- [x] 3.16 Manual Endpoint Testing with curl (MANDATORY — AGENT MUST EXECUTE): test `POST /platform-versions/{id}/approve` and `POST /platform-versions/{id}/reject` against seeded pending items, verify status transitions and error cases (unknown id, already-decided item), restore DB state after, document commands/responses in the phase report
- [x] 3.17 Update Technical Documentation (MANDATORY): document the orchestrator's stage flow and the approval-gate mechanics

## 4. Phase 4 — research-agent & case-curation

- [ ] 4.1 Add the chosen scraping client dependency (`httpx` plus Jina AI Reader usage; Firecrawl SDK as fallback) to `requirements.txt`
- [ ] 4.2 Write failing tests for the Jina-based `ISourceScraper` implementation against a mocked HTTP layer (source discovery, structured record extraction, OCR-summary handling for scanned PDFs, video/image description-only handling) — per `specs/research-agent/spec.md`
- [ ] 4.3 Implement the Jina scraper adapter to make 4.2 pass
- [ ] 4.4 Write failing tests for the Firecrawl fallback adapter (used when Jina fails on a protected/complex page) against a mocked HTTP layer
- [ ] 4.5 Implement the Firecrawl scraper adapter to make 4.4 pass
- [ ] 4.6 Write failing tests for `ResearchAgentUseCase`: source allowlist enforcement, discard-on-unverifiable/login-protected source with reporting, dedup against `/casos_cubiertos.md` before extraction, and "no interpretation" output constraint
- [ ] 4.7 Implement `ResearchAgentUseCase` to make 4.6 pass
- [ ] 4.8 Write failing tests for `CaseCurationUseCase`: five-criteria scoring, the ≥15/25 advancement threshold, permanent recording of every evaluated case (advanced or discarded) with date and reason, and the narrative-angle note attached on advancement — per `specs/case-curation/spec.md`
- [ ] 4.9 Implement `CaseCurationUseCase` to make 4.8 pass
- [ ] 4.10 Wire `ResearchAgentUseCase` and `CaseCurationUseCase` into the Phase 3 orchestrator, replacing the Phase 2 manual-curation CLI fixture as the real input path
- [ ] 4.11 Write failing tests for a `POST /research/run` trigger endpoint that starts a research+curation pass on demand (manual trigger, per design's Non-Goal deferring cron scheduling)
- [ ] 4.12 Implement the `POST /research/run` endpoint to make 4.11 pass
- [ ] 4.13 Review and Update Existing Unit Tests (MANDATORY)
- [ ] 4.14 Run Unit Tests and Verify Database State (MANDATORY) — report at `openspec/changes/archivo-desclasificado-pipeline/reports/<YYYY-MM-DD>-step-4.14-unit-test-and-db-verification.md`
- [ ] 4.15 Manual Endpoint Testing with curl (MANDATORY — AGENT MUST EXECUTE): `curl -X POST http://localhost:8000/research/run` against mocked/sandboxed sources, verify response and resulting `/casos_cubiertos.md` + `Document` records, restore DB state after the test, document commands/responses in the phase report
- [ ] 4.16 Update Technical Documentation (MANDATORY): document the source allowlist, the scraper adapter swap mechanism (Jina/Firecrawl), and the scoring rubric

## 5. Phase 5 — publishing

- [ ] 5.1 Add the Postiz client dependency (or a plain `httpx`-based adapter against its API) to `requirements.txt`
- [ ] 5.2 Write failing tests for the Postiz `ISocialPublisher` implementation against a mocked HTTP layer (schedule/publish call, returned post ID capture, error surfacing)
- [ ] 5.3 Implement the Postiz publisher adapter to make 5.2 pass
- [ ] 5.4 Write failing tests for `PublishingUseCase`: publish only when status is `approved`, use the calendar-defined optimal time or propose-and-hold-for-approval when undefined, record every outcome in `/calendario.md` with network/time/post ID, and report-without-silent-repeat-retry on failure — per `specs/publishing/spec.md`
- [ ] 5.5 Implement `PublishingUseCase` to make 5.4 pass
- [ ] 5.6 Wire `PublishingUseCase` into the orchestrator so it fires only after the Phase 3 approval gate observes `approved`
- [ ] 5.7 Write failing tests for a `GET /publish-records` (list/status) endpoint the admin panel will consume in Phase 6
- [ ] 5.8 Implement the `GET /publish-records` endpoint to make 5.7 pass
- [ ] 5.9 Review and Update Existing Unit Tests (MANDATORY)
- [ ] 5.10 Run Unit Tests and Verify Database State (MANDATORY) — report at `openspec/changes/archivo-desclasificado-pipeline/reports/<YYYY-MM-DD>-step-5.10-unit-test-and-db-verification.md`
- [ ] 5.11 Manual Endpoint Testing with curl (MANDATORY — AGENT MUST EXECUTE): approve a seeded pending item via the Phase 3 endpoint, trigger publishing, `curl -X GET http://localhost:8000/publish-records`, verify the resulting record and calendar entry, test the failure path against a mocked API error and confirm no silent second retry, restore DB state, document commands/responses in the phase report
- [ ] 5.12 Update Technical Documentation (MANDATORY): document the publisher port and how to swap Postiz for Ayrshare/Blotato later

## 6. Phase 6 — content-admin-panel (Next.js)

- [ ] 6.1 Scaffold the Next.js app in a new top-level `frontend/` directory, pointing at the FastAPI service from previous phases
- [ ] 6.2 Decide and implement the minimal shared-credential auth gate for the panel (per design Open Question — single shared token or basic auth; document the choice)
- [ ] 6.3 Write failing frontend tests for the Approval Queue view (source document, story summary, chapter script, all platform versions, approve/reject actions) — per `specs/content-admin-panel/spec.md`
- [ ] 6.4 Implement the Approval Queue view against the Phase 3 approve/reject endpoints to make 6.3 pass
- [ ] 6.5 Write failing frontend tests for the Editorial Calendar view (published/scheduled items by network and time)
- [ ] 6.6 Implement the Calendar view against the Phase 5 `GET /publish-records` endpoint to make 6.5 pass
- [ ] 6.7 Write failing frontend tests for the Covered Cases view (search, browse, manual edit of `/casos_cubiertos.md` entries)
- [ ] 6.8 Write failing backend tests for the endpoints the Covered Cases view needs (`GET /cases`, `PATCH /cases/{id}`)
- [ ] 6.9 Implement the `GET /cases` / `PATCH /cases/{id}` endpoints to make 6.8 pass
- [ ] 6.10 Implement the Covered Cases view against those endpoints to make 6.7 pass
- [ ] 6.11 Review and Update Existing Unit Tests (MANDATORY) — both backend and frontend
- [ ] 6.12 Run Unit Tests and Verify Database State (MANDATORY) — report at `openspec/changes/archivo-desclasificado-pipeline/reports/<YYYY-MM-DD>-step-6.12-unit-test-and-db-verification.md`
- [ ] 6.13 Manual Endpoint Testing with curl (MANDATORY — AGENT MUST EXECUTE): exercise `GET /cases` and `PATCH /cases/{id}` (verify update, then restore original values), document commands/responses in the phase report
- [ ] 6.14 E2E Testing with Playwright MCP (MANDATORY — AGENT MUST EXECUTE): start frontend and backend, navigate to the panel, run the full approve-then-see-in-calendar workflow and the covered-cases search/edit workflow, verify data persistence matches backend state, restore any test data created, document scenarios and outcomes in the phase report
- [ ] 6.15 Update Technical Documentation (MANDATORY): document how to run the admin panel locally against the backend

## 7. Final Wrap-up

- [ ] 7.1 Update the root `README.md` to describe the end-to-end pipeline (ingestion → research/curation → writing/adaptation → orchestration/approval → publishing → admin panel)
- [ ] 7.2 Replace the stale, unrelated-template content in `docs/data-model.md` with the actual editorial schema (`Document → Story → Chapter → PlatformVersion → PublishRecord`)
- [ ] 7.3 Verify no broken symlinks or duplicated canonical artifacts were introduced in `.claude`/`.cursor`/`ai-specs` by this change, per CLAUDE.md Section 6
- [ ] 7.4 Final full-suite test run (backend + frontend) and confirm all phase reports exist under `openspec/changes/archivo-desclasificado-pipeline/reports/`
