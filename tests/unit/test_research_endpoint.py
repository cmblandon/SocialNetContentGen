"""
Tests for POST /research/run — the manual trigger for a research+curation
pass (design.md defers cron/daily automation as a Non-Goal; this is the
operator-triggered stand-in). Real scraper/LLM adapters are overridden with
fakes via FastAPI's dependency_overrides, matching how get_session is
already overridden for the approval endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.editorial.application.case_curation_use_case import (
    CurationResult,
    CurationScore,
)
from src.editorial.application.platform_adaptation_use_case import (
    PlatformAdaptationUseCase,
)
from src.editorial.application.research_agent_use_case import ResearchResult
from src.editorial.application.story_writing_use_case import StoryWritingUseCase
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
from src.editorial.infrastructure.persistence.models import Base
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore
from src.editorial.infrastructure.persistence.session import get_session
from src.editorial.presentation.app import app
from src.editorial.presentation.routers.research import (
    get_case_curation,
    get_memory_store,
    get_platform_adaptation_use_case,
    get_research_agent,
    get_story_writing_use_case,
)


class FakeResearchAgent:
    def __init__(self, documents):
        self._documents = documents

    def discover(self, source_urls):
        return ResearchResult(documents=self._documents, discarded=[])


class FakeCaseCuration:
    def curate(self, document):
        return CurationResult(
            document=document,
            score=CurationScore(5, 5, 4, 3, 3),
            advanced=True,
            narrative_angle="angle",
        )


class FakeStoryWritingUseCase:
    def write_story(self, **kwargs):
        return StoryDraft(
            summary="s",
            chapters=[ChapterDraft(title="P1", script="script", visual_notes="n", source_citation="c", chapter_index=1)],
        )


class FakePlatformAdaptationUseCase:
    def adapt_chapter(self, **kwargs):
        return PlatformAdaptations(
            tiktok=TikTokAdaptation(script="s", on_screen_hook_lines=["a", "b"], hashtags=["#a", "#b", "#c"], description="d"),
            instagram=InstagramAdaptation(carousel_slides=["1", "2", "3", "4", "5", "6"]),
            x=XAdaptation(tweets=["t1", "t2", "t3", "t4"]),
            facebook=FacebookAdaptation(post="p?"),
        )


@pytest.fixture
def client(tmp_path):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_session():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    document = ScrapedDocument(
        title="AARO 2024 Annual Report",
        agency="AARO",
        doc_type="report",
        extracted_text=" ".join(["word"] * 50),
        published_date="2024-03-01",
    )

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_memory_store] = lambda: ProjectMemoryStore(memory_dir=tmp_path)
    app.dependency_overrides[get_research_agent] = lambda: FakeResearchAgent([document])
    app.dependency_overrides[get_case_curation] = lambda: FakeCaseCuration()
    app.dependency_overrides[get_story_writing_use_case] = lambda: FakeStoryWritingUseCase()
    app.dependency_overrides[get_platform_adaptation_use_case] = lambda: FakePlatformAdaptationUseCase()

    yield TestClient(app)
    app.dependency_overrides.clear()


def test_run_research_returns_cycle_summary(client):
    response = client.post("/research/run", json={"source_urls": ["https://www.aaro.mil/reports/2024.pdf"]})

    assert response.status_code == 200
    body = response.json()
    assert body["documents_reviewed"] == 1
    assert body["stories_created"] == 1
    assert body["chapters_generated"] == 1
    assert len(body["pending_approval_platform_version_ids"]) == 4


def test_run_research_requires_at_least_one_source_url(client):
    response = client.post("/research/run", json={"source_urls": []})

    assert response.status_code == 422
