# Backend Implementation Plan — `research-pipeline-checkpointing` (sections 1–3 only)

Scope: tasks 1.1–3.8 of `tasks.md` (model/migration, orchestrator fix, endpoints).
Explicitly OUT of scope for this plan: section 5 (frontend), sections 4 and 6
(closing verification/report steps), and any change to `run_cycle` or
`tests/unit/test_orchestrator_cycle.py`.

Read this whole plan before starting — the ordering below **is** the TDD
ordering (write the failing test named in a step, confirm it fails for the
right reason, then apply that step's implementation).

## Important corrections vs. `proposal.md` (design.md supersedes it)

- `proposal.md`'s "Impact" section lists `tests/unit/test_research_agent_use_case.py`
  as touched. **This is stale.** `design.md` Decision 4 explicitly chose to do
  the checkpoint-dedup filtering inside `run_research_cycle` (which already
  has a `Session` in scope), not inside `ResearchAgentUseCase.discover()`
  (which has zero DB dependency today and should keep it that way). Do
  **not** modify `test_research_agent_use_case.py` or
  `research_agent_use_case.py`. All new dedup-filter tests belong in
  `test_research_cycle.py`, asserting against a fake research agent's
  recorded inputs.
- Everywhere in this plan, "the shared per-document helper" is one **private**
  function inside `orchestrator.py` (not a new public API, not exported, not
  tested directly) — it's exercised only through `run_research_cycle` and
  `run_resume_cycle`, matching this codebase's existing testing style (test
  through the public entry point).

## Baseline

Current full suite: **224 passed** (verified via `pytest tests/unit/ -q` before
starting). After sections 1–3 land, expect roughly **224 + ~18 = ~242**
(estimate; exact count depends on final test decomposition — do not treat
242 as a hard requirement, just confirm the suite grows by new tests only,
nothing existing breaks or is removed). Rough breakdown of the ~18 new tests:
`test_discovered_documents_repo.py` (new file, ~7), `test_research_cycle.py`
(+~7), `test_research_endpoint.py` (+4). `test_editorial_migrations.py` gains
no new test *functions* (its 2 existing tests just start exercising the new
table via `EXPECTED_TABLES`). `test_orchestrator_cycle.py` and
`test_research_agent_use_case.py` are untouched (6 and 10 tests respectively,
unchanged).

---

## Section 1 — `DiscoveredDocument` model + migration

### 1.1 Failing test: extend `EXPECTED_TABLES`

File: `tests/unit/test_editorial_migrations.py`

Change only this line:

```python
EXPECTED_TABLES = {"documents", "stories", "chapters", "platform_versions", "publish_records"}
```

to:

```python
EXPECTED_TABLES = {
    "documents", "stories", "chapters", "platform_versions", "publish_records",
    "discovered_documents",
}
```

Run `pytest tests/unit/test_editorial_migrations.py -q` — both tests must now
fail (`test_upgrade_head_creates_all_editorial_tables` because
`discovered_documents` isn't created by any migration yet;
`test_downgrade_base_removes_all_editorial_tables` will actually still pass
at this point since `isdisjoint` against a table that was never created is
trivially true — confirm this, don't be alarmed, it flips to meaningfully
exercised only after 1.3 adds the table). The important one to confirm RED
is `test_upgrade_head_creates_all_editorial_tables`.

### 1.2 `CurationStatus` enum + `DiscoveredDocument` model

File: `src/editorial/infrastructure/persistence/models.py`

Append at the end of the file (after `PublishRecord`) — deliberately not
interleaved into the `Document -> Story -> Chapter -> PlatformVersion ->
PublishRecord` chain's block, since this is a separate, parallel checkpoint
concept (design.md Decision 1). No new imports are needed — `enum`, `String`,
`Text`, `DateTime`, `ForeignKey`, `SAEnum`, `Mapped`, `mapped_column`,
`Optional`, `datetime` are all already imported at the top of this file.

```python
class CurationStatus(str, enum.Enum):
    """
    Lifecycle of a DiscoveredDocument checkpoint (research-pipeline-
    checkpointing design.md Decision 1). PENDING until curation is
    attempted; ADVANCED/DISCARDED are terminal outcomes of a curation call
    that actually ran; FAILED means curation itself errored (LLM/network
    error, malformed response) — distinct from DISCARDED (curation ran to
    completion and scored below threshold) because a FAILED row is
    retryable via POST /research/resume and a DISCARDED one is not.
    """

    PENDING = "pending"
    ADVANCED = "advanced"
    DISCARDED = "discarded"
    FAILED = "failed"


class DiscoveredDocument(Base):
    """
    A document research-agent successfully scraped, checkpointed
    immediately — before curation is ever attempted — so a curation-stage
    failure can never silently lose already-scraped content (design.md
    Decision 1). Deliberately a separate table from Document: Document
    continues to mean "an editorial case with a story" everywhere else in
    this codebase (its `stories` relationship, the admin panel's cases
    view, manual_curation_cli), not "anything ever scraped, including
    permanently discarded/failed ones".

    Rows are never deleted (design.md Decision 5): once ADVANCED or
    DISCARDED they stay as a permanent audit trail; FAILED rows stay
    FAILED until a resume attempt changes their status.
    """

    __tablename__ = "discovered_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    agency: Mapped[str] = mapped_column(String(200), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(100), nullable=False)
    published_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_confidence: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[CurationStatus] = mapped_column(
        SAEnum(CurationStatus), nullable=False, default=CurationStatus.PENDING
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    narrative_angle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_id: Mapped[Optional[str]] = mapped_column(ForeignKey("documents.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
```

Notes:
- No `relationship()` back to `Document` and no back-reference on `Document`
  itself — intentionally minimal (nothing in scope needs to navigate
  `document.discovered_documents` or similar). `document_id` is a plain FK
  column, read/written directly.
- `SAEnum(CurationStatus)` matches the exact existing pattern for
  `PlatformVersion.status`/`PublishRecord.status` (`SAEnum(ApprovalStatus)`).
  The migration (1.3) uses the `sa.Enum(*values, name=..., native_enum=False)`
  form instead, matching `0001_initial_editorial_schema.py`'s pattern for
  `platformname`/`approvalstatus` — this asymmetry (ORM uses `SAEnum(EnumClass)`,
  migration uses `sa.Enum(*string_values, native_enum=False)`) is pre-existing
  in this codebase, not something to "fix" here.
- Because `tests/unit/test_research_cycle.py`, `test_research_endpoint.py`,
  and `test_orchestrator_cycle.py` all build their test DB via
  `Base.metadata.create_all(engine)` directly (not via Alembic), simply
  adding this class to `models.py` is enough to make `discovered_documents`
  available in every one of those test fixtures automatically — no fixture
  changes needed there for the table to exist.

### 1.3 New Alembic revision

New file:
`src/editorial/infrastructure/persistence/migrations/versions/0002_discovered_documents.py`

```python
"""Add discovered_documents table (research-pipeline-checkpointing)

Revision ID: 0002_discovered_documents
Revises: 0001_initial_editorial_schema
Create Date: 2026-09-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from src.editorial.infrastructure.persistence.models import CurationStatus

# revision identifiers, used by Alembic.
revision: str = "0002_discovered_documents"
down_revision: Union[str, None] = "0001_initial_editorial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CURATION_STATUS_VALUES = [s.value for s in CurationStatus]


def upgrade() -> None:
    op.create_table(
        "discovered_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("agency", sa.String(length=200), nullable=False),
        sa.Column("doc_type", sa.String(length=100), nullable=False),
        sa.Column("published_date", sa.String(length=50), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("extraction_confidence", sa.String(length=50), nullable=True),
        sa.Column(
            "status",
            sa.Enum(*_CURATION_STATUS_VALUES, name="curationstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("narrative_angle", sa.Text(), nullable=True),
        sa.Column(
            "document_id", sa.String(length=36), sa.ForeignKey("documents.id"), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("discovered_documents")
```

After this, `pytest tests/unit/test_editorial_migrations.py -q` must pass
(both tests GREEN).

---

## Section 2 — checkpoint before curating, isolate curation failures

### 2.1 / 2.2 — checkpoint persistence helper module

New file: `src/editorial/infrastructure/persistence/discovered_documents_repo.py`

This codebase has **no** ABC-based repository pattern anywhere (see
`docs/backend-standards.md`'s "Ports: `typing.Protocol`, not `abc.ABC`" and
the fact that `approval_gate.py` is plain functions taking `Session` as the
first argument, not a class). Follow that exact style here — plain
module-level functions, not a class:

```python
"""
Persistence helpers for DiscoveredDocument checkpoints (research-pipeline-
checkpointing design.md Decision 1): every document research-agent
successfully scrapes is checkpointed here immediately, before curation is
ever attempted, so a downstream curation failure never loses what was
already scraped. Plain functions taking an explicit Session, matching this
codebase's existing style for persistence-adjacent orchestration helpers
(see approval_gate.py) rather than a class-based repository.
"""
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.editorial.core.ports import ScrapedDocument
from src.editorial.infrastructure.persistence.models import CurationStatus, DiscoveredDocument


def create_pending_checkpoint(session: Session, scraped_document: ScrapedDocument) -> DiscoveredDocument:
    """
    Persists scraped_document as a new PENDING checkpoint row. Always
    creates a new row — callers are expected to have already filtered out
    source URLs with an existing non-terminal checkpoint before calling
    discover() in the first place (see run_research_cycle's pre-filter,
    section 3), so a ScrapedDocument reaching here is new.
    """
    checkpoint = DiscoveredDocument(
        title=scraped_document.title,
        agency=scraped_document.agency,
        doc_type=scraped_document.doc_type,
        published_date=scraped_document.published_date,
        source_url=scraped_document.source_url,
        extracted_text=scraped_document.extracted_text,
        extraction_confidence=scraped_document.extraction_confidence,
        status=CurationStatus.PENDING,
    )
    session.add(checkpoint)
    session.commit()
    return checkpoint


def find_checkpoint_by_source_url(session: Session, source_url: Optional[str]) -> Optional[DiscoveredDocument]:
    if not source_url:
        return None
    return session.execute(
        select(DiscoveredDocument).where(DiscoveredDocument.source_url == source_url)
    ).scalars().first()


def find_checkpoints_by_status(
    session: Session, statuses: Sequence[CurationStatus]
) -> list[DiscoveredDocument]:
    return list(
        session.execute(
            select(DiscoveredDocument).where(DiscoveredDocument.status.in_(list(statuses)))
        ).scalars()
    )


def count_checkpoints_by_status(session: Session, status: CurationStatus) -> int:
    return session.execute(
        select(func.count()).select_from(DiscoveredDocument).where(DiscoveredDocument.status == status)
    ).scalar_one()


def mark_checkpoint_failed(session: Session, checkpoint: DiscoveredDocument, error_message: str) -> None:
    checkpoint.status = CurationStatus.FAILED
    checkpoint.error_message = error_message
    session.commit()


def mark_checkpoint_discarded(session: Session, checkpoint: DiscoveredDocument) -> None:
    checkpoint.status = CurationStatus.DISCARDED
    session.commit()


def mark_checkpoint_advanced(
    session: Session,
    checkpoint: DiscoveredDocument,
    document_id: str,
    narrative_angle: Optional[str],
) -> None:
    checkpoint.status = CurationStatus.ADVANCED
    checkpoint.document_id = document_id
    checkpoint.narrative_angle = narrative_angle
    session.commit()
```

`count_checkpoints_by_status` isn't strictly needed until section 3.7/3.8, but
add it now alongside its siblings so this module is written once.

**New test file**: `tests/unit/test_discovered_documents_repo.py` — plain
`test_*` functions, `sqlite:///:memory:` + `Base.metadata.create_all(engine)`
fixture identical in shape to the `session` fixture in `test_research_cycle.py`.
Suggested tests (write these first, confirm RED against a not-yet-existing
module, then implement the module above to go GREEN):

- `test_create_pending_checkpoint_persists_a_pending_row` — build a
  `ScrapedDocument`, call `create_pending_checkpoint`, assert the returned
  row (and a freshly-queried row) has `status == CurationStatus.PENDING` and
  all fields copied over correctly.
- `test_find_checkpoint_by_source_url_returns_the_matching_row`
- `test_find_checkpoint_by_source_url_returns_none_when_absent`
- `test_find_checkpoint_by_source_url_returns_none_for_a_falsy_url` (covers
  `None`/`""`)
- `test_find_checkpoints_by_status_filters_by_the_given_statuses` — seed one
  row each of PENDING/FAILED/ADVANCED/DISCARDED, call with
  `[CurationStatus.PENDING, CurationStatus.FAILED]`, assert exactly those two
  come back.
- `test_mark_checkpoint_failed_sets_status_and_error_message`
- `test_mark_checkpoint_discarded_sets_status`
- `test_mark_checkpoint_advanced_sets_status_document_id_and_narrative_angle`
- `test_count_checkpoints_by_status_counts_only_matching_rows`

### 2.3 — failing tests in `test_research_cycle.py`

All additions below are **additive** to the existing file — do not modify
any of the 5 existing test functions or the existing fake classes'
behavior for existing call sites.

**Imports to add** at the top of `tests/unit/test_research_cycle.py`:

```python
from src.editorial.infrastructure.persistence.discovered_documents_repo import (
    find_checkpoint_by_source_url,
)
from src.editorial.infrastructure.persistence.models import CurationStatus, DiscoveredDocument, Story
```

(`select` is already imported from `sqlalchemy` at the top of this file —
reuse it.)

**One backward-compatible fixture-helper tweak** (the plan's author
double-checked this is necessary — every new dedup test needs a
`ScrapedDocument` with a real `source_url`, and `_scraped_document()`
currently never sets one, leaving the dataclass default of `None`):

```python
def _scraped_document(title="AARO 2024 Annual Report", source_url=None) -> ScrapedDocument:
    return ScrapedDocument(
        title=title,
        agency="AARO",
        doc_type="report",
        extracted_text=" ".join(["word"] * 50),
        published_date="2024-03-01",
        source_url=source_url,
    )
```

This is 100% backward compatible: every existing call site (`_scraped_document()`,
`_scraped_document(title=...)`) omits `source_url`, so it still defaults to
`None`, identical to today's behavior.

**New fake** (additive — do not touch the existing `FakeCaseCuration` class):

```python
class FakeCaseCurationWithFailures:
    """
    Like FakeCaseCuration, but a mapped value that is an Exception instance
    is raised instead of returned — used to test curation-failure isolation
    (design.md Decision 2). A title with no entry still means "curate()
    returns None" (already evaluated), matching FakeCaseCuration's existing
    convention.
    """

    def __init__(self, results_or_errors_by_title: dict):
        self._results_or_errors_by_title = results_or_errors_by_title
        self.curated_titles: list[str] = []

    def curate(self, document):
        self.curated_titles.append(document.title)
        outcome = self._results_or_errors_by_title.get(document.title)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
```

Also extend `FakeResearchAgent` (additive attribute, existing behavior
unchanged):

```python
class FakeResearchAgent:
    def __init__(self, documents: list[ScrapedDocument]):
        self._documents = documents
        self.received_queries: list[Optional[str]] = []
        self.received_source_urls: list[list[str]] = []

    def discover(self, source_urls, query=None):
        from src.editorial.application.research_agent_use_case import ResearchResult

        self.received_queries.append(query)
        self.received_source_urls.append(list(source_urls))
        return ResearchResult(documents=self._documents, discarded=[])
```

**New tests** (append at the end of the file):

```python
def test_scraped_documents_are_checkpointed_as_pending_before_curation_is_attempted(session, memory_store):
    document = _scraped_document()
    research_agent = FakeResearchAgent([document])
    seen_statuses = {}

    class InspectingCaseCuration:
        def curate(self, doc):
            checkpoint = session.execute(
                select(DiscoveredDocument).where(DiscoveredDocument.title == doc.title)
            ).scalar_one()
            seen_statuses[doc.title] = checkpoint.status
            return _curation_result(doc)

    run_research_cycle(
        session=session,
        source_urls=["https://www.aaro.mil/reports/2024.pdf"],
        research_agent=research_agent,
        case_curation=InspectingCaseCuration(),
        story_writing_use_case=FakeStoryWritingUseCase(_story()),
        platform_adaptation_use_case=FakePlatformAdaptationUseCase(),
        memory_store=memory_store,
    )

    assert seen_statuses[document.title] == CurationStatus.PENDING


def test_curation_failure_marks_the_checkpoint_failed_and_continues_to_the_next_document(session, memory_store):
    doc1 = _scraped_document(title="Doc One")
    doc2 = _scraped_document(title="Doc Two")
    research_agent = FakeResearchAgent([doc1, doc2])
    case_curation = FakeCaseCurationWithFailures({
        doc1.title: RuntimeError("Anthropic credit balance too low"),
        doc2.title: _curation_result(doc2),
    })

    summary = run_research_cycle(
        session=session,
        source_urls=["https://www.aaro.mil/reports/1.pdf", "https://www.aaro.mil/reports/2.pdf"],
        research_agent=research_agent,
        case_curation=case_curation,
        story_writing_use_case=FakeStoryWritingUseCase(_story()),
        platform_adaptation_use_case=FakePlatformAdaptationUseCase(),
        memory_store=memory_store,
    )

    assert case_curation.curated_titles == [doc1.title, doc2.title]  # doc2 still attempted
    assert summary.stories_created == 1  # only doc2 advanced

    doc1_checkpoint = session.execute(
        select(DiscoveredDocument).where(DiscoveredDocument.title == doc1.title)
    ).scalar_one()
    assert doc1_checkpoint.status == CurationStatus.FAILED
    assert "credit balance too low" in doc1_checkpoint.error_message


def test_earlier_advancing_documents_still_get_their_story_when_a_later_documents_curation_fails(session, memory_store):
    """
    The critical regression case (design.md Decision 2's "second, subtler
    loss"): today's code accumulates advanced documents into one list and
    calls run_cycle exactly once at the very end, so a crash on the 2nd of
    3 documents strands the 1st document's already-`Document`-persisted,
    already-advanced case with no Story ever created for it. This test
    fails against that code (either via the unhandled exception itself, or
    — if only the try/except were added without also moving run_cycle
    inside the per-document helper — via a missing Story row) and must
    pass once run_cycle is called immediately per advancing document.
    """
    doc1 = _scraped_document(title="Doc One")
    doc2 = _scraped_document(title="Doc Two")
    doc3 = _scraped_document(title="Doc Three")
    research_agent = FakeResearchAgent([doc1, doc2, doc3])
    case_curation = FakeCaseCurationWithFailures({
        doc1.title: _curation_result(doc1),
        doc2.title: RuntimeError("Anthropic credit balance too low"),
        doc3.title: _curation_result(doc3),
    })

    summary = run_research_cycle(
        session=session,
        source_urls=[
            "https://www.aaro.mil/reports/1.pdf",
            "https://www.aaro.mil/reports/2.pdf",
            "https://www.aaro.mil/reports/3.pdf",
        ],
        research_agent=research_agent,
        case_curation=case_curation,
        story_writing_use_case=FakeStoryWritingUseCase(_story()),
        platform_adaptation_use_case=FakePlatformAdaptationUseCase(),
        memory_store=memory_store,
    )

    # NOTE: summary.stories_created == 2, not 3 — doc2 never reaches
    # run_cycle at all (it failed curation), matching the pre-existing
    # semantics of `documents_reviewed`/`stories_created` (they only ever
    # counted documents that reached run_cycle, i.e. advanced ones — this
    # is unchanged by this fix, not a new quirk it introduces).
    assert summary.stories_created == 2

    doc1_row = session.execute(select(Document).where(Document.title == doc1.title)).scalar_one()
    doc1_story = session.execute(select(Story).where(Story.document_id == doc1_row.id)).scalar_one()
    assert doc1_story is not None

    doc3_row = session.execute(select(Document).where(Document.title == doc3.title)).scalar_one()
    assert session.execute(select(Story).where(Story.document_id == doc3_row.id)).scalar_one() is not None

    doc2_checkpoint = session.execute(
        select(DiscoveredDocument).where(DiscoveredDocument.title == doc2.title)
    ).scalar_one()
    assert doc2_checkpoint.status == CurationStatus.FAILED


def test_advancing_document_checkpoint_is_marked_advanced_with_document_id_and_angle(session, memory_store):
    document = _scraped_document()
    research_agent = FakeResearchAgent([document])
    case_curation = FakeCaseCuration({document.title: _curation_result(document, narrative_angle="angle")})

    run_research_cycle(
        session=session,
        source_urls=["https://www.aaro.mil/reports/2024.pdf"],
        research_agent=research_agent,
        case_curation=case_curation,
        story_writing_use_case=FakeStoryWritingUseCase(_story()),
        platform_adaptation_use_case=FakePlatformAdaptationUseCase(),
        memory_store=memory_store,
    )

    persisted_document = session.execute(select(Document).where(Document.title == document.title)).scalar_one()
    checkpoint = session.execute(
        select(DiscoveredDocument).where(DiscoveredDocument.title == document.title)
    ).scalar_one()
    assert checkpoint.status == CurationStatus.ADVANCED
    assert checkpoint.document_id == persisted_document.id
    assert checkpoint.narrative_angle == "angle"


def test_discarded_document_checkpoint_is_marked_discarded(session, memory_store):
    document = _scraped_document()
    research_agent = FakeResearchAgent([document])
    case_curation = FakeCaseCuration({document.title: _curation_result(document, advanced=False)})

    run_research_cycle(
        session=session,
        source_urls=["https://www.aaro.mil/reports/2024.pdf"],
        research_agent=research_agent,
        case_curation=case_curation,
        story_writing_use_case=FakeStoryWritingUseCase(_story()),
        platform_adaptation_use_case=FakePlatformAdaptationUseCase(),
        memory_store=memory_store,
    )

    checkpoint = session.execute(
        select(DiscoveredDocument).where(DiscoveredDocument.title == document.title)
    ).scalar_one()
    assert checkpoint.status == CurationStatus.DISCARDED
    assert checkpoint.document_id is None
```

**One INFERRED decision — flag this to the user/reviewer before implementing,
it is not spelled out in design.md**: when `case_curation.curate(...)`
returns `None` (meaning: this title was already evaluated previously, per
`CaseCurationUseCase`'s own `casos_cubiertos.md` dedup, done *inside*
`curate()` before it ever calls the LLM), what should happen to that
document's brand-new PENDING checkpoint? Design.md's Decision 1 only lists
`PENDING`/`ADVANCED`/`DISCARDED`/`FAILED` and doesn't explicitly address this
case. This plan recommends marking it **DISCARDED** (via
`mark_checkpoint_discarded`) — treating "already evaluated elsewhere" as a
final, non-retryable outcome, consistent with Decision 5's "DISCARDED is
permanent". The alternative (leaving it PENDING) would cause it to be picked
up again by every future `POST /research/resume` call, uselessly re-calling
`curate()` forever (harmless since `curate()` returns `None` before any LLM
call in this case, but noisy and pointless). Recommended test:

```python
def test_document_already_evaluated_previously_has_its_checkpoint_marked_discarded(session, memory_store):
    document = _scraped_document()
    research_agent = FakeResearchAgent([document])
    case_curation = FakeCaseCuration({})  # curate() returns None for every title

    run_research_cycle(
        session=session,
        source_urls=["https://www.aaro.mil/reports/2024.pdf"],
        research_agent=research_agent,
        case_curation=case_curation,
        story_writing_use_case=FakeStoryWritingUseCase(_story()),
        platform_adaptation_use_case=FakePlatformAdaptationUseCase(),
        memory_store=memory_store,
    )

    checkpoint = session.execute(
        select(DiscoveredDocument).where(DiscoveredDocument.title == document.title)
    ).scalar_one()
    assert checkpoint.status == CurationStatus.DISCARDED
```

If the reviewer disagrees (e.g. prefers leaving it PENDING, or wants a 5th
status), that's a one-branch change in the helper (2.4) plus this one test —
flag it, don't silently pick the other option without checking.

Confirm all six new tests above are RED (fail with `AttributeError`/
`ImportError`/assertion failures against today's `orchestrator.py`) before
moving to 2.4. Also re-run the 5 pre-existing tests in this file to confirm
they still pass unmodified at this point (they will, since nothing in
`orchestrator.py` has changed yet) — this just confirms the new test/fixture
additions above didn't accidentally break anything already there.

### 2.4 — implement the shared per-document helper; refactor `run_research_cycle`

File: `src/editorial/application/orchestrator.py`

**New imports** to add:

```python
from src.editorial.core.ports import ScrapedDocument
from src.editorial.infrastructure.persistence.discovered_documents_repo import (
    create_pending_checkpoint,
    find_checkpoints_by_status,
    mark_checkpoint_advanced,
    mark_checkpoint_discarded,
    mark_checkpoint_failed,
)
from src.editorial.infrastructure.persistence.models import CurationStatus, DiscoveredDocument, Document
```

(`Document` is already imported today — just extend that existing import
line to also bring in `CurationStatus`/`DiscoveredDocument` from the same
module, rather than adding a second import line from `models`.)

**Add a `merge` method to `CycleSummary`** (design.md Decision 2 explicitly
suggests this):

```python
@dataclass
class CycleSummary:
    documents_reviewed: int = 0
    stories_created: int = 0
    chapters_generated: int = 0
    pending_approval_platform_version_ids: list[str] = field(default_factory=list)
    discarded_document_ids: list[str] = field(default_factory=list)

    def merge(self, other: "CycleSummary") -> "CycleSummary":
        """Accumulates another CycleSummary into this one in place — used
        when run_cycle is invoked once per advancing document (design.md
        Decision 2) instead of once per batch, so the caller-visible total
        is still a single CycleSummary."""
        self.documents_reviewed += other.documents_reviewed
        self.stories_created += other.stories_created
        self.chapters_generated += other.chapters_generated
        self.pending_approval_platform_version_ids.extend(other.pending_approval_platform_version_ids)
        self.discarded_document_ids.extend(other.discarded_document_ids)
        return self
```

`run_cycle` itself: **do not touch**, not even whitespace.

**New private helper**, placed after `run_cycle` and before
`run_research_cycle`:

```python
def _process_checkpointed_document(
    session: Session,
    scraped_document: ScrapedDocument,
    checkpoint: DiscoveredDocument,
    case_curation: CaseCurationUseCase,
    story_writing_use_case: StoryWritingUseCase,
    platform_adaptation_use_case: PlatformAdaptationUseCase,
    memory_store: ProjectMemoryStore,
) -> CycleSummary:
    """
    Curates one already-checkpointed document and, if it advances, writes/
    adapts/persists it IMMEDIATELY via a single-element run_cycle call —
    design.md Decision 2. Shared by run_research_cycle (fresh discovery)
    and run_resume_cycle (section 3, reprocessing PENDING/FAILED
    checkpoints with no scraping involved), so the two entry points can't
    drift apart.

    Any exception from case_curation.curate() (LLM error, network failure,
    a deliberately-raised CurationError for malformed output, etc.) is
    caught here and isolates this one document — it does not propagate to
    the caller, and does not stop the remaining documents in the same
    batch from being processed.
    """
    try:
        curation_result = case_curation.curate(scraped_document)
    except Exception as error:  # noqa: BLE001 - intentionally broad: ANY
        # curation-stage failure must be isolated per document, not just
        # the specific exception types CaseCurationUseCase happens to
        # raise today (see design.md's Context: an unguarded LLM client
        # call can raise anything, e.g. anthropic.BadRequestError).
        mark_checkpoint_failed(session, checkpoint, str(error))
        return CycleSummary()

    if curation_result is None or not curation_result.advanced:
        # None: already evaluated previously (casos_cubiertos.md dedup) —
        # see this plan's "INFERRED decision" note in section 2.3 for why
        # this is treated the same as an explicit discard.
        mark_checkpoint_discarded(session, checkpoint)
        return CycleSummary()

    document = Document(
        title=scraped_document.title,
        agency=scraped_document.agency,
        doc_type=scraped_document.doc_type,
        published_date=scraped_document.published_date,
        source_url=scraped_document.source_url,
        extracted_text=scraped_document.extracted_text,
        extraction_confidence=scraped_document.extraction_confidence,
    )
    session.add(document)
    session.commit()

    summary = run_cycle(
        session=session,
        documents_with_angles=[(document, curation_result.narrative_angle)],
        story_writing_use_case=story_writing_use_case,
        platform_adaptation_use_case=platform_adaptation_use_case,
        memory_store=memory_store,
    )

    mark_checkpoint_advanced(
        session, checkpoint, document_id=document.id, narrative_angle=curation_result.narrative_angle
    )

    return summary
```

**Rewrite `run_research_cycle`'s body** (signature unchanged):

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
    Real input path (Phase 4): discover -> checkpoint -> curate -> (only
    advanced documents) write/adapt/persist, via the shared per-document
    helper (design.md Decision 2/3). Every document discover() returns is
    checkpointed as PENDING before curation is ever attempted, so a
    curation-stage failure never loses it — and one document's curation
    failure doesn't stop the rest of the batch (see
    _process_checkpointed_document). Source URLs already checkpointed as
    PENDING/FAILED from a previous run are skipped before discover() is
    even called, so a retried call with the same URLs doesn't re-scrape
    them (design.md Decision 4) — this is what task 3.2 adds; until then
    this function discovers unconditionally.

    research-query-scoping: `query` is forwarded unchanged to
    research_agent.discover() — this function has no opinion on what a
    query does or how scraper order is decided, that's entirely
    ResearchAgentUseCase's concern (see its module docstring).
    """
    non_terminal_checkpoints = find_checkpoints_by_status(
        session, [CurationStatus.PENDING, CurationStatus.FAILED]
    )
    already_checkpointed_urls = {
        checkpoint.source_url for checkpoint in non_terminal_checkpoints if checkpoint.source_url
    }
    urls_to_discover = [url for url in source_urls if url not in already_checkpointed_urls]

    research_result = research_agent.discover(urls_to_discover, query=query)

    summary = CycleSummary()
    for scraped_document in research_result.documents:
        checkpoint = create_pending_checkpoint(session, scraped_document)
        summary.merge(
            _process_checkpointed_document(
                session=session,
                scraped_document=scraped_document,
                checkpoint=checkpoint,
                case_curation=case_curation,
                story_writing_use_case=story_writing_use_case,
                platform_adaptation_use_case=platform_adaptation_use_case,
                memory_store=memory_store,
            )
        )

    return summary
```

**Important**: this single rewrite already includes the section 3.2 dedup
filter (`already_checkpointed_urls` / `urls_to_discover`) because it's a
handful of lines living in the exact same function body as the checkpoint
loop — splitting it into two separate edits (2.4 without the filter, then
3.2 adding it) is possible but mechanically awkward for this specific
function. **For strict TDD discipline, still treat 3.1's test as the one
that must be written and confirmed RED before this filter logic is
considered "done"** — i.e., write 2.3's tests first, get them GREEN with a
version of `run_research_cycle` that does NOT yet filter `source_urls`
(passing `source_urls` directly to `discover()`), confirm 2.3 GREEN, then
write 3.1's failing test, then add the four `non_terminal_checkpoints`/
`already_checkpointed_urls`/`urls_to_discover` lines to make 3.1 GREEN too.
The code shown above is the *final* state after both 2.4 and 3.2.

After 2.4 (with the filter still pending until 3.2's test is written first,
per the note above): run `pytest tests/unit/test_research_cycle.py
tests/unit/test_orchestrator_cycle.py -q` — all of 2.3's new tests GREEN,
all 5 pre-existing `test_research_cycle.py` tests still GREEN, all 6
`test_orchestrator_cycle.py` tests untouched and still GREEN.

---

## Section 3 — dedup against checkpoints, resume orchestration, endpoints

### 3.1 — failing dedup-filter test

Append to `tests/unit/test_research_cycle.py`:

```python
def test_source_urls_with_a_pending_or_failed_checkpoint_are_not_re_scraped(session, memory_store):
    already_pending_url = "https://www.aaro.mil/reports/already-pending.pdf"
    already_failed_url = "https://www.aaro.mil/reports/already-failed.pdf"
    new_url = "https://www.aaro.mil/reports/new.pdf"

    session.add_all([
        DiscoveredDocument(
            title="Pending doc", agency="AARO", doc_type="report", extracted_text="text",
            source_url=already_pending_url, status=CurationStatus.PENDING,
        ),
        DiscoveredDocument(
            title="Failed doc", agency="AARO", doc_type="report", extracted_text="text",
            source_url=already_failed_url, status=CurationStatus.FAILED,
        ),
    ])
    session.commit()

    new_document = _scraped_document(title="New doc", source_url=new_url)
    research_agent = FakeResearchAgent([new_document])
    case_curation = FakeCaseCuration({new_document.title: _curation_result(new_document)})

    run_research_cycle(
        session=session,
        source_urls=[already_pending_url, already_failed_url, new_url],
        research_agent=research_agent,
        case_curation=case_curation,
        story_writing_use_case=FakeStoryWritingUseCase(_story()),
        platform_adaptation_use_case=FakePlatformAdaptationUseCase(),
        memory_store=memory_store,
    )

    assert research_agent.received_source_urls == [[new_url]]


def test_source_urls_with_an_advanced_or_discarded_checkpoint_are_still_offered_to_discover(session, memory_store):
    """
    Only PENDING/FAILED are non-terminal and excluded — ADVANCED/DISCARDED
    are final outcomes (design.md Decision 5) and intentionally NOT
    filtered here; in practice they're expected to also be excluded by
    ResearchAgentUseCase's own pre-existing casos_cubiertos.md dedup
    (unchanged, out of scope), but this function's own filter must not
    over-exclude terminal checkpoints on its own.
    """
    terminal_url = "https://www.aaro.mil/reports/terminal.pdf"
    session.add(DiscoveredDocument(
        title="Advanced doc", agency="AARO", doc_type="report", extracted_text="text",
        source_url=terminal_url, status=CurationStatus.ADVANCED,
    ))
    session.commit()

    document = _scraped_document(source_url=terminal_url)
    research_agent = FakeResearchAgent([document])
    case_curation = FakeCaseCuration({document.title: _curation_result(document)})

    run_research_cycle(
        session=session,
        source_urls=[terminal_url],
        research_agent=research_agent,
        case_curation=case_curation,
        story_writing_use_case=FakeStoryWritingUseCase(_story()),
        platform_adaptation_use_case=FakePlatformAdaptationUseCase(),
        memory_store=memory_store,
    )

    assert research_agent.received_source_urls == [[terminal_url]]
```

Confirm both RED against the pre-3.2 version of `run_research_cycle` (the
first one, without the filter, should fail because `received_source_urls`
would include all 3/1 URLs unfiltered for the first test, and pass
trivially for the second — the second test is really a safety-net for the
*next* step, confirm it stays GREEN throughout).

### 3.2 — implement the filter

Already written above as part of 2.4's final `run_research_cycle` body (the
`non_terminal_checkpoints` / `already_checkpointed_urls` / `urls_to_discover`
lines). Add exactly those lines now if you deferred them per the note in
2.4. Confirm 3.1's tests GREEN, and re-run the full
`tests/unit/test_research_cycle.py` file to confirm nothing else regressed.

### 3.3 / 3.4 — `run_resume_cycle`

File: `src/editorial/application/orchestrator.py` — add after
`run_research_cycle`:

```python
def run_resume_cycle(
    session: Session,
    case_curation: CaseCurationUseCase,
    story_writing_use_case: StoryWritingUseCase,
    platform_adaptation_use_case: PlatformAdaptationUseCase,
    memory_store: ProjectMemoryStore,
) -> CycleSummary:
    """
    Reprocesses every checkpointed document still in a retryable state
    (PENDING or FAILED) through curation -> writing -> adaptation, with NO
    scraping involved at all — this is what lets an operator recover after
    fixing whatever broke (e.g. topping up LLM credit) without re-spending
    scraper calls (design.md Decision 3). Reuses the exact same
    per-document helper run_research_cycle uses, so the two entry points
    can't drift apart. Returns a zeroed CycleSummary, not an error, when
    nothing is pending/failed.
    """
    summary = CycleSummary()
    checkpoints = find_checkpoints_by_status(session, [CurationStatus.PENDING, CurationStatus.FAILED])

    for checkpoint in checkpoints:
        scraped_document = ScrapedDocument(
            title=checkpoint.title,
            agency=checkpoint.agency,
            doc_type=checkpoint.doc_type,
            extracted_text=checkpoint.extracted_text,
            published_date=checkpoint.published_date,
            source_url=checkpoint.source_url,
            extraction_confidence=checkpoint.extraction_confidence,
        )
        summary.merge(
            _process_checkpointed_document(
                session=session,
                scraped_document=scraped_document,
                checkpoint=checkpoint,
                case_curation=case_curation,
                story_writing_use_case=story_writing_use_case,
                platform_adaptation_use_case=platform_adaptation_use_case,
                memory_store=memory_store,
            )
        )

    return summary
```

**New tests** in `tests/unit/test_research_cycle.py` (a `run_resume_cycle`
import needs adding to this file's existing
`from src.editorial.application.orchestrator import run_research_cycle` line
— extend it to `import run_research_cycle, run_resume_cycle`):

```python
def test_run_resume_cycle_reprocesses_pending_and_failed_checkpoints_with_no_scraping(session, memory_store):
    pending_checkpoint = DiscoveredDocument(
        title="Pending doc", agency="AARO", doc_type="report",
        extracted_text=" ".join(["word"] * 50), source_url="https://www.aaro.mil/reports/p.pdf",
        status=CurationStatus.PENDING,
    )
    failed_checkpoint = DiscoveredDocument(
        title="Failed doc", agency="AARO", doc_type="report",
        extracted_text=" ".join(["word"] * 50), source_url="https://www.aaro.mil/reports/f.pdf",
        status=CurationStatus.FAILED, error_message="previous failure",
    )
    session.add_all([pending_checkpoint, failed_checkpoint])
    session.commit()

    case_curation = FakeCaseCuration({
        "Pending doc": _curation_result(_scraped_document(title="Pending doc"), narrative_angle="angle1"),
        "Failed doc": _curation_result(_scraped_document(title="Failed doc"), narrative_angle="angle2"),
    })

    summary = run_resume_cycle(
        session=session,
        case_curation=case_curation,
        story_writing_use_case=FakeStoryWritingUseCase(_story()),
        platform_adaptation_use_case=FakePlatformAdaptationUseCase(),
        memory_store=memory_store,
    )

    assert summary.stories_created == 2
    assert {pending_checkpoint.status, failed_checkpoint.status} == {CurationStatus.ADVANCED}


def test_run_resume_cycle_with_nothing_pending_or_failed_returns_a_zeroed_summary(session, memory_store):
    summary = run_resume_cycle(
        session=session,
        case_curation=FakeCaseCuration({}),
        story_writing_use_case=FakeStoryWritingUseCase(_story()),
        platform_adaptation_use_case=FakePlatformAdaptationUseCase(),
        memory_store=memory_store,
    )

    assert summary == CycleSummary()
```

(`CycleSummary` needs importing into the test file for the second
assertion — add
`from src.editorial.application.orchestrator import CycleSummary,
run_research_cycle, run_resume_cycle`. Since `CycleSummary` is a `@dataclass`,
`==` compares field-by-field, so `CycleSummary() == CycleSummary()` is `True`
by default dataclass equality — no custom `__eq__` needed.)

### 3.5 / 3.6 — `POST /research/resume`

File: `src/editorial/presentation/routers/research.py`

Add imports:

```python
from src.editorial.application.orchestrator import run_research_cycle, run_resume_cycle
from src.editorial.infrastructure.persistence.discovered_documents_repo import (
    count_checkpoints_by_status,
)
from src.editorial.infrastructure.persistence.models import CurationStatus
```

Add the endpoint (placed after `run_research`, before `list_sources` — order
doesn't functionally matter, just keep related endpoints grouped):

```python
@router.post("/resume", response_model=ResearchRunResponse)
def resume_research(
    session: Session = Depends(get_session),
    memory_store: ProjectMemoryStore = Depends(get_memory_store),
    case_curation: CaseCurationUseCase = Depends(get_case_curation),
    story_writing_use_case: StoryWritingUseCase = Depends(get_story_writing_use_case),
    platform_adaptation_use_case: PlatformAdaptationUseCase = Depends(
        get_platform_adaptation_use_case
    ),
) -> ResearchRunResponse:
    summary = run_resume_cycle(
        session=session,
        case_curation=case_curation,
        story_writing_use_case=story_writing_use_case,
        platform_adaptation_use_case=platform_adaptation_use_case,
        memory_store=memory_store,
    )
    return ResearchRunResponse(
        documents_reviewed=summary.documents_reviewed,
        stories_created=summary.stories_created,
        chapters_generated=summary.chapters_generated,
        pending_approval_platform_version_ids=summary.pending_approval_platform_version_ids,
        discarded_document_ids=summary.discarded_document_ids,
    )
```

No request body model — `POST /research/resume` takes no input, per
design.md Decision 3 ("no source_urls needed"). A bare `client.post(
"/research/resume")` (no `json=` kwarg at all) is a valid call.

**Test file changes**: `tests/unit/test_research_endpoint.py`

Add one line inside the existing `client` fixture (right before `yield
test_client`), exposing the session factory so new tests can seed
`DiscoveredDocument` rows directly — mirrors the existing
`test_client.research_agent = research_agent` pattern already in this
fixture:

```python
    test_client.research_agent = research_agent
    test_client.session_factory = TestSessionLocal
    yield test_client
```

Add import: `from src.editorial.infrastructure.persistence.models import
CurationStatus, DiscoveredDocument`.

New tests:

```python
def test_resume_research_processes_pending_checkpoints_and_returns_summary(client):
    session = client.session_factory()
    session.add(DiscoveredDocument(
        title="Old Scraped Doc",
        agency="AARO",
        doc_type="report",
        extracted_text=" ".join(["word"] * 50),
        published_date="2024-01-01",
        source_url="https://www.aaro.mil/reports/old.pdf",
        status=CurationStatus.PENDING,
    ))
    session.commit()
    session.close()

    response = client.post("/research/resume")

    assert response.status_code == 200
    body = response.json()
    assert body["documents_reviewed"] == 1
    assert body["stories_created"] == 1
    assert body["chapters_generated"] == 1


def test_resume_research_with_nothing_pending_or_failed_returns_a_zeroed_summary(client):
    response = client.post("/research/resume")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "documents_reviewed": 0,
        "stories_created": 0,
        "chapters_generated": 0,
        "pending_approval_platform_version_ids": [],
        "discarded_document_ids": [],
    }
```

### 3.7 / 3.8 — `GET /research/checkpoints/summary`

File: `src/editorial/presentation/routers/research.py`

Add response model (near the other response models):

```python
class CheckpointSummaryResponse(BaseModel):
    pending: int
    failed: int
```

Add endpoint:

```python
@router.get("/checkpoints/summary", response_model=CheckpointSummaryResponse)
def get_checkpoints_summary(session: Session = Depends(get_session)) -> CheckpointSummaryResponse:
    return CheckpointSummaryResponse(
        pending=count_checkpoints_by_status(session, CurationStatus.PENDING),
        failed=count_checkpoints_by_status(session, CurationStatus.FAILED),
    )
```

New tests in `tests/unit/test_research_endpoint.py`:

```python
def test_checkpoints_summary_returns_zero_counts_when_none_exist(client):
    response = client.get("/research/checkpoints/summary")

    assert response.status_code == 200
    assert response.json() == {"pending": 0, "failed": 0}


def test_checkpoints_summary_counts_pending_and_failed_rows_only(client):
    session = client.session_factory()
    session.add_all([
        DiscoveredDocument(title="P1", agency="AARO", doc_type="report", extracted_text="t", status=CurationStatus.PENDING),
        DiscoveredDocument(title="P2", agency="AARO", doc_type="report", extracted_text="t", status=CurationStatus.PENDING),
        DiscoveredDocument(title="F1", agency="AARO", doc_type="report", extracted_text="t", status=CurationStatus.FAILED),
        DiscoveredDocument(title="A1", agency="AARO", doc_type="report", extracted_text="t", status=CurationStatus.ADVANCED),
        DiscoveredDocument(title="D1", agency="AARO", doc_type="report", extracted_text="t", status=CurationStatus.DISCARDED),
    ])
    session.commit()
    session.close()

    response = client.get("/research/checkpoints/summary")

    assert response.status_code == 200
    assert response.json() == {"pending": 2, "failed": 1}
```

---

## Full-file summary of touched/new files

**New files**
- `src/editorial/infrastructure/persistence/migrations/versions/0002_discovered_documents.py`
- `src/editorial/infrastructure/persistence/discovered_documents_repo.py`
- `tests/unit/test_discovered_documents_repo.py`

**Modified files**
- `src/editorial/infrastructure/persistence/models.py` (append `CurationStatus`, `DiscoveredDocument`)
- `src/editorial/application/orchestrator.py` (`CycleSummary.merge`, new private `_process_checkpointed_document`, rewritten `run_research_cycle` body, new `run_resume_cycle`; `run_cycle` untouched)
- `src/editorial/presentation/routers/research.py` (new imports, `POST /resume`, `GET /checkpoints/summary`, `CheckpointSummaryResponse`)
- `tests/unit/test_editorial_migrations.py` (one-line `EXPECTED_TABLES` change)
- `tests/unit/test_research_cycle.py` (new imports, one backward-compatible `_scraped_document` signature tweak, new `FakeCaseCurationWithFailures`, `FakeResearchAgent.received_source_urls` addition, ~9 new test functions)
- `tests/unit/test_research_endpoint.py` (new imports, `test_client.session_factory` fixture addition, ~4 new test functions)

**Explicitly NOT touched**
- `src/editorial/application/orchestrator.py`'s `run_cycle` function
- `tests/unit/test_orchestrator_cycle.py`
- `src/editorial/application/research_agent_use_case.py`
- `tests/unit/test_research_agent_use_case.py`
- `frontend/` (any file)
- `openspec/changes/research-pipeline-checkpointing/reports/` (sections 4 and 6 own these)

## Verification commands for the implementer to run at the end of sections 1–3

```bash
pytest tests/unit/test_editorial_migrations.py tests/unit/test_discovered_documents_repo.py \
  tests/unit/test_research_cycle.py tests/unit/test_orchestrator_cycle.py \
  tests/unit/test_research_endpoint.py tests/unit/test_research_agent_use_case.py -q
pytest tests/unit/ -q   # full suite — confirm no regressions, count grows from 224
```

Do not run curl/manual endpoint testing or write phase reports here — those
are mandatory but belong to section 4 (out of this plan's scope), to be
picked up separately per the user's instructions.
