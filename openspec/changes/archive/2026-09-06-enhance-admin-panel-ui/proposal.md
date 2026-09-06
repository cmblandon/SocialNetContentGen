## Why

The Phase 6 admin panel is functionally correct but has two real problems in
practice: it's visually bare (three plain, unstyled pages), and — more
importantly — it has no way to *start* a pipeline run. The only way to
populate the Approval Queue today is a raw `curl POST /research/run` call,
which is exactly the confusion that prompted this change (a user with no
CLI/API familiarity had no path from "here's a document" to "something to
approve"). The user has supplied a reference mockup
(`frontend/mockup-panel-archivo-desclasificado.html`) that solves both
problems at once: a dark, "declassified case file" visual identity, and a
prominent "Ejecutar pipeline" action wired to the existing research/curation
pipeline, plus a clearer two-step approve-then-publish workflow with bulk
actions across cases.

## What Changes

- Redesign the panel's visual identity across all views per the reference
  mockup: dark ink background, a "paper" document-header treatment for each
  case, a rubber-stamp-style pending/approved indicator, sidebar navigation
  (Pipeline / Calendario / Casos cubiertos / Configuración) replacing the
  current flat page list.
- Consolidate the Approval Queue into a single **Pipeline** feed: one
  case-per-card (source document, hook, metadata, expandable chapter
  script/hashtags preview), matching the mockup's layout, replacing the
  current plain list.
- Add a **"Ejecutar pipeline" (Run Pipeline) action** in the Pipeline view,
  calling `POST /research/run` against an operator-configured list of
  source URLs, with live stage feedback (searching sources → curating →
  writing/adapting) and newly-created pending cases appended to the feed on
  completion. This directly replaces the curl-only trigger path.
- Add a **Configuración** view for managing the list of source URLs
  `POST /research/run` uses, so the operator never needs to hand-write a
  request body.
- **BREAKING**: decouple approval from automatic publishing. Today,
  approving a `PlatformVersion` immediately triggers a publish attempt
  (`POST /platform-versions/{id}/approve` calls `PublishingUseCase`
  synchronously). Going forward, approving only marks the case reviewed and
  ready; publishing to a given network becomes a distinct, explicit action
  the operator takes afterward — individually per case, or in bulk across
  every selected approved case for one network at a time, matching the
  mockup's per-network bulk-publish bar.
- Add bulk selection across approved cases, with one publish action per
  network applied to the whole selection.

## Capabilities

### New Capabilities
_None — this change restructures and extends existing capabilities; it
does not introduce a new pipeline stage._

### Modified Capabilities
- `content-admin-panel`: visual redesign, consolidated single-feed Pipeline
  view (replacing the separate Approval Queue page), a Run Pipeline trigger,
  a new Configuración view for source-URL management, and bulk multi-network
  publish actions across selected approved cases.
- `publishing`: publishing is no longer triggered automatically by approval
  — it becomes an explicit action (`POST /platform-versions/{id}/publish`,
  new), invokable individually or in bulk. The existing scheduling
  (`optimal_time` lookup/propose), single-attempt-no-retry, and
  `PublishRecord`/calendar-recording behavior are unchanged — only *when*
  publishing fires changes.
- `editorial-orchestration`: the requirement that approving "proceeds to
  publishing for that chapter" no longer holds automatically — approving
  now only transitions status to `approved`; a human takes a separate,
  explicit publish action afterward.

**Process note**: `content-admin-panel`, `publishing`, and
`editorial-orchestration` are capabilities introduced by the
`archivo-desclasificado-pipeline` change, which is fully implemented and
committed but not yet archived/synced into `openspec/specs/`. This change's
delta specs are written against that change's spec files (the current
source of truth for those capabilities) rather than `openspec/specs/`,
since the latter doesn't have them yet.

## Impact

- **Frontend** (`frontend/src/`): `ApprovalQueue.tsx` is replaced by a new
  Pipeline feed component; `Calendar.tsx` and `CasesView.tsx` get the same
  visual treatment; a new Configuración page/component; `src/lib/api.ts`
  gains `runResearch()`, `publishPlatformVersion()`, and source-URL-list
  CRUD calls; the app shell (`layout.tsx`) gains the sidebar navigation
  structure from the mockup.
- **Backend**: `POST /platform-versions/{id}/approve` no longer calls
  `PublishingUseCase`; a new `POST /platform-versions/{id}/publish`
  endpoint does instead (individually or looped for bulk from the
  frontend). A new small store for the operator-configured source-URL list
  (backing the Configuración view) — likely a new file in
  `ProjectMemoryStore` or a small dedicated table, decided in design.md.
- **Existing tests touched**: `test_approval_endpoints.py` (approve no
  longer triggers publishing — its publishing-wiring assertions move to a
  new publish-endpoint test file), `ApprovalQueue.test.tsx` (component
  replaced), the two Playwright E2E specs (the approve-then-calendar
  scenario now needs an explicit publish step).
- **No backend data model changes**: `PlatformVersion`/`PublishRecord`
  schemas are unchanged; only which endpoint transitions status changes.
