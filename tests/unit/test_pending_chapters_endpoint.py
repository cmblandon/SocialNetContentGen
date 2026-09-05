"""
Tests for GET /chapters/pending — added to support the content-admin-panel
Approval Queue view (specs/content-admin-panel/spec.md: "Every pending item
must show the source Document, the Story summary, the Chapter script, and
ALL PlatformVersions for that chapter"). Not itemized as its own task in
tasks.md; added because the queue view cannot be built without a read
endpoint exposing this context — see tasks.md 6.4's note.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.editorial.application.approval_gate import approve_platform_version, persist_story
from src.editorial.core.entities import (
    ChapterDraft,
    FacebookAdaptation,
    InstagramAdaptation,
    PlatformAdaptations,
    StoryDraft,
    TikTokAdaptation,
    XAdaptation,
)
from src.editorial.infrastructure.persistence.models import Base, Document
from src.editorial.infrastructure.persistence.session import get_session
from src.editorial.presentation.app import app
from src.editorial.presentation.dependencies import get_publishing_use_case


class FakePublishingUseCase:
    def publish(self, session, platform_version_id):
        from src.editorial.application.publishing_use_case import PublishOutcome
        return PublishOutcome(published=False, proposed_time="12:00")


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(test_engine):
    TestSessionLocal = sessionmaker(bind=test_engine)

    def override_get_session():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_publishing_use_case] = lambda: FakePublishingUseCase()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_chapter(test_engine, title="AARO 2024 Annual Report"):
    from sqlalchemy.orm import Session

    with Session(test_engine) as session:
        document = Document(
            title=title, agency="AARO", doc_type="report", extracted_text="text",
            source_url="https://www.aaro.mil/reports/2024.pdf", published_date="2024-03-01",
        )
        session.add(document)
        session.commit()
        story_draft = StoryDraft(
            summary="A radar contact goes unexplained.",
            chapters=[
                ChapterDraft(title="Part 1", script="Chapter script.", visual_notes="notes", source_citation="AARO, report, 2024-03-01", chapter_index=1)
            ],
        )
        adaptations = PlatformAdaptations(
            tiktok=TikTokAdaptation(script="s", on_screen_hook_lines=["a", "b"], hashtags=["#a", "#b", "#c"], description="d"),
            instagram=InstagramAdaptation(carousel_slides=["1", "2", "3", "4", "5", "6"]),
            x=XAdaptation(tweets=["t1", "t2", "t3", "t4"]),
            facebook=FacebookAdaptation(post="p?"),
        )
        story = persist_story(session, document, story_draft, [adaptations])
        return story.chapters[0].id, [pv.id for pv in story.chapters[0].platform_versions]


def test_lists_a_chapter_with_pending_platform_versions_and_full_context(client, test_engine):
    _seed_chapter(test_engine)

    response = client.get("/chapters/pending")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    chapter = body[0]
    assert chapter["title"] == "Part 1"
    assert chapter["script"] == "Chapter script."
    assert chapter["source_citation"] == "AARO, report, 2024-03-01"
    assert chapter["story_summary"] == "A radar contact goes unexplained."
    assert chapter["document"]["title"] == "AARO 2024 Annual Report"
    assert chapter["document"]["agency"] == "AARO"
    assert len(chapter["platform_versions"]) == 4
    assert {pv["platform"] for pv in chapter["platform_versions"]} == {"tiktok", "instagram", "x", "facebook"}
    assert all(pv["status"] == "pending_review" for pv in chapter["platform_versions"])


def test_excludes_a_chapter_once_all_its_platform_versions_are_decided(client, test_engine):
    _, platform_version_ids = _seed_chapter(test_engine)
    from sqlalchemy.orm import Session
    with Session(test_engine) as session:
        for pv_id in platform_version_ids:
            approve_platform_version(session, pv_id)

    response = client.get("/chapters/pending")

    assert response.json() == []


def test_returns_empty_list_when_nothing_is_pending(client):
    response = client.get("/chapters/pending")

    assert response.status_code == 200
    assert response.json() == []
