---
description: Frontend development standards for the editorial admin panel (Next.js) — implemented in Phase 6 of the archivo-desclasificado-pipeline OpenSpec change.
globs: ["frontend/src/**/*.{ts,tsx}", "frontend/e2e/**/*.ts", "frontend/tsconfig.json", "frontend/package.json"]
alwaysApply: true
---

# Frontend Project Standards (Editorial Admin Panel)

## Status: implemented (Phase 6; visual system and Pipeline feed redesigned by `enhance-admin-panel-ui`)

`frontend/` exists: Next.js 16 (App Router) + TypeScript, four views
(Pipeline, Calendario, Casos cubiertos, Configuración), a shared-token auth
gate, Jest + React Testing Library unit tests, and a Playwright E2E suite.
See the root `README.md`'s "Editorial Admin Panel" section for how to run
it locally against the backend.

## Overview

The panel is an internal, single-operator tool with four views, all behind
a persistent sidebar shell: the **Pipeline** feed (its primary purpose,
mounted at `/` — one case-per-card with document header, expandable
script/hashtags preview, case-level approve, per-network publish actions,
bulk multi-select publish, and the "Ejecutar pipeline" trigger), the
**Calendario**, **Casos cubiertos**, and **Configuración** (the
operator-managed source-URL list `/research/run` targets). It talks to the
editorial FastAPI service (`src/editorial/presentation/app.py`) over REST
via `src/lib/api.ts`.

Visual identity (`enhance-admin-panel-ui` design.md Decision 4): a dark
"declassified case file" theme ported near-verbatim from
`frontend/mockup-panel-archivo-desclasificado.html`'s CSS into
`src/app/globals.css` — ink background, paper-styled document headers, a
rubber-stamp pending/approved indicator. No design-system/component-library
adoption (no Tailwind, no MUI) — plain hand-written CSS classes, matching
this project's existing "no unnecessary dependency" posture.

## Technology Stack

- **Next.js 16** (App Router) + **TypeScript**, `src/` layout, path alias
  `@/*` → `src/*`.
- **Next.js 16 renamed `middleware.ts` to `proxy.ts`** — this project's auth
  gate (`src/proxy.ts`) uses the new convention; don't reintroduce a
  `middleware.ts` file.
- **Plain `fetch`** for calling the FastAPI backend (`src/lib/api.ts`) — no
  axios/SWR/React Query; the panel's data needs are simple enough that
  adding a fetching library isn't justified.
- **Testing**:
  - Unit/component tests: Jest (via `next/jest`) + React Testing Library +
    `@testing-library/user-event`. Client Components that fetch data are
    tested by mocking `@/lib/api` entirely (`jest.mock("@/lib/api")`) —
    Next's async Server Components aren't supported by Jest, which is why
    every interactive view here is a `"use client"` component.
  - **End-to-end: `@playwright/test`** (installed with `npx playwright
    install chromium --with-deps`), specs under `frontend/e2e/`. No
    Playwright MCP browser tool was available when this suite was built;
    if one becomes available later, prefer it, but `@playwright/test` run
    via `npm run test:e2e` / `npx playwright test` satisfies the same
    "agent executes real E2E tests itself" requirement.
  - Not Cypress — kept out of scope per `docs/openspec-tasks-mandatory-steps.md`.
- **Auth**: single shared token (`ADMIN_PANEL_TOKEN`), not per-user
  accounts and not basic auth (see "Auth Gate" below for the rationale) —
  no multi-user/roles system, per the explicit Non-Goal.

## Project Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx          # Pipeline feed (default/landing route)
│   │   ├── login/page.tsx    # Token entry form (unwrapped by AppShell)
│   │   ├── api/login/route.ts # Validates the token, sets the session cookie
│   │   ├── calendar/page.tsx
│   │   ├── cases/page.tsx
│   │   ├── settings/page.tsx # Configuración (source-URL manager)
│   │   └── globals.css       # Visual system (see Overview above)
│   ├── components/
│   │   ├── AppShell.tsx        # Sidebar nav shell; excludes /login. + no test (thin wrapper)
│   │   ├── PipelineFeed.tsx    # + __tests__/PipelineFeed.test.tsx
│   │   ├── SourceUrlManager.tsx # + __tests__/SourceUrlManager.test.tsx
│   │   ├── Calendar.tsx        # + __tests__/Calendar.test.tsx
│   │   └── CasesView.tsx       # + __tests__/CasesView.test.tsx
│   ├── lib/
│   │   └── api.ts             # fetch wrapper + shared types for every endpoint
│   └── proxy.ts               # Auth gate (Next.js 16 "proxy", not "middleware")
├── e2e/
│   ├── approval-to-calendar.spec.ts
│   └── covered-cases.spec.ts
├── jest.config.ts / jest.setup.ts
├── playwright.config.ts
├── .env.local.example         # NEXT_PUBLIC_API_BASE_URL, ADMIN_PANEL_TOKEN
├── package.json
└── tsconfig.json
```

The old `ApprovalQueue.tsx` (and its `/approvals` route) was removed by
`enhance-admin-panel-ui` — `PipelineFeed.tsx` replaces it at `/`, the new
default/landing route.

## Auth Gate

Decision: a **single shared token**, not basic auth. Rationale (recorded
here since design.md left this as an Open Question): basic auth's browser
credential caching makes logout awkward and gives no clean UX for entering
a token; a plain login form + httpOnly cookie is simpler for a
single-operator internal tool and easy to rotate (change `ADMIN_PANEL_TOKEN`
and every existing session cookie stops matching).

Flow: `POST /api/login` compares the submitted token to
`process.env.ADMIN_PANEL_TOKEN` and, on match, sets an httpOnly
`admin_session` cookie whose value is the token itself. `src/proxy.ts`
checks that cookie on every request except `/login`, `/api/login`, and
Next.js internals, redirecting to `/login` otherwise.

## Coding Standards

- **Components**: functional components with hooks, TypeScript throughout.
- **Naming**: PascalCase for components, camelCase for variables/functions,
  UPPER_SNAKE_CASE for constants.
- **Language**: all code, identifiers, and comments in English (per
  CLAUDE.md Section 2). **UI copy exception** (`enhance-admin-panel-ui`
  design.md Decision 5): visible label text may be Spanish, matching the
  reference mockup and this panel's Spanish-speaking operator audience
  (nav labels, button text like "Aprobar"/"Publicar en \<network\>", the
  "Configuración" view) — this corrects the original Phase 6 version of
  this rule, which predated the mockup and had no real UI copy to speak
  of yet. Route *slugs* still stay English (`/settings`, not
  `/configuracion`) per this project's code-in-English convention; only
  the rendered label is Spanish. Test names, code comments, and variable
  names remain English regardless of what a component's copy displays.
- **API types**: `src/lib/api.ts`'s interfaces are hand-kept in sync with
  the FastAPI Pydantic response models (`DocumentSummary`,
  `PlatformVersionSummary`, `PendingChapter`, `PublishRecord`, `CaseEntry`,
  ...) — there is no shared codegen between the two; when a backend
  response model changes, update `api.ts` in the same change.

## Pipeline feed (primary view)

Per `specs/content-admin-panel/spec.md`, backed by `GET /chapters/pending`
(added in Phase 6, filter widened by `enhance-admin-panel-ui` design.md
Decision 7 to include `approved` — not just `pending_review` — platform
versions, so a case stays visible after approval until every platform
version reaches a terminal state):

- Every listed case shows the source `Document` (title, hook/story summary,
  agency, doc type, date), a rubber-stamp "Pendiente"/"Aprobado" indicator,
  the chapter title, and an expandable script + hashtags preview.
- A case-level "Aprobar" button calls `POST /platform-versions/{id}/approve`
  for every still-`pending_review` platform version of that chapter in one
  click — approving no longer triggers a publish (that's now the separate
  `POST /platform-versions/{id}/publish` action, per design.md Decision 1).
  Once every platform version is decided, the stamp switches to "Aprobado"
  and the case becomes eligible for bulk selection.
- Each approved-but-not-yet-published platform version gets its own
  "Publicar en \<network\>" button (individual publish); published ones show
  a read-only status chip instead.
- Bulk selection (checkbox, disabled until a case is fully approved) plus a
  sticky bulk-action bar publish one chosen network for every selected
  case in one operator action — implemented as N sequential
  `publishPlatformVersion` calls client-side, not a dedicated bulk
  endpoint (design.md Decision 2); one case's failure doesn't block the
  others.
- "Ejecutar pipeline" calls `GET /research/sources` then
  `POST /research/run` with that list, showing a status pill while the run
  is in flight; disabled with no configured source URLs (see
  Configuración below).
- A "Tema (opcional)" text input next to "Ejecutar pipeline"
  (`research-query-scoping`) lets the operator scope a run to a topic —
  sent as `query` in the `POST /research/run` body only when non-empty
  (trimmed client-side in both `PipelineFeed.tsx` and `runResearch()`
  itself); leaving it blank reproduces the exact pre-existing behavior.

## Configuración

Backed by `GET/POST /research/sources` and `POST /research/sources/delete`
— `SourceUrlManager.tsx` lists, adds, and removes the URLs "Ejecutar
pipeline" targets. Mounted at `/settings`.

## Testing Standards

- **E2E scope**: the full approve → publish → appears-in-calendar workflow
  (`e2e/approval-to-calendar.spec.ts` — two explicit steps since
  `enhance-admin-panel-ui`: "Aprobar" then a separate "Publicar en
  \<network\>") and the covered-cases search/edit workflow
  (`e2e/covered-cases.spec.ts`), per
  `docs/openspec-tasks-mandatory-steps.md` Step N+3. Both specs log in and
  land on `/` (the Pipeline feed), not `/approvals` (removed).
- **Gotcha**: don't `page.goto()` immediately after clicking an action that
  fires a `fetch` (e.g. "Publicar en \<network\>") — a full navigation can
  abort the in-flight request before the backend receives it. Wait for a
  visible state change that only happens after the request resolves (e.g.
  the button being replaced by a status chip) first.
- **Data hygiene**: E2E runs need a real backend with seeded data (a
  pending chapter, an `optimal_time:<platform>=HH:MM` line in
  `calendario.md`, and a couple of `casos_cubiertos.md` entries) — reset
  `data/knowledge_base/editorial.sqlite` and
  `data/knowledge_base/editorial_memory/` before seeding to avoid stale
  duplicate data breaking Playwright's strict-mode element matching (this
  happened once during Phase 6 development).
- **CORS**: the backend must allow `http://localhost:3000` (see
  `docs/backend-standards.md`) or every E2E/manual browser test against a
  real server will fail outright.

## Development Workflow

```bash
cd frontend
npm install
cp .env.local.example .env.local   # fill in ADMIN_PANEL_TOKEN

npm run dev              # http://localhost:3000
npm run build             # production build + type-check
npm test                  # Jest unit tests
npm run test:e2e          # Playwright E2E (needs both servers running)
```

See the root `README.md`'s "Editorial Admin Panel" section for the full
local-dev walkthrough (starting the backend, applying migrations, seeding
data for E2E runs).
