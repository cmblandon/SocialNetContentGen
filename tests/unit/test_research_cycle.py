"""
Tests for run_research_cycle — wires ResearchAgentUseCase and
CaseCurationUseCase into the orchestrator's run_cycle, replacing the
Phase 2 manual-curation CLI fixture as the real input path (only advanced,
curated documents reach story-writing).
"""
from typing import Optional

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.editorial.application.orchestrator import CycleSummary, run_research_cycle, run_resume_cycle
from src.editorial.core.entities import (
    ChapterDraft,
    FacebookAdaptation,
    InstagramAdaptation,
    PlatformAdaptations,
    StoryDraft,
    TikTokAdaptation,
    XAdaptation,
)
from src.editorial.core.ports import ScrapedDocument
from src.editorial.infrastructure.persistence.models import (
    Base,
    CurationStatus,
    DiscoveredDocument,
    Document,
    Story,
)
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


class FakeCaseCuration:
    def __init__(self, results_by_title: dict):
        self._results_by_title = results_by_title
        self.curated_titles: list[str] = []

    def curate(self, document):
        self.curated_titles.append(document.title)
        return self._results_by_title.get(document.title)


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


class FakeStoryWritingUseCase:
    def __init__(self, story: StoryDraft):
        self._story = story

    def write_story(self, **kwargs):
        return self._story


class FakePlatformAdaptationUseCase:
    def adapt_chapter(self, **kwargs):
        return PlatformAdaptations(
            tiktok=TikTokAdaptation(script="s", on_screen_hook_lines=["a", "b"], hashtags=["#a", "#b", "#c"], description="d"),
            instagram=InstagramAdaptation(carousel_slides=["1", "2", "3", "4", "5", "6"]),
            x=XAdaptation(tweets=["t1", "t2", "t3", "t4"]),
            facebook=FacebookAdaptation(post="p?"),
        )


def _scraped_document(title="AARO 2024 Annual Report", source_url=None) -> ScrapedDocument:
    return ScrapedDocument(
        title=title,
        agency="AARO",
        doc_type="report",
        extracted_text=" ".join(["word"] * 50),
        published_date="2024-03-01",
        source_url=source_url,
    )


def _curation_result(document, advanced=True, narrative_angle="angle"):
    from src.editorial.application.case_curation_use_case import (
        CurationResult,
        CurationScore,
    )

    return CurationResult(
        document=document,
        score=CurationScore(5, 5, 4, 3, 3),
        advanced=advanced,
        narrative_angle=narrative_angle if advanced else None,
    )


def _story() -> StoryDraft:
    return StoryDraft(
        summary="s",
        chapters=[ChapterDraft(title="P1", script="script", visual_notes="n", source_citation="c", chapter_index=1)],
    )


def test_advanced_documents_are_persisted_and_written_into_stories(session, memory_store):
    document = _scraped_document()
    research_agent = FakeResearchAgent([document])
    case_curation = FakeCaseCuration({document.title: _curation_result(document)})
    writer = FakeStoryWritingUseCase(_story())
    adapter = FakePlatformAdaptationUseCase()

    summary = run_research_cycle(
        session=session,
        source_urls=["https://www.aaro.mil/reports/2024.pdf"],
        research_agent=research_agent,
        case_curation=case_curation,
        story_writing_use_case=writer,
        platform_adaptation_use_case=adapter,
        memory_store=memory_store,
    )

    assert summary.stories_created == 1
    persisted = session.execute(select(Document).where(Document.title == document.title)).scalar_one()
    assert persisted.agency == "AARO"


def test_documents_that_curation_discards_never_reach_story_writing(session, memory_store):
    document = _scraped_document()
    research_agent = FakeResearchAgent([document])
    case_curation = FakeCaseCuration({document.title: _curation_result(document, advanced=False)})
    writer = FakeStoryWritingUseCase(_story())
    adapter = FakePlatformAdaptationUseCase()

    summary = run_research_cycle(
        session=session,
        source_urls=["https://www.aaro.mil/reports/2024.pdf"],
        research_agent=research_agent,
        case_curation=case_curation,
        story_writing_use_case=writer,
        platform_adaptation_use_case=adapter,
        memory_store=memory_store,
    )

    assert summary.stories_created == 0
    assert session.execute(select(Document)).first() is None


def test_documents_curation_has_already_evaluated_are_skipped(session, memory_store):
    document = _scraped_document()
    research_agent = FakeResearchAgent([document])
    case_curation = FakeCaseCuration({})  # curate() returns None for every title
    writer = FakeStoryWritingUseCase(_story())
    adapter = FakePlatformAdaptationUseCase()

    summary = run_research_cycle(
        session=session,
        source_urls=["https://www.aaro.mil/reports/2024.pdf"],
        research_agent=research_agent,
        case_curation=case_curation,
        story_writing_use_case=writer,
        platform_adaptation_use_case=adapter,
        memory_store=memory_store,
    )

    assert summary.stories_created == 0
    assert case_curation.curated_titles == [document.title]


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
    fails against that code and must pass once run_cycle is called
    immediately per advancing document.
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
