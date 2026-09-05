---
description: Frontend development standards for the editorial admin panel (Next.js) — implemented in Phase 6 of the archivo-desclasificado-pipeline OpenSpec change.
globs: ["frontend/src/**/*.{ts,tsx}", "frontend/e2e/**/*.ts", "frontend/tsconfig.json", "frontend/package.json"]
alwaysApply: true
---

# Frontend Project Standards (Editorial Admin Panel)

## Status: implemented (Phase 6)

`frontend/` exists: Next.js 16 (App Router) + TypeScript, three views
(Approval Queue, Editorial Calendar, Covered Cases), a shared-token auth
gate, Jest + React Testing Library unit tests, and a Playwright E2E suite.
See the root `README.md`'s "Editorial Admin Panel" section for how to run
it locally against the backend.

## Overview

The panel is an internal, single-operator tool with three views: the
human-approval queue (its primary purpose — see design.md, this is the most
important screen given the mandatory approval gate), the editorial calendar,
and covered-cases management. It talks to the editorial FastAPI service
(`src/editorial/presentation/app.py`) over REST via `src/lib/api.ts`.

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
│   │   ├── page.tsx          # Home: links to the three views
│   │   ├── login/page.tsx    # Token entry form
│   │   ├── api/login/route.ts # Validates the token, sets the session cookie
│   │   ├── approvals/page.tsx
│   │   ├── calendar/page.tsx
│   │   └── cases/page.tsx
│   ├── components/
│   │   ├── ApprovalQueue.tsx  # + __tests__/ApprovalQueue.test.tsx
│   │   ├── Calendar.tsx       # + __tests__/Calendar.test.tsx
│   │   └── CasesView.tsx      # + __tests__/CasesView.test.tsx
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
- **Language**: all code, comments, and UI copy in English (per CLAUDE.md
  Section 2), independent of the fact that the editorial *content* it
  displays (scripts, hooks) may itself be in Spanish.
- **API types**: `src/lib/api.ts`'s interfaces are hand-kept in sync with
  the FastAPI Pydantic response models (`DocumentSummary`,
  `PlatformVersionSummary`, `PendingChapter`, `PublishRecord`, `CaseEntry`,
  ...) — there is no shared codegen between the two; when a backend
  response model changes, update `api.ts` in the same change.

## Approval Queue (primary view)

Per `specs/content-admin-panel/spec.md`, backed by `GET /chapters/pending`
(added in Phase 6 — the Phase 3 approve/reject endpoints alone don't expose
read context):

- Every pending item shows the source `Document`, the `Story` summary, the
  `Chapter` script, and **all** `PlatformVersion`s for that chapter.
- Approving a platform version calls `POST /platform-versions/{id}/approve`,
  which (Phase 5) triggers publishing immediately server-side — the UI
  shows the returned `publish_outcome` (published / proposed time / failed)
  inline, without removing the item's card; only the Approve/Reject buttons
  for that platform version disappear once decided.

## Testing Standards

- **E2E scope**: the full approve → appears-in-calendar workflow
  (`e2e/approval-to-calendar.spec.ts`) and the covered-cases search/edit
  workflow (`e2e/covered-cases.spec.ts`), per
  `docs/openspec-tasks-mandatory-steps.md` Step N+3.
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
