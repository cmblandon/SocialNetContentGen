"""
Tests for the approve/reject endpoints — the Phase 3 stand-in for the real
admin panel (Phase 6), per specs/editorial-orchestration/spec.md and the
design.md Phase 3 migration note. Named /platform-versions/{id}/... rather
than tasks.md's placeholder /cycles/{id}/... since there is no Cycle
entity in the schema — the thing actually being approved/rejected is a
PlatformVersion.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.editorial.application.approval_gate import persist_story
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
from src.editorial.application.publishing_use_case import PublishOutcome
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


def test_approve_transitions_status_and_returns_200(client, test_engine, pending_platform_version_id):
    response = client.post(f"/platform-versions/{pending_platform_version_id}/approve")

    assert response.status_code == 200
    assert response.json()["status"] == "approved"

    with Session(test_engine) as session:
        assert session.get(PlatformVersion, pending_platform_version_id).status == ApprovalStatus.APPROVED


def test_reject_transitions_status_and_returns_200(client, test_engine, pending_platform_version_id):
    response = client.post(f"/platform-versions/{pending_platform_version_id}/reject")

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    with Session(test_engine) as session:
        assert session.get(PlatformVersion, pending_platform_version_id).status == ApprovalStatus.REJECTED


def test_approve_unknown_id_returns_404(client):
    response = client.post("/platform-versions/does-not-exist/approve")

    assert response.status_code == 404


def test_reject_unknown_id_returns_404(client):
    response = client.post("/platform-versions/does-not-exist/reject")

    assert response.status_code == 404


def test_approve_an_already_decided_item_returns_409(client, pending_platform_version_id):
    client.post(f"/platform-versions/{pending_platform_version_id}/approve")

    response = client.post(f"/platform-versions/{pending_platform_version_id}/approve")

    assert response.status_code == 409


def test_reject_an_already_decided_item_returns_409(client, pending_platform_version_id):
    client.post(f"/platform-versions/{pending_platform_version_id}/reject")

    response = client.post(f"/platform-versions/{pending_platform_version_id}/reject")

    assert response.status_code == 409


def test_approve_triggers_publishing_and_includes_the_outcome(
    client, pending_platform_version_id, fake_publishing_use_case
):
    """Requirement (specs/editorial-orchestration): approving is what makes
    the orchestrator 'proceed to publishing' for that chapter."""
    response = client.post(f"/platform-versions/{pending_platform_version_id}/approve")

    assert response.status_code == 200
    assert fake_publishing_use_case.calls == [pending_platform_version_id]
    assert response.json()["publish_outcome"] == {
        "published": False,
        "external_post_id": None,
        "error_message": None,
        "proposed_time": "12:00",
    }


def test_reject_never_triggers_publishing(client, pending_platform_version_id, fake_publishing_use_case):
    client.post(f"/platform-versions/{pending_platform_version_id}/reject")

    assert fake_publishing_use_case.calls == []
