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

- [x] 4.1 Add the chosen scraping client dependency (`httpx` plus Jina AI Reader usage; Firecrawl SDK as fallback) to `requirements.txt` — `httpx` is already present from Phase 1; implemented the Firecrawl fallback via raw HTTP against its `/v1/extract` API rather than the `firecrawl-py` SDK, keeping both adapters symmetric and avoiding an extra dependency
- [x] 4.2 Write failing tests for the Jina-based `ISourceScraper` implementation against a mocked HTTP layer (source discovery, structured record extraction, OCR-summary handling for scanned PDFs, video/image description-only handling) — per `specs/research-agent/spec.md`
- [x] 4.3 Implement the Jina scraper adapter to make 4.2 pass
- [x] 4.4 Write failing tests for the Firecrawl fallback adapter (used when Jina fails on a protected/complex page) against a mocked HTTP layer
- [x] 4.5 Implement the Firecrawl scraper adapter to make 4.4 pass
- [x] 4.6 Write failing tests for `ResearchAgentUseCase`: source allowlist enforcement, discard-on-unverifiable/login-protected source with reporting, dedup against `/casos_cubiertos.md` before extraction, and "no interpretation" output constraint (scoped to processing a supplied list of candidate URLs, not autonomous listing-page crawling — see test file docstring)
- [x] 4.7 Implement `ResearchAgentUseCase` to make 4.6 pass
- [x] 4.8 Write failing tests for `CaseCurationUseCase`: five-criteria scoring, the ≥15/25 advancement threshold, permanent recording of every evaluated case (advanced or discarded) with date and reason, and the narrative-angle note attached on advancement — per `specs/case-curation/spec.md`
- [x] 4.9 Implement `CaseCurationUseCase` to make 4.8 pass
- [x] 4.10 Wire `ResearchAgentUseCase` and `CaseCurationUseCase` into the Phase 3 orchestrator, replacing the Phase 2 manual-curation CLI fixture as the real input path (`orchestrator.run_research_cycle`)
- [x] 4.11 Write failing tests for a `POST /research/run` trigger endpoint that starts a research+curation pass on demand (manual trigger, per design's Non-Goal deferring cron scheduling)
- [x] 4.12 Implement the `POST /research/run` endpoint to make 4.11 pass
- [x] 4.13 Review and Update Existing Unit Tests (MANDATORY)
- [x] 4.14 Run Unit Tests and Verify Database State (MANDATORY) — report at `openspec/changes/archivo-desclasificado-pipeline/reports/<YYYY-MM-DD>-step-4.14-unit-test-and-db-verification.md`
- [x] 4.15 Manual Endpoint Testing with curl (MANDATORY — AGENT MUST EXECUTE): curl-tested request validation and route wiring against a real live server; the full discover→curate→write→adapt→persist happy path is covered by `tests/unit/test_research_endpoint.py`'s `TestClient` + dependency-override fakes instead of live curl, since no `.env`/API keys are configured and the real dependencies would otherwise make genuine calls to Jina/Firecrawl/Anthropic — see the report's scope note
- [x] 4.16 Update Technical Documentation (MANDATORY): document the source allowlist, the scraper adapter swap mechanism (Jina/Firecrawl), and the scoring rubric

## 5. Phase 5 — publishing

- [x] 5.1 Add the Postiz client dependency (or a plain `httpx`-based adapter against its API) to `requirements.txt` — implemented via raw `httpx`, same symmetric approach as the Phase 4 scraper adapters; no new dependency needed
- [x] 5.2 Write failing tests for the Postiz `ISocialPublisher` implementation against a mocked HTTP layer (schedule/publish call, returned post ID capture, error surfacing)
- [x] 5.3 Implement the Postiz publisher adapter to make 5.2 pass
- [x] 5.4 Write failing tests for `PublishingUseCase`: publish only when status is `approved`, use the calendar-defined optimal time or propose-and-hold-for-approval when undefined, record every outcome in `/calendario.md` with network/time/post ID, and report-without-silent-repeat-retry on failure — per `specs/publishing/spec.md`
- [x] 5.5 Implement `PublishingUseCase` to make 5.4 pass
- [x] 5.6 Wire `PublishingUseCase` into the orchestrator so it fires only after the Phase 3 approval gate observes `approved` — `POST /platform-versions/{id}/approve` now invokes it immediately after recording the approval, per specs/editorial-orchestration's "orchestrator proceeds to publishing" requirement
- [x] 5.7 Write failing tests for a `GET /publish-records` (list/status) endpoint the admin panel will consume in Phase 6
- [x] 5.8 Implement the `GET /publish-records` endpoint to make 5.7 pass
- [x] 5.9 Review and Update Existing Unit Tests (MANDATORY) — extended `tests/unit/test_approval_endpoints.py` with the new publishing-wiring tests (5.6) since approve() now depends on `get_publishing_use_case`
- [x] 5.10 Run Unit Tests and Verify Database State (MANDATORY) — report at `openspec/changes/archivo-desclasificado-pipeline/reports/<YYYY-MM-DD>-step-5.10-unit-test-and-db-verification.md` (documents and resolves a real interim mutation caught during this step — see report)
- [x] 5.11 Manual Endpoint Testing with curl (MANDATORY — AGENT MUST EXECUTE): approved two seeded pending items via the Phase 3 endpoint against a real server/DB — one exercising the propose-time path, one exercising a real (naturally-occurring) publish failure — verified `GET /publish-records` and the calendar entries, confirmed no silent retry (409 on re-approval), restored DB state
- [x] 5.12 Update Technical Documentation (MANDATORY): document the publisher port and how to swap Postiz for Ayrshare/Blotato later

## 6. Phase 6 — content-admin-panel (Next.js)

- [x] 6.1 Scaffold the Next.js app in a new top-level `frontend/` directory, pointing at the FastAPI service from previous phases (Next.js 16 + TypeScript + App Router, `src/` dir; Jest + React Testing Library for unit tests, Playwright for E2E, per `docs/frontend-standards.md`). Note: Next.js 16 renamed `middleware.ts` to `proxy.ts` — the auth gate in 6.2 uses the new convention.
- [x] 6.2 Decide and implement the minimal shared-credential auth gate for the panel (per design Open Question — single shared token or basic auth; document the choice). Decided: single shared token (not basic auth — avoids browser basic-auth caching/logout quirks for a small internal tool), stored in `ADMIN_PANEL_TOKEN`, exchanged for an httpOnly session cookie via `POST /api/login`, enforced by `src/proxy.ts` (Next.js 16's renamed `middleware.ts`). No dedicated automated test — Next 16's proxy unit-testing support is explicitly experimental (`unstable_doesProxyMatch`); verified via `npm run build` (proxy compiles and is wired) and will be exercised live during the Playwright E2E pass (6.14).
- [x] 6.3 Write failing frontend tests for the Approval Queue view (source document, story summary, chapter script, all platform versions, approve/reject actions) — per `specs/content-admin-panel/spec.md`
- [x] 6.4 Implement the Approval Queue view against the Phase 3 approve/reject endpoints to make 6.3 pass. Also added `GET /chapters/pending` (backend) — the approve/reject endpoints alone don't expose the read context (source document, story summary, script, all platform versions) the spec requires the queue to display; not itemized separately above but required to build this view at all.
- [x] 6.5 Write failing frontend tests for the Editorial Calendar view (published/scheduled items by network and time)
- [x] 6.6 Implement the Calendar view against the Phase 5 `GET /publish-records` endpoint to make 6.5 pass
- [x] 6.7 Write failing frontend tests for the Covered Cases view (search, browse, manual edit of `/casos_cubiertos.md` entries)
- [x] 6.8 Write failing backend tests for the endpoints the Covered Cases view needs (`GET /cases`, `PATCH /cases/{id}`)
- [x] 6.9 Implement the `GET /cases` / `PATCH /cases/{id}` endpoints to make 6.8 pass
- [x] 6.10 Implement the Covered Cases view against those endpoints to make 6.7 pass
- [x] 6.11 Review and Update Existing Unit Tests (MANDATORY) — both backend and frontend. 194 backend + 10 frontend tests pass, no regressions.
- [x] 6.12 Run Unit Tests and Verify Database State (MANDATORY) — report at `openspec/changes/archivo-desclasificado-pipeline/reports/<YYYY-MM-DD>-step-6.12-unit-test-and-db-verification.md`
- [x] 6.13 Manual Endpoint Testing with curl (MANDATORY — AGENT MUST EXECUTE): exercise `GET /cases` and `PATCH /cases/{id}` (verify update, then restore original values), document commands/responses in the phase report
- [x] 6.14 E2E Testing (MANDATORY — AGENT MUST EXECUTE): no Playwright MCP browser tool was available in this environment, so used the project's own installed `@playwright/test` runner (real headless Chromium) via CLI instead — same substantive requirement (agent-executed, real-browser verification), standard mechanism per `docs/frontend-standards.md`. Ran the full approve-then-see-in-calendar workflow and the covered-cases search/edit workflow against real, running frontend+backend servers; found and fixed a real CORS gap plus two test-setup bugs; restored all test data. See the phase report for full detail.
- [x] 6.15 Update Technical Documentation (MANDATORY): document how to run the admin panel locally against the backend

## 7. Final Wrap-up

- [x] 7.1 Update the root `README.md` to describe the end-to-end pipeline (ingestion → research/curation → writing/adaptation → orchestration/approval → publishing → admin panel)
- [x] 7.2 Replace the stale, unrelated-template content in `docs/data-model.md` with the actual editorial schema (`Document → Story → Chapter → PlatformVersion → PublishRecord`) — done incrementally starting Phase 1 (the original unrelated-template content was replaced then, per the docs-consistency pass); this step brought the trailing "Status" section up to date through Phase 6, which had gone stale
- [x] 7.3 Verify no broken symlinks or duplicated canonical artifacts were introduced in `.claude`/`.cursor`/`ai-specs` by this change, per CLAUDE.md Section 6 — confirmed no symlinks exist anywhere in the repo and no `ai-specs`/`.cursor` directories exist; this project doesn't use that convention, so the section doesn't apply
- [x] 7.4 Final full-suite test run (backend + frontend) and confirm all phase reports exist under `openspec/changes/archivo-desclasificado-pipeline/reports/` — 196 backend + 10 frontend tests passing; all 12 expected reports present
