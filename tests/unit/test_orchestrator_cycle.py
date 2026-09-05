"""
Tests for the orchestrator's run_cycle — the top-level function tying
together readiness-checking, delegation to the Phase 2 use cases,
persistence behind the approval gate, and project-memory bookkeeping.
Per specs/editorial-orchestration/spec.md: "Discard or escalate ambiguous
or unverifiable material instead of inventing details."
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.editorial.application.orchestrator import (
    DocumentNotReadyError,
    ensure_document_is_ready_for_writing,
    run_cycle,
)
from src.editorial.core.entities import (
    ChapterDraft,
    FacebookAdaptation,
    InstagramAdaptation,
    PlatformAdaptations,
    StoryDraft,
    TikTokAdaptation,
    XAdaptation,
)
from src.editorial.infrastructure.persistence.models import ApprovalStatus, Base, Document
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def memory_store(tmp_path):
    return ProjectMemoryStore(memory_dir=tmp_path)


def _ready_document(session, **overrides) -> Document:
    defaults = dict(
        title="AARO 2024 Annual Report",
        agency="AARO",
        doc_type="report",
        extracted_text=" ".join(["word"] * 50),
        published_date="2024-03-01",
    )
    defaults.update(overrides)
    document = Document(**defaults)
    session.add(document)
    session.commit()
    return document


class FakeStoryWritingUseCase:
    def __init__(self, story: StoryDraft):
        self._story = story

    def write_story(self, **kwargs):
        return self._story


class FakePlatformAdaptationUseCase:
    def __init__(self, adaptations: PlatformAdaptations):
        self._adaptations = adaptations

    def adapt_chapter(self, **kwargs):
        return self._adaptations


def _story_with_one_chapter() -> StoryDraft:
    return StoryDraft(
        summary="A radar contact goes unexplained.",
        chapters=[
            ChapterDraft(
                title="Part 1",
                script="script",
                visual_notes="notes",
                source_citation="AARO, report, 2024-03-01",
                chapter_index=1,
            )
        ],
    )


def _adaptations() -> PlatformAdaptations:
    return PlatformAdaptations(
        tiktok=TikTokAdaptation(script="s", on_screen_hook_lines=["a", "b"], hashtags=["#a", "#b", "#c"], description="d"),
        instagram=InstagramAdaptation(carousel_slides=["1", "2", "3", "4", "5", "6"]),
        x=XAdaptation(tweets=["t1", "t2", "t3", "t4"]),
        facebook=FacebookAdaptation(post="p?"),
    )


# --- Requirement: readiness check (specs/editorial-orchestration) ---


def test_ready_document_passes_the_readiness_check(session):
    document = _ready_document(session)

    ensure_document_is_ready_for_writing(document)  # should not raise


def test_document_missing_agency_is_not_ready(session):
    document = _ready_document(session, agency="")

    with pytest.raises(DocumentNotReadyError):
        ensure_document_is_ready_for_writing(document)


def test_document_missing_doc_type_is_not_ready(session):
    document = _ready_document(session, doc_type="")

    with pytest.raises(DocumentNotReadyError):
        ensure_document_is_ready_for_writing(document)


def test_document_with_insufficient_text_is_not_ready(session):
    document = _ready_document(session, extracted_text="too short")

    with pytest.raises(DocumentNotReadyError):
        ensure_document_is_ready_for_writing(document)


# --- run_cycle: discards unready documents instead of inventing details ---


def test_run_cycle_discards_an_unready_document_and_never_calls_the_writer(session, memory_store):
    unready_document = _ready_document(session, agency="")
    writer = FakeStoryWritingUseCase(_story_with_one_chapter())
    adapter = FakePlatformAdaptationUseCase(_adaptations())

    summary = run_cycle(
        session=session,
        documents_with_angles=[(unready_document, "angle")],
        story_writing_use_case=writer,
        platform_adaptation_use_case=adapter,
        memory_store=memory_store,
    )

    assert summary.documents_reviewed == 1
    assert summary.stories_created == 0
    assert unready_document.id in summary.discarded_document_ids
    assert unready_document.id in memory_store.read_casos_cubiertos()


def test_run_cycle_advances_a_ready_document_through_writing_and_adaptation(session, memory_store):
    document = _ready_document(session)
    writer = FakeStoryWritingUseCase(_story_with_one_chapter())
    adapter = FakePlatformAdaptationUseCase(_adaptations())

    summary = run_cycle(
        session=session,
        documents_with_angles=[(document, "military witness + radar corroboration")],
        story_writing_use_case=writer,
        platform_adaptation_use_case=adapter,
        memory_store=memory_store,
    )

    assert summary.documents_reviewed == 1
    assert summary.stories_created == 1
    assert summary.chapters_generated == 1
    assert len(summary.pending_approval_platform_version_ids) == 4  # one per platform
    assert str(document.id) in memory_store.read_casos_cubiertos()


def test_run_cycle_persists_platform_versions_as_pending_review(session, memory_store):
    document = _ready_document(session)
    writer = FakeStoryWritingUseCase(_story_with_one_chapter())
    adapter = FakePlatformAdaptationUseCase(_adaptations())

    summary = run_cycle(
        session=session,
        documents_with_angles=[(document, "angle")],
        story_writing_use_case=writer,
        platform_adaptation_use_case=adapter,
        memory_store=memory_store,
    )

    from src.editorial.infrastructure.persistence.models import PlatformVersion

    for platform_version_id in summary.pending_approval_platform_version_ids:
        pv = session.get(PlatformVersion, platform_version_id)
        assert pv.status == ApprovalStatus.PENDING_REVIEW


# --- End-of-cycle summary (specs/editorial-orchestration) ---


def test_run_cycle_summary_counts_across_multiple_documents(session, memory_store):
    ready = _ready_document(session)
    unready = _ready_document(session, doc_type="")
    writer = FakeStoryWritingUseCase(_story_with_one_chapter())
    adapter = FakePlatformAdaptationUseCase(_adaptations())

    summary = run_cycle(
        session=session,
        documents_with_angles=[(ready, "angle"), (unready, "angle")],
        story_writing_use_case=writer,
        platform_adaptation_use_case=adapter,
        memory_store=memory_store,
    )

    assert summary.documents_reviewed == 2
    assert summary.stories_created == 1
    assert summary.chapters_generated == 1
    assert len(summary.discarded_document_ids) == 1
    assert len(summary.pending_approval_platform_version_ids) == 4
