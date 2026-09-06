"""
Tests for the subtitle review endpoints — specs/subtitle-generation-and-approval.

The behaviours that matter here are the gate (no captions from an unapproved
script), timing preservation across an edit, and idempotence: regenerating
must never silently discard an editor's corrections.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.editorial.application.subtitle_generation_use_case import (
    SubtitleGenerationUseCase,
)
from src.editorial.application.subtitle_review_use_case import SubtitleReviewUseCase
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
from src.editorial.infrastructure.persistence.subtitle_store import SubtitleStore
from src.editorial.presentation.app import app
from src.editorial.presentation.dependencies import get_subtitle_review_use_case

CHAPTER_SCRIPT = "Primera frase del guion. Segunda frase del guion."


class FakeTTSClient:
    def __init__(self, duration_ms: int = 4000):
        self.duration_ms = duration_ms
        self.calls: list[tuple[str, str]] = []

    def generate_speech(self, text: str, language: str, output_path: str) -> int:
        self.calls.append((text, language))
        with open(output_path, "wb") as f:
            f.write(b"fake-audio")
        return self.duration_ms

    def get_audio_duration(self, audio_path: str) -> int:
        return self.duration_ms


class FakeLLMClient:
    def complete(self, prompt: str) -> str:
        return "First script sentence. Second script sentence."


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
def tts():
    return FakeTTSClient()


@pytest.fixture
def store(tmp_path):
    return SubtitleStore(
        subtitle_root=tmp_path / "subtitles", audio_root=tmp_path / "audio"
    )


@pytest.fixture
def client(test_engine, tts, store, tmp_path):
    TestSessionLocal = sessionmaker(bind=test_engine)

    def override_get_session():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    use_case = SubtitleReviewUseCase(
        tts_client=tts,
        subtitle_use_case=SubtitleGenerationUseCase(
            FakeLLMClient(), cache_dir=tmp_path / "cache"
        ),
        subtitle_store=store,
    )

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_subtitle_review_use_case] = lambda: use_case
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_chapter(engine, *, script_approved: bool) -> str:
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
            visual_notes="archival footage",
            source_citation="AARO, report, 2024-03-01",
        )
        session.add_all([document, story, chapter])
        for platform in PlatformName:
            session.add(
                PlatformVersion(
                    chapter=chapter,
                    platform=platform,
                    content="{}",
                    status=ApprovalStatus.PENDING_REVIEW,
                    script_approved=script_approved,
                )
            )
        session.commit()
        return chapter.id


def test_generate_produces_spanish_and_english_tracks(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)

    response = client.post(f"/chapters/{chapter_id}/subtitles/generate")

    assert response.status_code == 200
    tracks = response.json()
    assert {track["lang"] for track in tracks} == {"es", "en"}
    assert all(track["edited"] is False for track in tracks)
    assert all(len(track["segments"]) > 0 for track in tracks)


def test_generate_uses_srt_timecode_format(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)

    tracks = client.post(f"/chapters/{chapter_id}/subtitles/generate").json()

    segment = tracks[0]["segments"][0]
    assert segment["start"] == "00:00:00,000"
    assert segment["index"] == 1
    # HH:MM:SS,mmm
    assert len(segment["end"]) == len("00:00:00,000")
    assert "," in segment["end"]


def test_generate_rejects_unapproved_script_with_409(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=False)

    response = client.post(f"/chapters/{chapter_id}/subtitles/generate")

    assert response.status_code == 409
    assert "approved" in response.json()["detail"].lower()


def test_generate_unknown_chapter_returns_404(client):
    assert client.post("/chapters/no-such-id/subtitles/generate").status_code == 404


def test_generate_is_idempotent(client, test_engine, tts):
    """A second call must not re-synthesize or overwrite existing tracks."""
    chapter_id = _seed_chapter(test_engine, script_approved=True)

    client.post(f"/chapters/{chapter_id}/subtitles/generate")
    calls_after_first = len(tts.calls)
    client.post(f"/chapters/{chapter_id}/subtitles/generate")

    assert len(tts.calls) == calls_after_first


def test_get_returns_empty_before_generation(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)

    response = client.get(f"/chapters/{chapter_id}/subtitles")

    assert response.status_code == 200
    assert response.json() == []


def test_get_returns_generated_tracks(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)
    client.post(f"/chapters/{chapter_id}/subtitles/generate")

    tracks = client.get(f"/chapters/{chapter_id}/subtitles").json()

    assert {track["lang"] for track in tracks} == {"es", "en"}


def test_get_unknown_chapter_returns_404(client):
    assert client.get("/chapters/no-such-id/subtitles").status_code == 404


def test_update_replaces_text_and_preserves_timing(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)
    original = client.post(f"/chapters/{chapter_id}/subtitles/generate").json()
    spanish = next(track for track in original if track["lang"] == "es")

    response = client.post(
        f"/chapters/{chapter_id}/subtitles/update",
        json={
            "lang": "es",
            "segments": [
                {"index": segment["index"], "text": f"corregido {segment['index']}"}
                for segment in spanish["segments"]
            ],
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["edited"] is True
    assert [s["text"] for s in updated["segments"]] == [
        f"corregido {s['index']}" for s in spanish["segments"]
    ]
    # Timing is untouched.
    assert [(s["start"], s["end"]) for s in updated["segments"]] == [
        (s["start"], s["end"]) for s in spanish["segments"]
    ]


def test_update_rejects_wrong_segment_count(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)
    client.post(f"/chapters/{chapter_id}/subtitles/generate")

    response = client.post(
        f"/chapters/{chapter_id}/subtitles/update",
        json={"lang": "es", "segments": [{"index": 1, "text": "solo uno"}]},
    )

    assert response.status_code == 422
    assert "segment" in response.json()["detail"].lower()


def test_update_rejects_unknown_language(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)
    client.post(f"/chapters/{chapter_id}/subtitles/generate")

    response = client.post(
        f"/chapters/{chapter_id}/subtitles/update",
        json={"lang": "fr", "segments": [{"index": 1, "text": "bonjour"}]},
    )

    assert response.status_code == 422


def test_update_before_generation_returns_404(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)

    response = client.post(
        f"/chapters/{chapter_id}/subtitles/update",
        json={"lang": "es", "segments": [{"index": 1, "text": "texto"}]},
    )

    assert response.status_code == 404


def test_update_rejects_blank_segment_text(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)
    client.post(f"/chapters/{chapter_id}/subtitles/generate")

    response = client.post(
        f"/chapters/{chapter_id}/subtitles/update",
        json={"lang": "es", "segments": [{"index": 1, "text": ""}]},
    )

    assert response.status_code == 422


def test_edit_survives_regeneration(client, test_engine):
    """The spec's 'edited subtitles are used in video composition' depends on
    regeneration not clobbering the edit."""
    chapter_id = _seed_chapter(test_engine, script_approved=True)
    original = client.post(f"/chapters/{chapter_id}/subtitles/generate").json()
    spanish = next(track for track in original if track["lang"] == "es")

    client.post(
        f"/chapters/{chapter_id}/subtitles/update",
        json={
            "lang": "es",
            "segments": [
                {"index": s["index"], "text": "texto corregido"}
                for s in spanish["segments"]
            ],
        },
    )
    client.post(f"/chapters/{chapter_id}/subtitles/generate")

    tracks = client.get(f"/chapters/{chapter_id}/subtitles").json()
    spanish_now = next(track for track in tracks if track["lang"] == "es")
    assert spanish_now["edited"] is True
    assert all(s["text"] == "texto corregido" for s in spanish_now["segments"])
