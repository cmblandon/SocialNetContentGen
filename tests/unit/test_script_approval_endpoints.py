"""
Tests for the script review endpoints — specs/script-approval-workflow/spec.md.

Approval is chapter-scoped and fans out to every platform version of that
chapter, so the assertions here check the fan-out rather than a single row.
The load-bearing behaviour is the reset: editing an approved script must
clear approval, or video generation would narrate text no one signed off on.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.editorial.infrastructure.persistence.models import (
    ApprovalStatus,
    Base,
    Chapter,
    Document,
    PlatformName,
    PlatformVersion,
    Story,
)
from src.editorial.infrastructure.persistence.session import get_session
from src.editorial.presentation.app import app

CHAPTER_SCRIPT = "Una frase del guion. Otra frase del guion."


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


def _seed_chapter(engine, *, status=ApprovalStatus.PENDING_REVIEW) -> str:
    """A chapter with all four platform versions, as persist_story creates."""
    with Session(engine) as session:
        document = Document(
            title="AARO 2024 Annual Report",
            agency="AARO",
            doc_type="report",
            extracted_text="Full text.",
        )
        story = Story(document=document, summary="A radar contact goes unexplained.")
        chapter = Chapter(
            story=story,
            chapter_index=1,
            title="Part 1",
            script=CHAPTER_SCRIPT,
            visual_notes="archival footage of military radar",
            source_citation="AARO, report, 2024-03-01",
        )
        session.add_all([document, story, chapter])
        for platform in PlatformName:
            session.add(
                PlatformVersion(
                    chapter=chapter,
                    platform=platform,
                    content="{}",
                    status=status,
                )
            )
        session.commit()
        return chapter.id


def _platform_versions(engine, chapter_id) -> list[PlatformVersion]:
    with Session(engine) as session:
        chapter = session.get(Chapter, chapter_id)
        return list(chapter.platform_versions)


def test_approve_sets_flag_on_every_platform_version(client, test_engine):
    chapter_id = _seed_chapter(test_engine)

    response = client.post(f"/chapters/{chapter_id}/script/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["script_approved"] is True
    assert body["script_approved_at"] is not None
    assert body["platform_versions_updated"] == 4

    versions = _platform_versions(test_engine, chapter_id)
    assert all(pv.script_approved for pv in versions)
    assert all(pv.script_approved_at is not None for pv in versions)


def test_reject_clears_flag_on_every_platform_version(client, test_engine):
    chapter_id = _seed_chapter(test_engine)
    client.post(f"/chapters/{chapter_id}/script/approve")

    response = client.post(f"/chapters/{chapter_id}/script/reject")

    assert response.status_code == 200
    assert response.json()["script_approved"] is False
    assert response.json()["script_approved_at"] is None

    versions = _platform_versions(test_engine, chapter_id)
    assert not any(pv.script_approved for pv in versions)
    assert all(pv.script_approved_at is None for pv in versions)


def test_update_replaces_script_text(client, test_engine):
    chapter_id = _seed_chapter(test_engine)

    response = client.post(
        f"/chapters/{chapter_id}/script/update",
        json={"script_text": "Un guion completamente nuevo."},
    )

    assert response.status_code == 200
    with Session(test_engine) as session:
        assert session.get(Chapter, chapter_id).script == "Un guion completamente nuevo."


def test_editing_an_approved_script_resets_approval(client, test_engine):
    """The gate's whole point: narrated text is text a human read."""
    chapter_id = _seed_chapter(test_engine)
    client.post(f"/chapters/{chapter_id}/script/approve")

    response = client.post(
        f"/chapters/{chapter_id}/script/update",
        json={"script_text": "Texto editado despues de la aprobacion."},
    )

    assert response.status_code == 200
    assert response.json()["script_approved"] is False
    assert response.json()["script_approved_at"] is None

    versions = _platform_versions(test_engine, chapter_id)
    assert not any(pv.script_approved for pv in versions)


def test_update_rejects_blank_script(client, test_engine):
    chapter_id = _seed_chapter(test_engine)

    response = client.post(
        f"/chapters/{chapter_id}/script/update", json={"script_text": "   "}
    )

    assert response.status_code == 422
    with Session(test_engine) as session:
        assert session.get(Chapter, chapter_id).script == CHAPTER_SCRIPT


def test_update_rejects_missing_script_text(client, test_engine):
    chapter_id = _seed_chapter(test_engine)

    response = client.post(f"/chapters/{chapter_id}/script/update", json={})

    assert response.status_code == 422


def test_approve_unknown_chapter_returns_404(client):
    response = client.post("/chapters/no-such-id/script/approve")
    assert response.status_code == 404


def test_reject_unknown_chapter_returns_404(client):
    response = client.post("/chapters/no-such-id/script/reject")
    assert response.status_code == 404


def test_update_unknown_chapter_returns_404(client):
    response = client.post(
        "/chapters/no-such-id/script/update", json={"script_text": "texto"}
    )
    assert response.status_code == 404


def test_pending_scripts_lists_chapter_with_review_fields(client, test_engine):
    chapter_id = _seed_chapter(test_engine)

    response = client.get("/chapters/pending/scripts")

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == chapter_id
    assert row["title"] == "Part 1"
    assert row["script"] == CHAPTER_SCRIPT
    assert row["source_citation"] == "AARO, report, 2024-03-01"
    assert row["script_approved"] is False
    assert row["script_approved_at"] is None
    assert row["created_at"] is not None
    assert row["word_count"] == len(CHAPTER_SCRIPT.split())


def test_pending_scripts_reflects_approval(client, test_engine):
    chapter_id = _seed_chapter(test_engine)
    client.post(f"/chapters/{chapter_id}/script/approve")

    row = client.get("/chapters/pending/scripts").json()[0]

    assert row["script_approved"] is True
    assert row["script_approved_at"] is not None


def test_pending_scripts_reports_partial_approval_as_unapproved(client, test_engine):
    """A chapter is approved only when every platform version is."""
    chapter_id = _seed_chapter(test_engine)
    client.post(f"/chapters/{chapter_id}/script/approve")

    with Session(test_engine) as session:
        chapter = session.get(Chapter, chapter_id)
        chapter.platform_versions[0].script_approved = False
        session.commit()

    assert client.get("/chapters/pending/scripts").json()[0]["script_approved"] is False


def test_pending_scripts_excludes_fully_terminal_chapters(client, test_engine):
    """Mirrors /chapters/pending: a chapter drops out once nothing is active."""
    _seed_chapter(test_engine, status=ApprovalStatus.PUBLISHED)

    assert client.get("/chapters/pending/scripts").json() == []


def test_pending_scripts_is_empty_when_nothing_seeded(client):
    assert client.get("/chapters/pending/scripts").json() == []
