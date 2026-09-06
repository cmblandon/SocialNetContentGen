# Backend Implementation Plan — Tasks 1.1–1.5 (Decouple publish from approve)

Scope: `openspec/changes/enhance-admin-panel-ui/tasks.md` section
"1. Backend: Decouple publish from approve" (tasks 1.1–1.5 only).
This plan does **not** cover section 2 (source-URL list) or sections 3+/4+
(closing steps, frontend). See `design.md` Decision 1 for the rationale —
this is a "moved, not rewritten" change: the gate, scheduling, and
recording logic in `PublishingUseCase` are untouched; only which route
triggers `publish()` changes.

This is a plan only — no code should be written from this document without
following the TDD order below (failing test → run → minimal implementation
→ run again).

## Baseline (verified before planning)

- `pytest tests/unit/test_approval_endpoints.py tests/unit/test_publishing_use_case.py -q`
  → 14 passed, 0 failed. Confirm this again right before starting, and
  again after each numbered step below.
- Current `approve()` in
  `src/editorial/presentation/routers/approval.py` (lines 27–50) takes a
  `publishing_use_case: PublishingUseCase = Depends(get_publishing_use_case)`
  parameter, calls `publishing_use_case.publish(session, platform_version_id)`
  right after `approve_platform_version(...)` succeeds, and nests the result
  under a `"publish_outcome"` key in the response body.
- `PublishingUseCase.publish(session, platform_version_id)` (in
  `src/editorial/application/publishing_use_case.py`) is gated internally by
  `approval_gate.run_if_approved(session, platform_version_id, action=...)`
  (`src/editorial/application/approval_gate.py:104`), which raises
  `ApprovalRequiredError` (a plain `Exception` subclass, not an HTTP
  exception) when the `PlatformVersion.status` isn't `ApprovalStatus.APPROVED`.
  It returns a `PublishOutcome` dataclass with exactly four fields:
  `published: bool`, `external_post_id: Optional[str]`,
  `error_message: Optional[str]`, `proposed_time: Optional[str]`.
- `get_publishing_use_case` (in `src/editorial/presentation/dependencies.py:33`)
  is the existing FastAPI provider — wires a real `PostizPublisherAdapter`
  + `ProjectMemoryStore`. Reuse exactly as-is; do not modify this file.
- `AlreadyDecidedError` (raised by `approve_platform_version`/
  `reject_platform_version` in `approval_gate.py` when status isn't
  `PENDING_REVIEW`) is already mapped to **HTTP 409** in `approve()`/
  `reject()` (`approval.py` lines 36–37, 58–59). This is the only existing
  precedent in the codebase for mapping a domain error to a status code —
  use it as the pattern for `ApprovalRequiredError` too (see Decision below).
- `_ensure_exists(session, platform_version_id)` (`approval.py:63`) already
  raises `HTTPException(404, "PlatformVersion not found")` and is reused
  verbatim by both existing routes — reuse it for the new route too.

## Decisions to record before coding (flagged here so they aren't
re-litigated mid-implementation)

1. **HTTP status for "not approved yet"**: map `ApprovalRequiredError` →
   **409 Conflict**, matching the existing `AlreadyDecidedError` → 409
   precedent. Both errors represent "the resource's current status
   disagrees with the status this operation requires" — same conceptual
   class of error, same status code. (400 would be wrong — the request
   itself is well-formed; it's the resource's *state* that's the issue.)
2. **Where the new endpoint lives**: add it directly to the existing
   `src/editorial/presentation/routers/approval.py` file, in the existing
   `router` (prefix `/platform-versions`), immediately after `approve()`
   and before `reject()`. Do **not** create a new router file. Rationale:
   `approval.py` already imports `PublishingUseCase`,
   `get_publishing_use_case`, and `_ensure_exists` — everything the new
   endpoint needs is already in scope, and design.md explicitly frames this
   as "moved, not rewritten." Every other router in this codebase
   (`cases.py`, `pending_chapters.py`, `publish_records.py`, `research.py`)
   is one router per *resource concept*, and `/platform-versions/{id}/publish`
   is unambiguously about the same resource (`PlatformVersion`) as
   `/approve` and `/reject`, just a different lifecycle transition on it.
3. **Response shape**: the new endpoint returns the `PublishOutcome` fields
   **flat** at the top level of the JSON body — `{"published": ..., "external_post_id": ..., "error_message": ..., "proposed_time": ...}`
   — not nested under a `"publish_outcome"` key. That nesting only existed
   because it was a secondary side-effect embedded in the approve response;
   here, producing the outcome *is* the endpoint's entire job, so nesting it
   under its own name is redundant. (Do not add an `"id"`/`"status"` field
   to this response unless a task explicitly asks for one — 1.1 only lists
   the four outcome fields as required assertions.)

## Files touched

| File | Change |
|---|---|
| `tests/unit/test_publish_endpoint.py` (new) | Task 1.1 — failing tests for the new endpoint |
| `src/editorial/presentation/routers/approval.py` | Tasks 1.2, 1.4 — add `publish()` route handler; remove the publish call + now-unused param from `approve()` |
| `tests/unit/test_approval_endpoints.py` | Tasks 1.3, 1.5 — add no-publish-side-effect assertions; remove the two now-incorrect tests and unused fixtures/imports |
| `openspec/changes/enhance-admin-panel-ui/tasks.md` | Check off `[x]` 1.1–1.5 as each completes |

No changes to: `publishing_use_case.py`, `approval_gate.py`,
`dependencies.py`, `app.py` (no new router object is created, so no new
`include_router` call is needed), or any model/schema file.

## Step-by-step plan

### Task 1.1 — `tests/unit/test_publish_endpoint.py` (new file)

Copy the reusable fixture scaffolding from
`tests/unit/test_approval_endpoints.py` (the module docstring's naming
rationale — "Named /platform-versions/{id}/... rather than
/cycles/{id}/..." — is also worth carrying over into this new file's
docstring for consistency). Specifically duplicate:
- `FakePublishingUseCase` class (records calls in `self.calls`, returns a
  configured `PublishOutcome`)
- `test_engine` fixture (in-memory SQLite via `StaticPool`)
- `client` fixture (overrides `get_session` and `get_publishing_use_case`)
- `pending_platform_version_id` fixture (builds a `Document` → `Story` →
  `Chapter` → 4×`PlatformVersion` via `persist_story`, all starting
  `PENDING_REVIEW`)
- Needed imports: `pytest`, `TestClient`, `create_engine`, `Session`,
  `sessionmaker`, `StaticPool`, `persist_story`, the `core.entities`
  dataclasses (`ChapterDraft`, `FacebookAdaptation`, `InstagramAdaptation`,
  `PlatformAdaptations`, `StoryDraft`, `TikTokAdaptation`, `XAdaptation`),
  `ApprovalStatus`/`Base`/`Document`/`PlatformVersion` from
  `infrastructure.persistence.models`, `PublishOutcome` from
  `application.publishing_use_case`, `get_session`, `app`,
  `get_publishing_use_case`.

New fixture needed beyond what's copied: an **approved** platform version
id, since `/publish` (unlike `/approve`) requires the version to already be
`approved`. Add:

```python
@pytest.fixture
def approved_platform_version_id(test_engine, pending_platform_version_id):
    with Session(test_engine) as session:
        platform_version = session.get(PlatformVersion, pending_platform_version_id)
        platform_version.status = ApprovalStatus.APPROVED
        session.commit()
    return pending_platform_version_id
```

Write these test cases (all initially failing since the route doesn't
exist yet — expect 404 "Not Found" from FastAPI's own routing, not the
app's `_ensure_exists` 404, until 1.2 lands):

1. `test_publish_invokes_use_case_and_returns_the_outcome_flat(client, approved_platform_version_id, fake_publishing_use_case)`
   — POST `/platform-versions/{approved_platform_version_id}/publish`;
   assert `response.status_code == 200`; assert
   `fake_publishing_use_case.calls == [approved_platform_version_id]`;
   assert `response.json() == {"published": False, "external_post_id": None, "error_message": None, "proposed_time": "12:00"}`
   (matching the `fake_publishing_use_case` fixture's configured outcome —
   reuse the same `PublishOutcome(published=False, proposed_time="12:00")`
   default). Critically assert there is **no** `"publish_outcome"` key and
   no `"id"`/`"status"` wrapper — the body *is* the outcome.
2. `test_publish_unknown_id_returns_404(client)` — POST to
   `/platform-versions/does-not-exist/publish`; assert 404. (This exercises
   `_ensure_exists`, so use a real path shape, not FastAPI's route-miss
   404 — both happen to be 404 but for different reasons; this test's
   intent is the app-level "no such PlatformVersion" branch, which only
   exists once 1.2 lands and calls `_ensure_exists`.)
3. `test_publish_on_a_not_yet_approved_version_returns_409(client, pending_platform_version_id)`
   — POST to `/platform-versions/{pending_platform_version_id}/publish`
   where the version is still `PENDING_REVIEW` (not approved); this needs
   the **real** `PublishingUseCase` (not the fake) so that
   `run_if_approved`'s `ApprovalRequiredError` actually fires — either:
   - override `get_publishing_use_case` in this one test via
     `app.dependency_overrides[get_publishing_use_case] = lambda: PublishingUseCase(publisher=<fake ISocialPublisher>, memory_store=<fake/real ProjectMemoryStore>)`, or
   - simpler: don't override `get_publishing_use_case` for this specific
     test at all and instead give this test its own `client`-like setup
     that only overrides `get_session`, using the real
     `get_publishing_use_case` dependency chain but with a stub publisher.
   Recommended approach: add a second, narrower fixture in this file,
   e.g. `client_with_real_publishing_use_case(test_engine)`, that overrides
   only `get_session` (leaving `get_publishing_use_case` un-overridden so
   the real `run_if_approved` gate runs) — but the real
   `get_publishing_use_case` depends on `get_publisher`
   (`PostizPublisherAdapter`, needs real API keys) and `get_memory_store`
   (writes to `EDITORIAL_MEMORY_DIR` on disk), which is undesirable in a
   unit test. **Simplest correct option**: don't go through the DI-real
   chain at all — directly construct `PublishingUseCase` with a minimal
   fake `ISocialPublisher` (never actually called, since the gate raises
   before reaching it) and a fake/real-but-tmp `ProjectMemoryStore`
   (also never reached), and override `get_publishing_use_case` to return
   that instance for this one test. Since `ApprovalRequiredError` is raised
   by `run_if_approved` *before* `self._publisher`/`self._memory_store` are
   ever touched (see `publish()`'s `_do_publish` closure — it only calls
   `_resolve_optimal_time_of_day`/`_publish_now` from inside the
   `action` callback that `run_if_approved` only invokes post-gate), a
   `ProjectMemoryStore(memory_dir=<any tmp_path>)` and a trivial
   `ISocialPublisher`-shaped stub (or even `object()` cast, but prefer a
   proper stub for type-honesty) are both safe to construct without any
   real I/O happening in this test. Assert `response.status_code == 409`.
4. Confirm this file has **no** test asserting anything about `/approve`'s
   behavior — that stays entirely in `test_approval_endpoints.py` (task 1.3).

Run: `pytest tests/unit/test_publish_endpoint.py -v` — expect all new
tests to fail (route doesn't exist / `_ensure_exists` not reached / no
409 mapping yet) before moving to 1.2.

### Task 1.2 — implement the endpoint

In `src/editorial/presentation/routers/approval.py`:

1. Add `ApprovalRequiredError` to the existing import from
   `src.editorial.application.approval_gate` (alongside
   `AlreadyDecidedError`, `approve_platform_version`,
   `reject_platform_version`).
2. Insert a new route handler between `approve()` and `reject()`:

```python
@router.post("/{platform_version_id}/publish")
def publish(
    platform_version_id: str,
    session: Session = Depends(get_session),
    publishing_use_case: PublishingUseCase = Depends(get_publishing_use_case),
) -> dict:
    _ensure_exists(session, platform_version_id)
    try:
        outcome = publishing_use_case.publish(session, platform_version_id)
    except ApprovalRequiredError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return {
        "published": outcome.published,
        "external_post_id": outcome.external_post_id,
        "error_message": outcome.error_message,
        "proposed_time": outcome.proposed_time,
    }
```

3. Update the module docstring (lines 1–10) — it currently says approving
   "invokes PublishingUseCase immediately after recording the approval";
   that's no longer true after 1.4. Rewrite it to describe the current
   two-step model, e.g.: note that `approve()` only records the approval
   decision per the gate, and that `publish()` is the explicit,
   separate action that invokes `PublishingUseCase` (gated by
   `run_if_approved`), matching `design.md` Decision 1 of
   `enhance-admin-panel-ui`. Keep the reference to
   `specs/editorial-orchestration/spec.md` but correct the quoted
   behavior description to match the new contract, and note that this
   requirement itself is being amended by the delta spec in
   `openspec/changes/enhance-admin-panel-ui/specs/editorial-orchestration/spec.md`.

Run: `pytest tests/unit/test_publish_endpoint.py -v` — all tests from 1.1
should now pass. Also run the full existing `test_approval_endpoints.py`
to confirm nothing there broke yet (the two publish-wiring tests there
will still pass at this point, since `approve()` hasn't changed yet).

### Task 1.3 — failing tests in `test_approval_endpoints.py` for "approve no longer publishes"

Add new test cases to the existing file (don't touch the two
soon-to-be-removed tests yet — that's 1.5):

```python
def test_approve_response_has_no_publish_outcome(client, pending_platform_version_id):
    response = client.post(f"/platform-versions/{pending_platform_version_id}/approve")

    assert response.status_code == 200
    assert "publish_outcome" not in response.json()
    assert response.json() == {"id": pending_platform_version_id, "status": "approved"}


def test_approve_does_not_invoke_publishing_use_case(
    client, pending_platform_version_id, fake_publishing_use_case
):
    client.post(f"/platform-versions/{pending_platform_version_id}/approve")

    assert fake_publishing_use_case.calls == []


def test_approve_leaves_status_as_approved_not_published_or_failed(
    client, test_engine, pending_platform_version_id
):
    client.post(f"/platform-versions/{pending_platform_version_id}/approve")

    with Session(test_engine) as session:
        status = session.get(PlatformVersion, pending_platform_version_id).status
        assert status == ApprovalStatus.APPROVED
```

These will **fail** at this point because `approve()` still calls
`publishing_use_case.publish(...)` and still nests `publish_outcome` in
the response (though note: the third test would actually still pass even
before 1.4, since `FakePublishingUseCase` never changes `PlatformVersion.status`
in the DB — only the real `PublishingUseCase._publish_now` does that. Flag
this in code review: it's a legitimate but weaker assertion given the fake;
it's included for documentation/regression value once 1.4 lands, not
because it's guaranteed to fail pre-1.4. The first two tests are the ones
that must fail pre-1.4 and pass post-1.4.)

Run: `pytest tests/unit/test_approval_endpoints.py -v` — confirm the first
two new tests fail, third passes trivially either way, and all pre-existing
tests (including the two about-to-be-removed ones) still pass.

### Task 1.4 — remove the publish call from `approve()`

In `src/editorial/presentation/routers/approval.py`:

```python
@router.post("/{platform_version_id}/approve")
def approve(platform_version_id: str, session: Session = Depends(get_session)) -> dict:
    _ensure_exists(session, platform_version_id)
    try:
        approve_platform_version(session, platform_version_id)
    except AlreadyDecidedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"id": platform_version_id, "status": "approved"}
```

Remove the now-unused `publishing_use_case: PublishingUseCase = Depends(get_publishing_use_case)`
parameter from `approve()`'s signature — but **keep** the
`PublishingUseCase`/`get_publishing_use_case` imports at the top of the
file, since `publish()` (added in 1.2) still needs both.

Run: `pytest tests/unit/test_approval_endpoints.py -v` — the three new
1.3 tests should now pass. The two old tests
(`test_approve_triggers_publishing_and_includes_the_outcome`,
`test_reject_never_triggers_publishing`) will now **fail** — expected,
since they assert the old contract. That's fine; 1.5 removes them next.

### Task 1.5 — clean up `test_approval_endpoints.py`

1. Delete `test_approve_triggers_publishing_and_includes_the_outcome` in
   full — its assertions (calls recorded, outcome shape) are now covered
   by `test_publish_endpoint.py`'s
   `test_publish_invokes_use_case_and_returns_the_outcome_flat`.
2. Delete `test_reject_never_triggers_publishing`. Judgment call per the
   task instructions: reject never touched publishing before *or* after
   this change (`reject()` never had a `publishing_use_case` param), so
   this assertion was arguably redundant from day one — nothing in this
   change makes it newly meaningful, and there's no equivalent "does
   /publish get called by /reject" scenario worth adding to the new file
   either (reject and publish are unrelated code paths — there's nothing
   to gate). **Decision: drop it, do not port it anywhere.**
3. Check remaining usages of `FakePublishingUseCase` and
   `fake_publishing_use_case` in the file: `test_approve_does_not_invoke_publishing_use_case`
   (added in 1.3) still needs both the fixture and the class — so **do not
   remove them**. Keep the `FakePublishingUseCase` class, the
   `fake_publishing_use_case` fixture, the `client` fixture's
   `app.dependency_overrides[get_publishing_use_case] = ...` line, and the
   `PublishOutcome`/`get_publishing_use_case` imports — all still exercised.
4. Re-read the file top-to-bottom once done to confirm no import is now
   orphaned (there shouldn't be any after step 3's check — the only two
   tests removed didn't introduce any import that isn't also used
   elsewhere in the file).

Run: `pytest tests/unit/test_approval_endpoints.py -v` — expect all
remaining tests green, with the two old tests gone entirely (not
present, not skipped).

### `tasks.md` updates

After each of 1.1 through 1.5 is verified green (or, for 1.1/1.3, verified
*correctly red* before its paired implementation step), edit
`openspec/changes/enhance-admin-panel-ui/tasks.md` to flip that item's
checkbox from `- [ ] 1.N ...` to `- [x] 1.N ...`. Check off one box per
completed step, not all five at once at the end — this preserves an
accurate in-progress record if the work is interrupted partway through.

### Final full-suite verification

Run `pytest tests/unit/ -q` (the entire backend unit suite, not just the
touched files) and confirm the full pass count is baseline count
(check current total via `pytest tests/unit/ -q | tail -5` before
starting) plus the net new tests added here: +3 in
`test_publish_endpoint.py`, +3 in `test_approval_endpoints.py`, −2 removed
from `test_approval_endpoints.py` → net +4 tests, 0 failures, 0 unexpected
skips. Do not stop at the two touched files passing — a change to a
shared router file (`approval.py`) is exactly the kind of change that can
silently break an unrelated test elsewhere (e.g. any Playwright/E2E spec
that inspects the `/approve` response shape — out of scope for this
backend-only plan, but worth a mental note that section 8 of `tasks.md`
depends on this section landing first).

## Notes / gotchas for whoever implements this

- **Do not confuse the two different 404s.** `_ensure_exists` produces
  `HTTPException(404, "PlatformVersion not found")` when the ID genuinely
  doesn't exist in the DB. FastAPI's own router will *also* return a 404
  (with a different, framework-generated body) for `/publish` requests
  made before task 1.2 lands, simply because no route is registered yet.
  Both are HTTP 404 but mean different things — 1.1's "unknown id" test
  should be understood as testing the *app-level* 404 that only becomes
  meaningful once the route exists (see the task 1.1 test #2 note above).
- **`ApprovalRequiredError` vs `AlreadyDecidedError`** are separate
  exception classes for a reason: `AlreadyDecidedError` guards
  approve/reject (must be `PENDING_REVIEW`), `ApprovalRequiredError`
  guards publish (must be `APPROVED`). Do not conflate them or try to
  reuse one for the other's check — this plan maps both to 409 because
  they're the *same kind* of error (state-conflict), not because they're
  the same error.
- **`PublishingUseCase.publish` signature is `(session, platform_version_id)`
  — it does its own `session.get` internally via `run_if_approved`.** The
  route handler does not need to fetch the `PlatformVersion` itself beyond
  the existing `_ensure_exists` existence check.
- **The `fake_publishing_use_case` fixture's `FakePublishingUseCase.publish`
  never raises `ApprovalRequiredError`** — it always returns the configured
  outcome regardless of status. This is why task 1.1's 409 test (test #3)
  must use the *real* `PublishingUseCase` (or a purpose-built fake that can
  raise), not the shared `fake_publishing_use_case` fixture — using the fake
  there would make the test pass for the wrong reason (or not exercise the
  gate at all).
- **Do not modify `PublishOutcome`, `PublishingUseCase`, or
  `approval_gate.py`** as part of this section — every field/behavior
  needed already exists; this is purely a routing change per design.md
  Decision 1 ("moved, not rewritten").
- **CLAUDE.md compliance**: work in the exact task order above (1.1 → run
  red → 1.2 → run green → 1.3 → run red → 1.4 → run green → 1.5 → run
  green → full suite), one task at a time, confirming test status at each
  transition before moving on — do not batch multiple tasks' code changes
  together even though they touch the same two files.
