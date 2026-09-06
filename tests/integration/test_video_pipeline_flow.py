"""
End-to-end flow through the real HTTP surface (tasks 15.1-15.4).

Unlike the endpoint unit tests, nothing here injects a hand-built use case.
The app's own dependency graph is used, with only the three external
collaborators replaced — ElevenLabs, Unsplash, and FFmpeg — plus the
directories they write to. So this exercises the real wiring: the DI
providers, the routers, the use cases, the stores, and the database
together. A layer that works alone but is composed wrongly fails here and
nowhere else.

Not covered: real ElevenLabs/Unsplash calls (task 15.6), which need
credentials and cost money per run.
"""
from pathlib import Path

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
    VideoGeneration,
    VideoGenerationStatus,
)
from src.editorial.infrastructure.persistence.session import (
    get_session,
    get_session_factory,
)
from src.editorial.infrastructure.persistence.subtitle_store import SubtitleStore
from src.editorial.presentation.app import app
from src.editorial.presentation.dependencies import (
    get_image_client,
    get_llm_client,
    get_subtitle_generation_use_case,
    get_subtitle_store,
    get_text_to_speech_client,
    get_video_compositor,
    get_video_root,
)
from src.editorial.application.subtitle_generation_use_case import (
    SubtitleGenerationUseCase,
)

CHAPTER_SCRIPT = "Primera frase del guion. Segunda frase del guion."


class RecordingTTSClient:
    """Writes a real file so ffprobe-free duration handling still has bytes."""

    def __init__(self):
        self.synth_calls: list[tuple[str, str]] = []
        self.fail_next = False

    def generate_speech(self, text: str, language: str, output_path: str) -> int:
        self.synth_calls.append((text, language))
        if self.fail_next:
            raise RuntimeError("ElevenLabs quota exceeded")
        Path(output_path).write_bytes(b"fake-audio-bytes")
        return 4000

    def get_audio_duration(self, audio_path: str) -> int:
        return 4000


class RecordingImageClient:
    def __init__(self):
        self.searches: list[str] = []

    def search_image(self, query: str):
        self.searches.append(query)
        return None  # forces the documented colour+text fallback

    def download_image(self, url: str, output_path: str) -> None:  # pragma: no cover
        raise AssertionError("search returns None, so download must not run")

    def create_fallback_image(self, text: str, output_path: str) -> None:
        Path(output_path).write_bytes(b"fake-image-bytes")


class RecordingCompositor:
    def __init__(self):
        self.calls: list[dict] = []
        self.fail_next = False

    def composite(
        self, audio_path, visual_path, subtitle_path, output_path, duration_seconds=None
    ) -> None:
        self.calls.append({"subtitle_path": subtitle_path, "duration": duration_seconds})
        if self.fail_next:
            raise RuntimeError("FFmpeg encoder crashed")
        Path(output_path).write_bytes(b"fake-mp4" * 512)


class StubLLMClient:
    def complete(self, prompt: str) -> str:
        return "First script sentence. Second script sentence."


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def externals():
    return {
        "tts": RecordingTTSClient(),
        "images": RecordingImageClient(),
        "compositor": RecordingCompositor(),
    }


@pytest.fixture
def client(engine, externals, tmp_path):
    TestSessionLocal = sessionmaker(bind=engine)

    def override_session():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    store = SubtitleStore(
        subtitle_root=tmp_path / "subtitles", audio_root=tmp_path / "audio"
    )

    app.dependency_overrides = {
        get_session: override_session,
        get_session_factory: lambda: TestSessionLocal,
        get_text_to_speech_client: lambda: externals["tts"],
        get_image_client: lambda: externals["images"],
        get_video_compositor: lambda: externals["compositor"],
        get_subtitle_store: lambda: store,
        get_video_root: lambda: tmp_path / "videos_generated",
        get_llm_client: lambda: StubLLMClient(),
        get_subtitle_generation_use_case: lambda: SubtitleGenerationUseCase(
            StubLLMClient(), cache_dir=tmp_path / "cache"
        ),
    }
    yield TestClient(app)
    app.dependency_overrides.clear()


def seed_chapter(engine) -> str:
    """A curated document with a story, chapter, and all four platform versions."""
    with Session(engine) as session:
        document = Document(
            title="AARO 2024 Annual Report",
            agency="AARO",
            doc_type="report",
            extracted_text="Full declassified text.",
        )
        story = Story(document=document, summary="A radar contact goes unexplained.")
        chapter = Chapter(
            story=story,
            chapter_index=1,
            title="Parte 1",
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
                    status=ApprovalStatus.PENDING_REVIEW,
                )
            )
        session.commit()
        return chapter.id


def test_full_workflow_from_curated_document_to_playable_video(
    client, engine, externals, tmp_path
):
    """15.1: document -> script approval -> subtitles -> video -> playback."""
    chapter_id = seed_chapter(engine)

    # The chapter appears in the script queue, unapproved.
    queue = client.get("/chapters/pending/scripts").json()
    assert [row["id"] for row in queue] == [chapter_id]
    assert queue[0]["script_approved"] is False

    # Video is refused before approval.
    blocked = client.post(f"/chapters/{chapter_id}/video/generate")
    assert blocked.status_code == 409

    # Approve the script.
    approved = client.post(f"/chapters/{chapter_id}/script/approve")
    assert approved.status_code == 200
    assert approved.json()["platform_versions_updated"] == 4

    # Subtitles generate in both languages.
    tracks = client.post(f"/chapters/{chapter_id}/subtitles/generate").json()
    assert {track["lang"] for track in tracks} == {"es", "en"}
    assert all(track["segments"] for track in tracks)

    # Video generation returns pending rows and completes in the background.
    created = client.post(
        f"/chapters/{chapter_id}/video/generate", json={"platforms": ["tiktok"]}
    )
    assert created.status_code == 202
    assert [row["status"] for row in created.json()] == ["pending"]

    videos = client.get(f"/chapters/{chapter_id}/video").json()
    assert len(videos) == 1
    assert videos[0]["status"] == "generated"
    assert videos[0]["size_mb"] > 0

    # The produced file is actually servable over HTTP.
    playback = client.get(f"/videos/{videos[0]['id']}/file")
    assert playback.status_code == 200
    assert playback.headers["content-type"] == "video/mp4"

    # And it shows up in the library with its chapter context.
    library = client.get("/videos").json()
    assert library[0]["chapter_title"] == "Parte 1"


def test_video_generation_succeeds_once_the_script_is_approved(client, engine):
    """15.2: the approval gate is the only thing standing in the way."""
    chapter_id = seed_chapter(engine)

    assert client.post(f"/chapters/{chapter_id}/video/generate").status_code == 409

    client.post(f"/chapters/{chapter_id}/script/approve")
    assert (
        client.post(
            f"/chapters/{chapter_id}/video/generate", json={"platforms": ["tiktok"]}
        ).status_code
        == 202
    )

    videos = client.get(f"/chapters/{chapter_id}/video").json()
    assert videos[0]["status"] == "generated"


def test_editing_a_script_after_approval_reblocks_video_generation(client, engine):
    """15.3: the reset is not cosmetic — it re-closes the gate."""
    chapter_id = seed_chapter(engine)
    client.post(f"/chapters/{chapter_id}/script/approve")

    updated = client.post(
        f"/chapters/{chapter_id}/script/update",
        json={"script_text": "Un guion corregido después de la aprobación."},
    )
    assert updated.status_code == 200
    assert updated.json()["script_approved"] is False

    assert client.post(f"/chapters/{chapter_id}/video/generate").status_code == 409
    assert client.post(f"/chapters/{chapter_id}/subtitles/generate").status_code == 409


def test_retry_reuses_cached_audio_and_visuals(client, engine, externals):
    """15.4: a composition failure must not re-buy narration."""
    chapter_id = seed_chapter(engine)
    client.post(f"/chapters/{chapter_id}/script/approve")

    externals["compositor"].fail_next = True
    client.post(f"/chapters/{chapter_id}/video/generate", json={"platforms": ["tiktok"]})

    failed = client.get(f"/chapters/{chapter_id}/video").json()
    assert [row["status"] for row in failed] == ["failed"]
    assert "composition step failed" in failed[0]["error_message"]
    synth_after_failure = len(externals["tts"].synth_calls)
    searches_after_failure = len(externals["images"].searches)
    assert synth_after_failure == 1

    externals["compositor"].fail_next = False
    retried = client.post(f"/chapters/{chapter_id}/video/retry")
    assert retried.status_code == 202

    rows = client.get(f"/chapters/{chapter_id}/video").json()
    assert any(row["status"] == "generated" for row in rows)
    # The whole point of deterministic paths: no second TTS bill, no second
    # image fetch.
    assert len(externals["tts"].synth_calls) == synth_after_failure
    assert len(externals["images"].searches) == searches_after_failure


def test_edited_subtitles_reach_the_composited_video(client, engine, externals, tmp_path):
    """The correction an editor makes is what FFmpeg burns in."""
    chapter_id = seed_chapter(engine)
    client.post(f"/chapters/{chapter_id}/script/approve")
    tracks = client.post(f"/chapters/{chapter_id}/subtitles/generate").json()
    spanish = next(track for track in tracks if track["lang"] == "es")

    client.post(
        f"/chapters/{chapter_id}/subtitles/update",
        json={
            "lang": "es",
            "segments": [
                {"index": segment["index"], "text": "TEXTO CORREGIDO"}
                for segment in spanish["segments"]
            ],
        },
    )

    client.post(f"/chapters/{chapter_id}/video/generate", json={"platforms": ["tiktok"]})

    burned_in = Path(externals["compositor"].calls[-1]["subtitle_path"])
    assert "TEXTO CORREGIDO" in burned_in.read_text(encoding="utf-8")


def test_narration_is_synthesized_once_across_all_platforms(client, engine, externals):
    """Four platform videos, one language, one TTS bill."""
    chapter_id = seed_chapter(engine)
    client.post(f"/chapters/{chapter_id}/script/approve")

    client.post(f"/chapters/{chapter_id}/video/generate")

    videos = client.get(f"/chapters/{chapter_id}/video").json()
    assert len(videos) == 4
    assert all(row["status"] == "generated" for row in videos)
    assert len(externals["tts"].synth_calls) == 1


def test_deleting_one_platform_video_leaves_the_others_playable(client, engine):
    """Shared narration and captions must survive a single deletion."""
    chapter_id = seed_chapter(engine)
    client.post(f"/chapters/{chapter_id}/script/approve")
    client.post(f"/chapters/{chapter_id}/video/generate")

    videos = client.get(f"/chapters/{chapter_id}/video").json()
    assert len(videos) == 4

    assert client.delete(f"/videos/{videos[0]['id']}").status_code == 200

    for survivor in videos[1:]:
        assert client.get(f"/videos/{survivor['id']}/file").status_code == 200

    remaining = client.get(f"/chapters/{chapter_id}/video").json()
    assert len(remaining) == 3
    # The deleted attempt stays in the audit trail.
    audit = client.get(f"/chapters/{chapter_id}/audit").json()
    assert len(audit) == 4
    assert sum(1 for entry in audit if entry["deleted_at"]) == 1


def test_tts_failure_is_reported_and_retryable(client, engine, externals):
    """A quota failure surfaces on the row and does not poison later runs."""
    chapter_id = seed_chapter(engine)
    client.post(f"/chapters/{chapter_id}/script/approve")

    externals["tts"].fail_next = True
    client.post(f"/chapters/{chapter_id}/video/generate", json={"platforms": ["tiktok"]})

    failed = client.get(f"/chapters/{chapter_id}/video").json()
    assert failed[0]["status"] == "failed"
    assert "tts step failed" in failed[0]["error_message"]

    externals["tts"].fail_next = False
    assert client.post(f"/chapters/{chapter_id}/video/retry").status_code == 202
    assert any(
        row["status"] == "generated"
        for row in client.get(f"/chapters/{chapter_id}/video").json()
    )


def test_duplicate_generation_is_refused(client, engine):
    """Two live attempts would write the same MP4 concurrently."""
    chapter_id = seed_chapter(engine)
    client.post(f"/chapters/{chapter_id}/script/approve")
    client.post(f"/chapters/{chapter_id}/video/generate", json={"platforms": ["tiktok"]})

    duplicate = client.post(
        f"/chapters/{chapter_id}/video/generate", json={"platforms": ["tiktok"]}
    )

    assert duplicate.status_code == 409
    with Session(engine) as session:
        assert session.query(VideoGeneration).count() == 1


def test_stats_reflect_generated_videos(client, engine):
    chapter_id = seed_chapter(engine)
    client.post(f"/chapters/{chapter_id}/script/approve")
    client.post(f"/chapters/{chapter_id}/video/generate", json={"platforms": ["tiktok"]})

    stats = client.get("/videos/stats").json()

    assert stats["count_by_status"]["generated"] == 1
    assert stats["total_storage_mb"] > 0
    assert stats["missing_on_disk"] == 0
    assert stats["disk_free_mb"] is not None
