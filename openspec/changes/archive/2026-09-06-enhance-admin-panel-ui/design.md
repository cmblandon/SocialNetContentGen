## Context

The Phase 6 admin panel (`frontend/`) is functionally complete but was
never given a visual pass — three plain pages (Approval Queue, Calendar,
Cases) with no styling beyond default HTML. More importantly, it exposed a
real usability gap: there is no way to *start* a pipeline run from the UI.
The only trigger is `POST /research/run` via curl, which is exactly the
friction that prompted this change.

The user supplied a reference mockup
(`frontend/mockup-panel-archivo-desclasificado.html`) — a static,
vanilla-JS prototype with a dark "declassified case file" visual identity,
sidebar navigation, a "Ejecutar pipeline" trigger with live status, and a
per-case card with an expandable script preview and a per-network
publish-status row supporting bulk multi-select publishing. This design
adopts that direction and translates it into the existing Next.js/FastAPI
architecture.

This change also surfaces a real behavioral decision buried in the
mockup: approving a case and publishing it to a network are shown as two
separate steps (approve now, publish per network later, possibly in
bulk), whereas the current implementation auto-publishes the instant a
`PlatformVersion` is approved. That's the one non-visual, breaking part of
this change.

## Goals / Non-Goals

**Goals:**
- Adopt the mockup's visual identity (dark ink theme, paper-styled
  document header, rubber-stamp status indicator, sidebar nav) across all
  views, reusing its CSS as closely as practical rather than
  reinterpreting it through a component library.
- Let an operator start a pipeline run from the UI against a
  UI-configurable list of source URLs — no more hand-written curl bodies.
- Decouple "approved" from "published": approving marks a platform
  version eligible; publishing to a given network is a separate, explicit
  action, invokable individually or in bulk across selected approved
  cases for one network at a time.

**Non-Goals:**
- No change to the underlying `Document → Story → Chapter →
  PlatformVersion → PublishRecord` schema — only which endpoint transitions
  `PlatformVersion.status` to attempt a publish changes.
- No real bulk backend endpoint — "bulk publish" is the frontend looping
  individual `POST /platform-versions/{id}/publish` calls. A dedicated
  bulk endpoint is future work if volume ever justifies it.
- No design-system/component-library adoption (no Tailwind, no MUI) — the
  mockup's own hand-written CSS is the design system for this change,
  matching the frontend's existing "no unnecessary dependency" posture
  (`docs/frontend-standards.md`).
- No autonomous/cron triggering of pipeline runs — still an explicit,
  operator-initiated action (unchanged Non-Goal from the original
  `archivo-desclasificado-pipeline` change).

## Decisions

### 1. Publishing becomes an explicit endpoint, not a side effect of approval
Remove the `publishing_use_case.publish(...)` call from
`POST /platform-versions/{id}/approve`. Add
`POST /platform-versions/{id}/publish`, which does exactly what that call
used to do (invoke `PublishingUseCase.publish`, gated by
`approval_gate.run_if_approved`, returning the same outcome shape) — moved,
not rewritten. This is a small, low-risk backend diff: the gate, the
scheduling logic, and the recording behavior are all untouched; only which
route triggers them changes.
**Alternative considered**: keep auto-publish and add a separate
"unpublish"/undo action instead — rejected, because the mockup's model
(and the more familiar editorial mental model) is "approve now, decide
when/where to publish later," not "publish immediately, then reconsider."

### 2. Bulk publish is N sequential frontend calls, not a new bulk endpoint
The frontend's bulk-publish action calls
`POST /platform-versions/{id}/publish` once per selected case's matching
platform version, updating each card's status independently as its call
resolves. A failure on one case does not block the others (matches
`specs/publishing`'s existing single-attempt-independent-failure
semantics).
**Alternative considered**: a `POST /platform-versions/bulk-publish`
endpoint taking a list of ids — rejected for now as unnecessary complexity
for a single-operator tool; revisit if bulk sizes grow large enough that
sequential round-trips become a real problem (explicit Non-Goal above).

### 3. Source-URL list: a new plain-text memory file, not a database table
Add `ProjectMemoryStore.read_source_urls() / add_source_url(url) /
remove_source_url(url)`, backed by a new `fuentes.md` file (one URL per
line), following the exact pattern already established for
`casos_cubiertos.md`/`calendario.md`. New endpoints:
`GET /research/sources` (list), `POST /research/sources` (add, body
`{url}`), `POST /research/sources/delete` (remove, body `{url}`) — a
`POST .../delete` rather than `DELETE` with a body, avoiding the
still-inconsistent cross-client support for bodies on `DELETE` requests.
`add_source_url` is a no-op if the URL is already present (dedup on add,
no other validation — consistent with this project's existing
plain-file, minimal-validation posture for editorial memory).
**Alternative considered**: a `SourceUrl` SQL table — rejected; this data
has the exact same shape and durability needs as the existing
memory-store files (a short, human-editable, append-mostly list), and
introducing a table for it would be inconsistent with how every other
piece of "operator-managed list" data in this project is stored.

### 4. Visual system: port the mockup's CSS near-verbatim into the Next.js app
Move the mockup's `<style>` block into `frontend/src/app/globals.css`
(CSS custom properties for the ink/paper/accent palette, the stamp/paper
treatments, the sidebar and card layout classes), and rewrite its vanilla
JS DOM manipulation as React state/JSX in new components — the visual
output should be near-identical to the mockup; only the implementation
substrate changes (React components + real API calls instead of a
hardcoded `CASES` array and `setInterval` simulation).
**Alternative considered**: reinterpret the design through Tailwind
utility classes — rejected; it would mean re-deriving every visual detail
from scratch instead of reusing working CSS, for no benefit given this
project already chose "no Tailwind" when scaffolding the frontend.

### 5. Route/component restructuring
- `ApprovalQueue.tsx` → replaced by a new `PipelineFeed.tsx`, mounted at
  `/` (the mockup treats "Pipeline" as the default/landing view, not a
  secondary page reached via a plain link list). The existing `/approvals`
  route is removed; anything relying on it (the two Playwright specs)
  moves to `/`.
- `Calendar.tsx` and `CasesView.tsx` keep their routes (`/calendar`,
  `/cases`) and behavior; only their visual styling changes to match the
  new system.
- New `/settings` route (English slug for the URL, matching this
  project's code-in-English convention; the *label* shown in the sidebar
  is "Configuración," matching the mockup's Spanish UI copy — see
  `docs/frontend-standards.md`'s existing rule that UI copy may be Spanish
  while code/identifiers stay English) hosts the source-URL manager.
- `layout.tsx` gains the persistent sidebar shell (brand mark, nav items
  for Pipeline/Calendario/Casos cubiertos/Configuración) wrapping every
  page, replacing the current bare `<body>{children}</body>`.
- The `/login` page and its own layout are unaffected — the sidebar shell
  only wraps authenticated pages.

### 6. "Ejecutar pipeline" reads the configured source list, not a text input
Clicking the button calls `GET /research/sources` (if not already
cached in state) then `POST /research/run` with that list. If the list is
empty, the button is disabled with a hint pointing at Configuración,
rather than allowing a no-op run.

### 7. Extend `GET /chapters/pending` so approved-but-unpublished chapters stay visible
Discovered during frontend implementation (section 5): the existing
`GET /chapters/pending` (Phase 6) only returns chapters that still have at
least one `PlatformVersion` in `PENDING_REVIEW`. Once every platform
version of a chapter has been approved, the chapter drops out of the
response entirely — but this change's "Publish an approved case" and
"Bulk-publish selected approved cases" requirements
(`specs/content-admin-panel/spec.md`) both assume the operator can still
see and select that case in the panel afterward, since the explicit
publish action must be invoked from somewhere. Fix: broaden the endpoint's
filter from "has a `PENDING_REVIEW` platform version" to "has a
`PENDING_REVIEW` **or** `APPROVED` platform version" (i.e., still has at
least one non-terminal platform version) — a chapter drops out only once
every platform version has reached a terminal state (`PUBLISHED`, `FAILED`,
or `REJECTED`). The endpoint path/response shape (`PendingChapterResponse`)
is unchanged; only the SQL filter changes. Renaming the endpoint was
considered and rejected as unnecessary churn for a one-clause query change.
**Alternative considered**: a second, separate endpoint for "approved,
awaiting publish" cases — rejected because the Pipeline feed needs one
unified list (mixed pending/approved cases in one feed, per the mockup),
not two lists to merge client-side.

## Risks / Trade-offs

- **[Risk]** Decoupling approve/publish is a breaking behavior change for
  two existing Playwright specs and one backend endpoint test →
  **[Mitigation]** both are updated in this same change (tasks.md), and
  the full suite (backend + frontend + E2E) is re-run before considering
  the change done.
- **[Risk]** A large, all-at-once visual diff across every frontend file
  increases regression surface → **[Mitigation]** reuse the mockup's CSS
  verbatim wherever possible instead of redesigning from scratch, and keep
  the underlying data-fetching logic in each view unchanged except where
  this design explicitly calls for new endpoints.
- **[Risk]** Sequential bulk-publish calls give no atomicity — a bulk
  action can partially succeed → **[Accepted trade-off]**: this matches
  `specs/publishing`'s existing per-item independent-failure model; the UI
  must reflect per-case outcomes individually rather than a single
  bulk-success/failure state.
- **[Risk]** The source-URL list has no format validation → **[Mitigation]**
  acceptable for an internal single-operator tool; `research_agent`'s
  existing domain allowlist already discards anything not from an official
  source, so a malformed/irrelevant entry here is caught downstream, not
  silently acted upon.

## Migration Plan

1. Backend: add `POST /platform-versions/{id}/publish`; remove the
   publish call from `approve()`; add `ProjectMemoryStore` source-URL
   methods + `GET/POST /research/sources` + `POST /research/sources/delete`.
2. Frontend: port the visual system into `globals.css` and the app shell
   (`layout.tsx` sidebar).
3. Frontend: build `PipelineFeed.tsx` (replaces `ApprovalQueue.tsx`) at
   `/`, wired to `GET /chapters/pending`, the new publish endpoint, bulk
   selection, and the "Ejecutar pipeline" trigger.
4. Frontend: build the `/settings` Configuración view for the source-URL
   list.
5. Frontend: restyle `Calendar.tsx`/`CasesView.tsx` to the new visual
   system (no behavioral change).
6. Update `test_approval_endpoints.py` (remove publish-wiring assertions,
   add a new `test_publish_endpoint.py`), and both Playwright specs (add
   an explicit publish step; update the route from `/approvals` to `/`).
7. Mandatory verification: full unit-test run (backend + frontend), curl
   testing for the new endpoints, Playwright E2E re-run, documentation
   updates — same discipline as every prior phase.

Rollback: every piece here is additive-or-swapped behind its own
route/endpoint; reverting the commit(s) for this change fully restores the
Phase 6 behavior (auto-publish-on-approve, plain-page UI), since no data
model or migration is involved.

## Open Questions

- The three capabilities this change modifies
  (`content-admin-panel`, `publishing`, `editorial-orchestration`) belong
  to `archivo-desclasificado-pipeline`, which is fully implemented but not
  yet archived into `openspec/specs/`. Should that change be archived
  before or after this one lands? This change's delta specs are written
  against its change-local spec files either way (see proposal.md's
  process note), so it isn't blocking — but archive ordering affects
  which change's history "owns" these capabilities going forward.
- Should the source-URL list eventually support per-URL metadata (e.g. a
  label, or a "last run" timestamp) once the Configuración view exists, or
  stay a bare list of strings? Deferred — start with the bare list; the
  spec only requires add/remove/list.
