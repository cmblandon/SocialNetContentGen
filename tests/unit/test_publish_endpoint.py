"""
Tests for the explicit publish endpoint — per design.md Decision 1 of the
enhance-admin-panel-ui change: publishing is no longer a side effect of
approval, it's its own action. Named /platform-versions/{id}/publish for
the same reason test_approval_endpoints.py uses /platform-versions/{id}/...
— the thing being acted on is a PlatformVersion, not a Cycle.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.editorial.application.approval_gate import persist_story
from src.editorial.application.publishing_use_case import (
    PublishingUseCase,
    PublishOutcome,
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
from src.editorial.infrastructure.persistence.models import (
    ApprovalStatus,
    Base,
    Document,
    PlatformVersion,
)
from src.editorial.infrastructure.persistence.project_memory import (
    ProjectMemoryStore,
)
from src.editorial.infrastructure.persistence.session import get_session
from src.editorial.presentation.app import app
from src.editorial.presentation.dependencies import get_publishing_use_case


class FakePublishingUseCase:
    def __init__(self, outcome: PublishOutcome):
        self._outcome = outcome
        self.calls: list[str] = []

    def publish(self, session, platform_version_id):
        self.calls.append(platform_version_id)
        return self._outcome


class StubPublisher:
    def publish(self, platform: str, content: str, scheduled_at=None):  # pragma: no cover - never reached
        raise AssertionError("publisher should not be invoked when the gate rejects the request")


@pytest.fixture
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def fake_publishing_use_case():
    return FakePublishingUseCase(PublishOutcome(published=False, proposed_time="12:00"))


@pytest.fixture
def client(test_engine, fake_publishing_use_case):
    TestSessionLocal = sessionmaker(bind=test_engine)

    def override_get_session():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_publishing_use_case] = lambda: fake_publishing_use_case
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def client_with_real_publishing_use_case(test_engine, tmp_path):
    TestSessionLocal = sessionmaker(bind=test_engine)

    def override_get_session():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    real_use_case = PublishingUseCase(
        publisher=StubPublisher(),
        memory_store=ProjectMemoryStore(memory_dir=tmp_path),
    )

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_publishing_use_case] = lambda: real_use_case
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def pending_platform_version_id(test_engine):
    with Session(test_engine) as session:
        document = Document(title="t", agency="AARO", doc_type="report", extracted_text="text")
        session.add(document)
        session.commit()

        story_draft = StoryDraft(
            summary="s",
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
        adaptations = PlatformAdaptations(
            tiktok=TikTokAdaptation(script="s", on_screen_hook_lines=["a", "b"], hashtags=["#a", "#b", "#c"], description="d"),
            instagram=InstagramAdaptation(carousel_slides=["1", "2", "3", "4", "5", "6"]),
            x=XAdaptation(tweets=["t1", "t2", "t3", "t4"]),
            facebook=FacebookAdaptation(post="p?"),
        )
        story = persist_story(session, document, story_draft, [adaptations])
        return story.chapters[0].platform_versions[0].id


@pytest.fixture
def approved_platform_version_id(test_engine, pending_platform_version_id):
    with Session(test_engine) as session:
        platform_version = session.get(PlatformVersion, pending_platform_version_id)
        platform_version.status = ApprovalStatus.APPROVED
        session.commit()
    return pending_platform_version_id


def test_publish_invokes_use_case_and_returns_the_outcome_flat(
    client, approved_platform_version_id, fake_publishing_use_case
):
    response = client.post(f"/platform-versions/{approved_platform_version_id}/publish")

    assert response.status_code == 200
    assert fake_publishing_use_case.calls == [approved_platform_version_id]
    body = response.json()
    assert "publish_outcome" not in body
    assert "id" not in body
    assert "status" not in body
    assert body == {
        "published": False,
        "external_post_id": None,
        "error_message": None,
        "proposed_time": "12:00",
    }


def test_publish_unknown_id_returns_404(client):
    response = client.post("/platform-versions/does-not-exist/publish")

    assert response.status_code == 404


def test_publish_on_a_not_yet_approved_version_returns_409(
    client_with_real_publishing_use_case, pending_platform_version_id
):
    response = client_with_real_publishing_use_case.post(
        f"/platform-versions/{pending_platform_version_id}/publish"
    )

    assert response.status_code == 409
