"""
Tests for run_research_cycle — wires ResearchAgentUseCase and
CaseCurationUseCase into the orchestrator's run_cycle, replacing the
Phase 2 manual-curation CLI fixture as the real input path (only advanced,
curated documents reach story-writing).
"""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.editorial.application.orchestrator import run_research_cycle
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
from src.editorial.infrastructure.persistence.models import Base, Document
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

    def discover(self, source_urls):
        from src.editorial.application.research_agent_use_case import ResearchResult

        return ResearchResult(documents=self._documents, discarded=[])


class FakeCaseCuration:
    def __init__(self, results_by_title: dict):
        self._results_by_title = results_by_title
        self.curated_titles: list[str] = []

    def curate(self, document):
        self.curated_titles.append(document.title)
        return self._results_by_title.get(document.title)


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


def _scraped_document(title="AARO 2024 Annual Report") -> ScrapedDocument:
    return ScrapedDocument(
        title=title,
        agency="AARO",
        doc_type="report",
        extracted_text=" ".join(["word"] * 50),
        published_date="2024-03-01",
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
