---
description: Frontend development standards for the editorial admin panel (Next.js) — planned in Phase 6 of the archivo-desclasificado-pipeline OpenSpec change. Not yet implemented.
globs: ["frontend/src/**/*.{js,jsx,ts,tsx}", "frontend/tests/**/*.{ts,tsx}", "frontend/tsconfig.json", "frontend/package.json"]
alwaysApply: true
---

# Frontend Project Standards (Editorial Admin Panel)

## Status: not yet implemented

There is no frontend in this repository yet. This document sets the
standards for the admin panel to be built in **Phase 6** of the
`archivo-desclasificado-pipeline` OpenSpec change (see
`openspec/changes/archivo-desclasificado-pipeline/design.md` and
`specs/content-admin-panel/spec.md`) — it exists now so Phase 6 starts from
an agreed convention instead of improvising one. Update this document's
"Overview"/status line once `frontend/` actually exists.

## Overview

The panel is an internal, single-operator tool with three views: the
human-approval queue (its primary purpose — see design.md, this is the most
important screen given the mandatory approval gate), the editorial calendar,
and covered-cases management. It talks to the editorial FastAPI service
(`src/editorial/presentation/app.py`) over REST.

## Technology Stack

- **Next.js** (App Router) + **TypeScript** — per the proposal/design's
  explicit choice, not Create React App. Rationale: same stack decision as
  the rest of the project's tooling assumptions (Vercel-friendly, file-based
  routing suits a small fixed set of admin views).
- **Fetch/axios** for calling the FastAPI backend — pick one and use it
  consistently; don't mix.
- **Testing**:
  - Unit/component tests: Jest + React Testing Library.
  - **End-to-end: Playwright, driven via the Playwright MCP tools** — not
    Cypress. This project's mandatory task workflow
    (`docs/openspec-tasks-mandatory-steps.md`) requires the coding agent to
    execute E2E tests itself through Playwright MCP; do not introduce
    Cypress as it isn't part of that workflow.
- **Auth**: a minimal shared-credential gate (single token or basic auth) —
  see design.md's Open Questions. Decide and document the exact mechanism
  in this file when Phase 6 task 6.2 implements it; do not build a
  multi-user/roles system (explicit Non-Goal).

## Project Structure

```
frontend/
├── src/
│   ├── app/                # Next.js App Router pages
│   │   ├── approvals/      # Approval queue (source doc, story summary,
│   │   │                   # chapter script, platform versions, approve/reject)
│   │   ├── calendar/       # Editorial calendar (published/scheduled items)
│   │   └── cases/          # Covered-cases search/browse/edit
│   ├── components/         # Shared UI components
│   └── lib/                 # API client, types shared with the FastAPI schemas
├── tests/
│   └── e2e/                 # Playwright specs
├── package.json
└── tsconfig.json
```

## Coding Standards

- **Components**: functional components with hooks, TypeScript throughout
  (no `.js`/`.jsx` — this is a new app, not a migration).
- **Naming**: PascalCase for components, camelCase for variables/functions,
  UPPER_SNAKE_CASE for constants — standard TS/React conventions.
- **Language**: all code, comments, and UI copy in English (per CLAUDE.md
  Section 2), independent of the fact that the editorial *content* it
  displays (scripts, hooks) may itself be in Spanish.
- **API types**: derive/share request-response types from the FastAPI
  service's Pydantic models where practical, to avoid the two sides drifting.

## Approval Queue (primary view)

Per `specs/content-admin-panel/spec.md`:

- Every pending item must show: the source `Document`, the `Story` summary,
  the `Chapter` script, and **all** `PlatformVersion`s for that chapter —
  not a subset.
- Approve/reject actions call the backend and must reflect the resulting
  `PlatformVersion.status` transition immediately in the UI (the orchestrator
  polls this status to resume/halt publishing — see design.md Decision 5).

## Testing Standards

- **E2E scope**: cover the full approve → appears-in-calendar workflow, and
  the covered-cases search/edit workflow, per
  `docs/openspec-tasks-mandatory-steps.md` Step N+3 — these are the two
  workflows explicitly named in `tasks.md` Phase 6.
- **Data hygiene**: any test data created during E2E runs must be cleaned up
  and the database state restored, per the same mandatory-steps document.

## Development Workflow

To be filled in once `frontend/` is scaffolded (Phase 6, task 6.1) — expect
the standard `npm run dev` / `npm run build` / `npm test` / Playwright
commands, added here rather than assumed in advance.
