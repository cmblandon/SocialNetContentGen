# Backend Implementation Plan — `research-query-scoping` (tasks 2.1-2.3, 3.1-3.4)

Scope: only `ResearchAgentUseCase.discover()` ordering (section 2) and threading
`query` through `run_research_cycle` + `POST /research/run` (section 3). Section 1
(`ports.py`, `jina_scraper.py`, `firecrawl_scraper.py`) is already implemented and
green — confirmed by reading the current files; do not touch them. Section 5
(frontend) is a separate plan; do not touch anything under `frontend/`.

This plan follows CLAUDE.md's TDD requirement: for each task pair (2.1→2.2,
3.1→3.2, 3.3→3.4) write the failing tests first, run them to confirm they fail
for the *expected* reason (missing feature, not a typo), then implement the
minimal change to turn them green, then move to the next pair.

Baseline: `pytest tests/unit/` currently passes **216 tests, 0 failed, 0
skipped** (verified before writing this plan). Keep this exact command as your
regression gate after every step.

---

## Step 1 (task 2.1) — Failing tests: `ResearchAgentUseCase.discover(source_urls, query=None)`

File: `tests/unit/test_research_agent_use_case.py`

### 1a. Update `FakeScraper` (regression-safe signature + call-order + query tracking)

Replace the current `FakeScraper` class:

```python
class FakeScraper:
    def __init__(self, documents_by_url: dict):
        self._documents_by_url = documents_by_url
        self.fetched_urls: list[str] = []

    def fetch(self, source_url: str):
        self.fetched_urls.append(source_url)
        return self._documents_by_url.get(source_url)
```

with:

```python
from typing import Optional


class FakeScraper:
    def __init__(
        self,
        documents_by_url: dict,
        call_log: Optional[list[str]] = None,
        name: str = "scraper",
    ):
        self._documents_by_url = documents_by_url
        self.fetched_urls: list[str] = []
        self.fetched_queries: list[Optional[str]] = []
        self._call_log = call_log
        self._name = name

    def fetch(self, source_url: str, query: Optional[str] = None):
        self.fetched_urls.append(source_url)
        self.fetched_queries.append(query)
        if self._call_log is not None:
            self._call_log.append(self._name)
        return self._documents_by_url.get(source_url)
```

Notes:
- `call_log` and `name` are optional with defaults, so every existing
  `FakeScraper({...})` construction call in the 6 pre-existing tests keeps
  working **completely unmodified** — this satisfies task 2.1(a)'s "regression
  guard: all 6 existing tests must still pass ... only the `FakeScraper.fetch`
  signature needs touching, not the test bodies/assertions."
  Do not modify any of the 6 existing test function bodies.
- `fetched_queries` is a simple parallel list to `fetched_urls` (appended in the
  same call), matching this file's existing plain-list style — no mocking
  library.
- `call_log` is a single list shared by two `FakeScraper` instances (primary and
  fallback) in the new order-sensitive tests below, so you can assert exact
  call order across both fakes without needing a mocking framework's
  `call_args_list`.

Add `from typing import Optional` to this test file's imports (it currently has
none — check the top of the file before adding, since the existing tests don't
use `Optional` anywhere else).

### 1b. New test — query given, both scrapers configured, fallback satisfies it (task 2.1(b), first half)

```python
def test_with_a_query_and_both_scrapers_configured_the_fallback_is_tried_first_and_wins(tmp_path):
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    url = "https://www.aaro.mil/reports/2024.pdf"
    call_log: list[str] = []
    primary = FakeScraper({url: _document()}, call_log=call_log, name="primary")
    fallback = FakeScraper({url: _document(extraction_confidence="alta")}, call_log=call_log, name="fallback")
    use_case = ResearchAgentUseCase(primary_scraper=primary, fallback_scraper=fallback, memory_store=memory_store)

    result = use_case.discover([url], query="missile silo incidents")

    assert call_log == ["fallback"]  # fallback alone satisfied it; primary never tried
    assert fallback.fetched_urls == [url]
    assert fallback.fetched_queries == ["missile silo incidents"]
    assert primary.fetched_urls == []
    assert len(result.documents) == 1
    assert result.documents[0].extraction_confidence == "alta"
```

### 1c. New test — query given, fallback returns `None`, primary is tried next with the query (task 2.1(b), second half)

```python
def test_with_a_query_the_primary_is_tried_only_after_the_fallback_returns_none(tmp_path):
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    url = "https://www.aaro.mil/reports/2024.pdf"
    call_log: list[str] = []
    fallback = FakeScraper({}, call_log=call_log, name="fallback")  # returns None for every url
    primary = FakeScraper({url: _document()}, call_log=call_log, name="primary")
    use_case = ResearchAgentUseCase(primary_scraper=primary, fallback_scraper=fallback, memory_store=memory_store)

    result = use_case.discover([url], query="missile silo incidents")

    assert call_log == ["fallback", "primary"]
    assert fallback.fetched_queries == ["missile silo incidents"]
    assert primary.fetched_urls == [url]
    assert primary.fetched_queries == ["missile silo incidents"]
    assert len(result.documents) == 1
```

### 1d. New test — query given, no fallback configured (task 2.1(c))

```python
def test_with_a_query_but_no_fallback_scraper_the_primary_is_used_and_receives_the_query(tmp_path):
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    url = "https://www.aaro.mil/reports/2024.pdf"
    primary = FakeScraper({url: _document()})
    use_case = ResearchAgentUseCase(primary_scraper=primary, fallback_scraper=None, memory_store=memory_store)

    result = use_case.discover([url], query="missile silo incidents")

    assert primary.fetched_urls == [url]
    assert primary.fetched_queries == ["missile silo incidents"]
    assert len(result.documents) == 1
```

### 1e. New test — no query given, order is exactly today's, and `None` is what scrapers receive (task 2.1(d))

```python
def test_with_no_query_the_default_primary_then_fallback_order_is_unchanged(tmp_path):
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    url = "https://www.cia.gov/readingroom/some-case"
    call_log: list[str] = []
    primary = FakeScraper({}, call_log=call_log, name="primary")  # returns None -> triggers fallback
    fallback = FakeScraper({url: _document()}, call_log=call_log, name="fallback")
    use_case = ResearchAgentUseCase(primary_scraper=primary, fallback_scraper=fallback, memory_store=memory_store)

    result = use_case.discover([url])  # query omitted entirely

    assert call_log == ["primary", "fallback"]  # unchanged from today
    assert primary.fetched_queries == [None]
    assert fallback.fetched_queries == [None]
    assert len(result.documents) == 1
```

This covers explicit `query=None` behavior implicitly too (`discover([url],
query=None)` is byte-for-byte the same call as `discover([url])` given the
parameter's default) — no separate test needed for that variant, don't add one
(avoid redundant tests per CLAUDE.md's incremental-changes principle).

**Run `pytest tests/unit/test_research_agent_use_case.py -v` now** — expect the
6 pre-existing tests to still pass (only the fixture class changed) and the 4
new tests (1b-1e) to fail with a `TypeError` (`discover() got an unexpected
keyword argument 'query'`) — that confirms they're failing for the right
reason before you implement anything.

---

## Step 2 (task 2.2) — Implement query-aware ordering in `discover()`

File: `src/editorial/application/research_agent_use_case.py`

Replace the `discover` method:

```python
    def discover(self, source_urls: list[str]) -> ResearchResult:
        result = ResearchResult()
        already_covered = self._memory_store.read_casos_cubiertos()

        for source_url in source_urls:
            if not _is_allowed_source(source_url):
                result.discarded.append(
                    ResearchDiscard(source_url, "not an official/verifiable source")
                )
                continue

            if source_url in already_covered:
                continue

            document = self._primary_scraper.fetch(source_url)
            if document is None and self._fallback_scraper is not None:
                document = self._fallback_scraper.fetch(source_url)

            if document is None:
                result.discarded.append(
                    ResearchDiscard(source_url, "inaccessible or unverifiable")
                )
                continue

            result.documents.append(document)

        return result
```

with:

```python
    def discover(self, source_urls: list[str], query: Optional[str] = None) -> ResearchResult:
        result = ResearchResult()
        already_covered = self._memory_store.read_casos_cubiertos()

        # research-query-scoping (design.md Decision 2): when a query is given
        # and a fallback scraper is configured, try the fallback first — in
        # this codebase's only wiring the fallback slot holds the
        # query-capable adapter (Firecrawl). With no query, or no fallback
        # configured, the order is unchanged from before this change
        # (primary, then fallback).
        if query and self._fallback_scraper is not None:
            first_scraper, second_scraper = self._fallback_scraper, self._primary_scraper
        else:
            first_scraper, second_scraper = self._primary_scraper, self._fallback_scraper

        for source_url in source_urls:
            if not _is_allowed_source(source_url):
                result.discarded.append(
                    ResearchDiscard(source_url, "not an official/verifiable source")
                )
                continue

            if source_url in already_covered:
                continue

            document = first_scraper.fetch(source_url, query=query)
            if document is None and second_scraper is not None:
                document = second_scraper.fetch(source_url, query=query)

            if document is None:
                result.discarded.append(
                    ResearchDiscard(source_url, "inaccessible or unverifiable")
                )
                continue

            result.documents.append(document)

        return result
```

Notes / important gotchas:
- `Optional` is already imported at the top of this file (`from typing import
  Optional`) — no new import needed here.
- The order decision is computed **once per `discover()` call**, outside the
  per-URL loop — a single run either is or isn't query-scoped; there's no
  scenario where the order should flip mid-loop across different
  `source_urls` in the same call.
- `query and self._fallback_scraper is not None` — using truthy `query` (not
  `query is not None`) means an empty string `""` also falls through to
  today's default order. This matches the frontend design (Decision 5: empty
  input is normalized away before being sent), so `""` should never actually
  reach this layer in practice, but treating it the same as `None` here is
  the more defensive, consistent choice — do not use `is not None` here.
- Both `first_scraper.fetch(...)` and `second_scraper.fetch(...)` now pass
  `query=query` explicitly as a keyword — this is why `FakeScraper.fetch` in
  the test file needed the `query: Optional[str] = None` parameter added
  (Step 1a); without it, all 6 pre-existing tests would fail with
  `TypeError: fetch() got an unexpected keyword argument 'query'`.
- Do not add any `supports_query`/capability-flag attribute to `ISourceScraper`
  or the adapters — design.md's Decision 2 explicitly rejected that as
  over-engineering for two adapters; the *caller* (`get_research_agent()` in
  Step 3 below) is what encodes the assumption, not `discover()` itself.

**Run `pytest tests/unit/test_research_agent_use_case.py -v`** — all 10 tests
(6 original + 4 new) should now pass.

---

## Step 3 (task 2.3) — Document the primary/fallback role assumption

### 3a. Module docstring — `src/editorial/application/research_agent_use_case.py`

Append a paragraph to the existing module docstring (do not remove the
existing text):

```python
"""
ResearchAgentUseCase — per specs/research-agent/spec.md.

Processes a list of candidate source URLs (already identified by the
operator, or a future listing step — autonomous crawling of a source's
listing pages is out of scope here, see the test module's docstring):
enforces the official-source allowlist, dedups against
/casos_cubiertos.md before ever fetching, and falls back from the primary
scraper to the fallback scraper on failure. Never interprets or rewrites
what a scraper extracted.

research-query-scoping (design.md Decision 2): discover() accepts an
optional `query`. When one is given and a fallback_scraper is configured,
discover() tries the fallback scraper BEFORE the primary for that call,
because this codebase's only wiring (see get_research_agent() in
presentation/routers/research.py) assumes fallback_scraper is the
query-capable adapter (FirecrawlScraperAdapter) and primary_scraper is not
(JinaScraperAdapter, which accepts but ignores query). This class never
inspects which concrete adapter it was given — the inversion is a plain
boolean decision ("was a query given, and is there a fallback"), not a
capability check. If ResearchAgentUseCase is ever wired with a different
pair of scrapers (e.g. primary/fallback swapped, or a third adapter with
different query support), this ordering heuristic must be revisited — see
design.md's Risks section.
"""
```

### 3b. Construction-site comment — `src/editorial/presentation/routers/research.py`

Add a comment immediately above the `return ResearchAgentUseCase(...)` line
inside `get_research_agent()`:

```python
def get_research_agent(
    memory_store: ProjectMemoryStore = Depends(get_memory_store),
) -> ResearchAgentUseCase:
    primary_scraper = JinaScraperAdapter(api_key=settings.jina_api_key)
    fallback_scraper = (
        FirecrawlScraperAdapter(api_key=settings.firecrawl_api_key)
        if settings.firecrawl_api_key
        else None
    )
    # research-query-scoping: ResearchAgentUseCase.discover() inverts its
    # scraper try-order (fallback first) whenever a query is given, on the
    # assumption that fallback_scraper here is the query-capable adapter
    # (FirecrawlScraperAdapter) and primary_scraper is not (JinaScraperAdapter,
    # which ignores query). If this wiring is ever changed to swap which
    # adapter fills which slot, or to use different adapters entirely, that
    # assumption must be re-verified — see ResearchAgentUseCase's module
    # docstring and design.md Decision 2 / Risks.
    return ResearchAgentUseCase(primary_scraper, fallback_scraper, memory_store)
```

No test asserts on docstring/comment text — this step doesn't add or change
any test, it's pure documentation. Skip straight to Step 4 after this.

---

## Step 4 (task 3.1) — Failing tests: `run_research_cycle(..., query=None)`

File: `tests/unit/test_research_cycle.py`

### 4a. Update `FakeResearchAgent`

Replace:

```python
class FakeResearchAgent:
    def __init__(self, documents: list[ScrapedDocument]):
        self._documents = documents

    def discover(self, source_urls):
        from src.editorial.application.research_agent_use_case import ResearchResult

        return ResearchResult(documents=self._documents, discarded=[])
```

with:

```python
class FakeResearchAgent:
    def __init__(self, documents: list[ScrapedDocument]):
        self._documents = documents
        self.received_queries: list[Optional[str]] = []

    def discover(self, source_urls, query=None):
        from src.editorial.application.research_agent_use_case import ResearchResult

        self.received_queries.append(query)
        return ResearchResult(documents=self._documents, discarded=[])
```

Add `from typing import Optional` to this file's imports (check the current
import block — it doesn't import `Optional` today).

This signature fix alone is what keeps the 3 pre-existing tests
(`test_advanced_documents_are_persisted_and_written_into_stories`,
`test_documents_that_curation_discards_never_reach_story_writing`,
`test_documents_curation_has_already_evaluated_are_skipped`) passing once
`run_research_cycle` starts calling `research_agent.discover(source_urls,
query=query)` in Step 5 — without it they'd all fail with a `TypeError`. Do
not modify these 3 tests' bodies.

### 4b. New test — query is forwarded unchanged

```python
def test_query_is_forwarded_to_the_research_agent_unchanged(session, memory_store):
    document = _scraped_document()
    research_agent = FakeResearchAgent([document])
    case_curation = FakeCaseCuration({document.title: _curation_result(document)})
    writer = FakeStoryWritingUseCase(_story())
    adapter = FakePlatformAdaptationUseCase()

    run_research_cycle(
        session=session,
        source_urls=["https://www.aaro.mil/reports/2024.pdf"],
        research_agent=research_agent,
        case_curation=case_curation,
        story_writing_use_case=writer,
        platform_adaptation_use_case=adapter,
        memory_store=memory_store,
        query="missile silo incidents",
    )

    assert research_agent.received_queries == ["missile silo incidents"]
```

### 4c. New test — omitting query preserves today's exact behavior

```python
def test_omitting_query_forwards_none_to_the_research_agent(session, memory_store):
    document = _scraped_document()
    research_agent = FakeResearchAgent([document])
    case_curation = FakeCaseCuration({document.title: _curation_result(document)})
    writer = FakeStoryWritingUseCase(_story())
    adapter = FakePlatformAdaptationUseCase()

    run_research_cycle(
        session=session,
        source_urls=["https://www.aaro.mil/reports/2024.pdf"],
        research_agent=research_agent,
        case_curation=case_curation,
        story_writing_use_case=writer,
        platform_adaptation_use_case=adapter,
        memory_store=memory_store,
    )

    assert research_agent.received_queries == [None]
```

**Run `pytest tests/unit/test_research_cycle.py -v` now** — expect the 3
pre-existing tests to still pass and the 2 new tests to fail with `TypeError:
run_research_cycle() got an unexpected keyword argument 'query'`.

---

## Step 5 (task 3.2) — Implement `query` on `run_research_cycle`

File: `src/editorial/application/orchestrator.py`

Add `Optional` to the typing import at the top of the file. Current import
block:

```python
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session
```

becomes:

```python
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session
```

Then update `run_research_cycle`'s signature and its call to `discover`:

```python
def run_research_cycle(
    session: Session,
    source_urls: list[str],
    research_agent: ResearchAgentUseCase,
    case_curation: CaseCurationUseCase,
    story_writing_use_case: StoryWritingUseCase,
    platform_adaptation_use_case: PlatformAdaptationUseCase,
    memory_store: ProjectMemoryStore,
    query: Optional[str] = None,
) -> CycleSummary:
    """
    Real input path (Phase 4), replacing the Phase 2 manual-curation CLI
    fixture: discover -> curate -> (only advanced documents) write/adapt/
    persist via run_cycle. A document that curation discards or has
    already evaluated never reaches story-writing.

    research-query-scoping: `query` is forwarded unchanged to
    research_agent.discover() — this function has no opinion on what a
    query does or how scraper order is decided, that's entirely
    ResearchAgentUseCase's concern (see its module docstring).
    """
    research_result = research_agent.discover(source_urls, query=query)

    documents_with_angles: list[tuple[Document, str]] = []
    ...  # unchanged below this point
```

Everything else in the function body is unchanged. Keep `query` as the last
parameter (after `memory_store`) so every existing positional-or-keyword call
site in `test_research_cycle.py` and `research.py` (which already calls with
all-keyword arguments) keeps working without modification.

**Run `pytest tests/unit/test_research_cycle.py -v`** — all 5 tests (3
original + 2 new) should now pass.

---

## Step 6 (task 3.3) — Failing tests: `POST /research/run` with an optional `query` field

File: `tests/unit/test_research_endpoint.py`

### 6a. Update `FakeResearchAgent` and the `client` fixture

Replace:

```python
class FakeResearchAgent:
    def __init__(self, documents):
        self._documents = documents

    def discover(self, source_urls):
        return ResearchResult(documents=self._documents, discarded=[])
```

with:

```python
class FakeResearchAgent:
    def __init__(self, documents):
        self._documents = documents
        self.received_queries: list = []

    def discover(self, source_urls, query=None):
        self.received_queries.append(query)
        return ResearchResult(documents=self._documents, discarded=[])
```

The `client` fixture currently does:

```python
    app.dependency_overrides[get_research_agent] = lambda: FakeResearchAgent([document])
```

This constructs a **new** `FakeResearchAgent` on every dependency resolution
(FastAPI calls the override callable per request), so there's no way to
inspect `received_queries` after the request unless the same instance is
reused and exposed. Change it to:

```python
    research_agent = FakeResearchAgent([document])

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_memory_store] = lambda: ProjectMemoryStore(memory_dir=tmp_path)
    app.dependency_overrides[get_research_agent] = lambda: research_agent
    app.dependency_overrides[get_case_curation] = lambda: FakeCaseCuration()
    app.dependency_overrides[get_story_writing_use_case] = lambda: FakeStoryWritingUseCase()
    app.dependency_overrides[get_platform_adaptation_use_case] = lambda: FakePlatformAdaptationUseCase()

    test_client = TestClient(app)
    test_client.research_agent = research_agent
    yield test_client
    app.dependency_overrides.clear()
```

(replacing the current `yield TestClient(app)` line). Attaching
`research_agent` as a plain attribute on the `TestClient` instance lets new
tests read `client.research_agent.received_queries` after a request, while
the 2 pre-existing tests — which only ever call `client.post(...)` and
inspect the HTTP response — are completely unaffected by this fixture
change; **do not modify their bodies**.

### 6b. New test — query flows through to the research agent

```python
def test_run_research_forwards_query_to_the_research_agent(client):
    response = client.post(
        "/research/run",
        json={
            "source_urls": ["https://www.aaro.mil/reports/2024.pdf"],
            "query": "missile silo incidents",
        },
    )

    assert response.status_code == 200
    assert client.research_agent.received_queries == ["missile silo incidents"]
```

### 6c. New test — omitting query preserves today's exact behavior

```python
def test_omitting_query_from_the_request_body_forwards_none(client):
    response = client.post(
        "/research/run",
        json={"source_urls": ["https://www.aaro.mil/reports/2024.pdf"]},
    )

    assert response.status_code == 200
    assert client.research_agent.received_queries == [None]
```

**Run `pytest tests/unit/test_research_endpoint.py -v` now** — expect the 2
pre-existing tests to still pass (fixture change is backward compatible) and
the 2 new tests to fail: 6b will get a `422` (Pydantic rejects the unknown...
actually FastAPI/Pydantic v2 by default *ignores* extra fields unless
`model_config = {"extra": "forbid"}` is set — check `ResearchRunRequest`'s
config before assuming; if extra fields are silently ignored, this test will
instead fail on the `assert client.research_agent.received_queries ==
["missile silo incidents"]` line because `None` was actually forwarded, not
on the HTTP status. Either way it fails for the right reason: the `query`
field isn't wired yet).

---

## Step 7 (task 3.4) — Implement `query` on `ResearchRunRequest` and the handler

File: `src/editorial/presentation/routers/research.py`

Add `Optional` to the typing import (this file currently has no `typing`
import — check before adding):

```python
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
```

Update `ResearchRunRequest`:

```python
class ResearchRunRequest(BaseModel):
    source_urls: list[str] = Field(min_length=1)
    query: Optional[str] = None
```

Update the `run_research` handler's call to `run_research_cycle`:

```python
@router.post("/run", response_model=ResearchRunResponse)
def run_research(
    request: ResearchRunRequest,
    session: Session = Depends(get_session),
    memory_store: ProjectMemoryStore = Depends(get_memory_store),
    research_agent: ResearchAgentUseCase = Depends(get_research_agent),
    case_curation: CaseCurationUseCase = Depends(get_case_curation),
    story_writing_use_case: StoryWritingUseCase = Depends(get_story_writing_use_case),
    platform_adaptation_use_case: PlatformAdaptationUseCase = Depends(
        get_platform_adaptation_use_case
    ),
) -> ResearchRunResponse:
    summary = run_research_cycle(
        session=session,
        source_urls=request.source_urls,
        research_agent=research_agent,
        case_curation=case_curation,
        story_writing_use_case=story_writing_use_case,
        platform_adaptation_use_case=platform_adaptation_use_case,
        memory_store=memory_store,
        query=request.query,
    )
    return ResearchRunResponse(
        documents_reviewed=summary.documents_reviewed,
        stories_created=summary.stories_created,
        chapters_generated=summary.chapters_generated,
        pending_approval_platform_version_ids=summary.pending_approval_platform_version_ids,
        discarded_document_ids=summary.discarded_document_ids,
    )
```

`ResearchRunResponse` is unchanged — this change only affects the request
shape, per proposal.md's Non-Goals (no change to `ScrapedDocument` or
response shape).

**Run `pytest tests/unit/test_research_endpoint.py -v`** — all 4 tests (2
original + 2 new) should now pass.

---

## Final verification

Run the full backend suite:

```bash
pytest tests/unit/ -q
```

Expected result if you followed this plan exactly (4 new tests in
`test_research_agent_use_case.py`, 2 new in `test_research_cycle.py`, 2 new in
`test_research_endpoint.py`):

```
216 (baseline) + 8 (new) = 224 passed
```

If your actual new-test count differs slightly (e.g. you split a test
differently), the important invariants to verify are:
- Every one of the 216 originally-passing tests still passes, **unmodified in
  intent** (only fixture/fake classes touched, never assertions or scenario
  setup in the 6+3+2 = 11 pre-existing test bodies across these three files).
- Zero skipped/xfail tests introduced.
- No test outside `test_research_agent_use_case.py`, `test_research_cycle.py`,
  and `test_research_endpoint.py` changes at all in this scope (sections 2-3
  don't touch scraper tests, curation tests, publishing tests, etc.).

Also sanity-check with `ruff`/`mypy` if this project runs them in CI/pre-commit
(check `pyproject.toml` / `.pre-commit-config.yaml` for configured hooks) —
this plan assumes full type hints throughout (`Optional[str] = None`
everywhere a query parameter is added), consistent with CLAUDE.md's Type
Safety principle.

---

## Summary of files touched in this scope

| File | Change |
|---|---|
| `src/editorial/application/research_agent_use_case.py` | `discover(source_urls, query=None)` query-aware try-order; module docstring addition |
| `src/editorial/presentation/routers/research.py` | `ResearchRunRequest.query: Optional[str] = None`; `run_research` forwards `query=request.query`; comment on `get_research_agent()`'s `ResearchAgentUseCase(...)` construction |
| `src/editorial/application/orchestrator.py` | `run_research_cycle(..., query: Optional[str] = None)` forwards to `research_agent.discover(source_urls, query=query)`; add `Optional` import |
| `tests/unit/test_research_agent_use_case.py` | `FakeScraper` gains `query`/`call_log`/`name`; 4 new tests |
| `tests/unit/test_research_cycle.py` | `FakeResearchAgent` gains `query`/`received_queries`; 2 new tests; add `Optional` import |
| `tests/unit/test_research_endpoint.py` | `FakeResearchAgent` gains `query`/`received_queries`; `client` fixture exposes the shared `research_agent` instance; 2 new tests |

Not touched in this scope: `src/editorial/core/ports.py`,
`src/editorial/infrastructure/scraping/jina_scraper.py`,
`src/editorial/infrastructure/scraping/firecrawl_scraper.py`,
`tests/unit/test_jina_scraper.py`, `tests/unit/test_firecrawl_scraper.py`, and
everything under `frontend/`.
