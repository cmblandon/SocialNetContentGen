"""
Tests for GET /publish-records — the Phase 5 read model the admin panel
(Phase 6) will consume for the editorial calendar view.
"""
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.editorial.application.approval_gate import approve_platform_version, persist_story
from src.editorial.application.publishing_use_case import PublishingUseCase
from src.editorial.core.entities import (
    ChapterDraft,
    FacebookAdaptation,
    InstagramAdaptation,
    PlatformAdaptations,
    StoryDraft,
    TikTokAdaptation,
    XAdaptation,
)
from src.editorial.core.ports import PublishResult
from src.editorial.infrastructure.persistence.models import Base, Document
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore
from src.editorial.infrastructure.persistence.session import get_session
from src.editorial.presentation.app import app


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
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_publish_records_returns_empty_list_when_none_exist(client):
    response = client.get("/publish-records")

    assert response.status_code == 200
    assert response.json() == []


def test_list_publish_records_returns_a_published_record(client, test_engine):
    with Session(test_engine) as session:
        document = Document(title="t", agency="AARO", doc_type="report", extracted_text="text")
        session.add(document)
        session.commit()
        story_draft = StoryDraft(
            summary="s",
            chapters=[ChapterDraft(title="P1", script="script", visual_notes="n", source_citation="c", chapter_index=1)],
        )
        adaptations = PlatformAdaptations(
            tiktok=TikTokAdaptation(script="s", on_screen_hook_lines=["a", "b"], hashtags=["#a", "#b", "#c"], description="d"),
            instagram=InstagramAdaptation(carousel_slides=["1", "2", "3", "4", "5", "6"]),
            x=XAdaptation(tweets=["t1", "t2", "t3", "t4"]),
            facebook=FacebookAdaptation(post="p?"),
        )
        story = persist_story(session, document, story_draft, [adaptations])
        platform_version_id = next(
            pv.id for pv in story.chapters[0].platform_versions if pv.platform.value == "tiktok"
        )
        approve_platform_version(session, platform_version_id)

        class FakePublisher:
            def publish(self, platform, content, scheduled_at=None):
                return PublishResult(success=True, external_post_id="postiz-999")

        memory_store = ProjectMemoryStore(memory_dir=Path(tempfile.mkdtemp()))
        memory_store.append_calendario_entry("optimal_time:tiktok=18:00")
        use_case = PublishingUseCase(publisher=FakePublisher(), memory_store=memory_store)
        use_case.publish(session, platform_version_id)

    response = client.get("/publish-records")

    assert response.status_code == 200
    records = response.json()
    assert len(records) == 1
    assert records[0]["platform_version_id"] == platform_version_id
    assert records[0]["platform"] == "tiktok"
    assert records[0]["status"] == "published"
    assert records[0]["external_post_id"] == "postiz-999"
