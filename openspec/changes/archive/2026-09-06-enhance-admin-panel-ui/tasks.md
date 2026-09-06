## Execution note

Per CLAUDE.md and the user's explicit request: backend-touching tasks
(sections 1-3) should be delegated to the `backend-developer` subagent;
frontend-touching tasks (sections 4-8) should be delegated to the
`frontend-developer` subagent, at `/opsx:apply` time. This file defines
*what* to build and in what order; which agent does the typing is an
apply-time execution detail, not a spec/requirement.

## 0. Setup: Create Feature Branch (MANDATORY - FIRST STEP)

- [x] 0.1 Create feature branch `feature/enhance-admin-panel-ui` from the current branch (`feature/archivo-desclasificado-pipeline` — not yet merged to `main`, and holds all the code this change modifies)
- [x] 0.2 Verify branch creation and current branch status

## 1. Backend: Decouple publish from approve

- [x] 1.1 Write failing tests for `POST /platform-versions/{id}/publish`: mirrors the current approve-triggered-publish behavior — gated by `approval_gate.run_if_approved`, returns the same outcome shape (`published`, `external_post_id`, `error_message`, `proposed_time`), 404 on unknown id, error when the platform version isn't `approved`
- [x] 1.2 Implement the endpoint to make 1.1 pass, reusing `PublishingUseCase` and `dependencies.get_publishing_use_case` as-is
- [x] 1.3 Write failing tests confirming `POST /platform-versions/{id}/approve` no longer triggers a publish attempt: response has no `publish_outcome`, the injected `PublishingUseCase`/publisher is never invoked, status stays `approved` (not `published`/`failed`) until the new endpoint is called
- [x] 1.4 Remove the `publishing_use_case.publish(...)` call from `approve()` to make 1.3 pass
- [x] 1.5 Update the existing publishing-wiring tests in `test_approval_endpoints.py` (added in the prior change) to match the new contract — they now belong to the new publish-endpoint test file; remove the now-incorrect assertions from `test_approval_endpoints.py`

## 2. Backend: Source-URL list

- [x] 2.1 Write failing tests for `ProjectMemoryStore.read_source_urls()` / `add_source_url(url)` / `remove_source_url(url)`: empty list by default, add appends, add is a no-op when the URL already exists (dedup), remove drops a matching entry
- [x] 2.2 Implement the three methods (backed by a new `fuentes.md` file) to make 2.1 pass
- [x] 2.3 Write failing tests for `GET /research/sources` (list), `POST /research/sources` (add, body `{url}`), `POST /research/sources/delete` (remove, body `{url}`)
- [x] 2.4 Implement the three endpoints to make 2.3 pass

## 3. Backend: Mandatory closing steps

- [x] 3.1 Review and Update Existing Unit Tests (MANDATORY)
- [x] 3.2 Run Unit Tests and Verify Database State (MANDATORY) — capture pre/post baseline, run targeted then full suite, create report at `openspec/changes/enhance-admin-panel-ui/reports/<YYYY-MM-DD>-step-3.2-unit-test-and-db-verification.md`
- [x] 3.3 Manual Endpoint Testing with curl (MANDATORY — AGENT MUST EXECUTE): seed an approved platform version, call the new `/publish` endpoint and verify the outcome/record; call `/research/sources` add/list/delete; confirm `POST .../approve` no longer produces a publish attempt; restore DB/memory-file state after; document in the phase report

## 3.5 Backend: Extend pending-chapters endpoint for post-approval visibility

Discovered during frontend implementation (section 5) — see design.md
Decision 7. `GET /chapters/pending` only returns chapters with at least one
`PENDING_REVIEW` platform version, so a chapter vanishes from the panel the
moment every platform version is approved — before the operator has had a
chance to use the new explicit publish action on it. Broaden the filter to
"has a `PENDING_REVIEW` or `APPROVED` platform version" (non-terminal),
keeping the endpoint path and response shape unchanged.

- [x] 3.5.1 Write a failing test: a chapter whose platform versions are ALL `APPROVED` (none `PENDING_REVIEW`) still appears in `GET /chapters/pending`'s response; a chapter whose platform versions are ALL terminal (`PUBLISHED`/`FAILED`/`REJECTED`) does not
- [x] 3.5.2 Widen the SQL filter in `list_pending_chapters` to make 3.5.1 pass
- [x] 3.5.3 Run the full backend suite to confirm no regressions; update this section's tasks.md checkboxes

## 4. Frontend: Visual system

- [x] 4.1 Port the mockup's (`frontend/mockup-panel-archivo-desclasificado.html`) CSS custom properties and layout/component classes into `frontend/src/app/globals.css`
- [x] 4.2 Rebuild `frontend/src/app/layout.tsx` with the sidebar app shell (brand mark, nav items for Pipeline / Calendario / Casos cubiertos / Configuración with active-state styling), wrapping every authenticated page; leave `/login` unwrapped

## 5. Frontend: Pipeline feed (replaces Approval Queue)

- [x] 5.1 Write failing tests for the new `PipelineFeed.tsx`: renders each pending case's document header (title, hook, pending/approved stamp), metadata row (agency, doc type, date, chapters), an expandable chapter-script + hashtags preview, per-network status chips, an individual "Publicar" action per approved platform version, bulk selection restricted to approved cases, a bulk "Publicar en `<network>`" action, and the "Ejecutar pipeline" trigger (disabled when no source URLs are configured)
- [x] 5.2 Add `runResearch()`, `publishPlatformVersion(id)`, and `fetchSourceUrls()` to `frontend/src/lib/api.ts`
- [x] 5.3 Implement `PipelineFeed.tsx` to make 5.1 pass
- [x] 5.4 Mount `PipelineFeed` at `/` (`frontend/src/app/page.tsx`); delete the old `frontend/src/app/approvals/` route, `ApprovalQueue.tsx`, and `ApprovalQueue.test.tsx`

## 6. Frontend: Configuración view

- [x] 6.1 Write failing tests for a new source-URL manager component: lists configured URLs, adds one, removes one
- [x] 6.2 Add `addSourceUrl(url)` / `removeSourceUrl(url)` to `frontend/src/lib/api.ts` (done alongside 5.2's api.ts edit)
- [x] 6.3 Implement the component to make 6.1 pass and mount it at `frontend/src/app/settings/page.tsx`

## 7. Frontend: Restyle Calendar and Cases views

- [x] 7.1 Update `Calendar.tsx` and `CasesView.tsx` markup/class names to the new visual system from `globals.css` — behavior unchanged, so no new tests are needed; re-run their existing test files to confirm they still pass unmodified

## 8. Update existing E2E specs for the new explicit-publish flow

- [x] 8.1 Update `frontend/e2e/approval-to-calendar.spec.ts`: navigate to `/` instead of `/approvals`, click "Approve" then a separate "Publicar" action before checking the calendar (the old single-step approve-publishes flow no longer applies)
- [x] 8.2 Review `frontend/e2e/covered-cases.spec.ts` against the new sidebar shell/layout and update selectors if the shell changes how `/cases` renders

## 9. Mandatory closing steps

- [x] 9.1 Review and Update Existing Unit Tests (MANDATORY) — both backend and frontend
- [x] 9.2 Run Unit Tests and Verify Database State (MANDATORY) — report at `openspec/changes/enhance-admin-panel-ui/reports/<YYYY-MM-DD>-step-9.2-unit-test-and-db-verification.md`
- [x] 9.3 E2E Testing (MANDATORY — AGENT MUST EXECUTE): run both updated Playwright specs against real, running frontend + backend servers; seed data as needed; restore all test data afterward; document in the phase report (note in the report if a Playwright MCP browser tool is unavailable and `@playwright/test` is used instead, per the precedent from the prior change)
- [x] 9.4 Update Technical Documentation (MANDATORY): `README.md` (new `/publish` endpoint, source-URL endpoints, new route map), `docs/backend-standards.md` (new endpoints), `docs/frontend-standards.md` (new visual system, new `PipelineFeed`/Configuración components, updated route list)
