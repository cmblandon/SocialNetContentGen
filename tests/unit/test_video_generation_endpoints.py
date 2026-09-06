"""
Tests for the video generation endpoints — specs/video-generation-from-script.

Generation is asynchronous: the POST must persist PENDING rows and return
before composition runs. TestClient executes BackgroundTasks synchronously on
response, so "did the background work run" is observable by reading the rows
back afterwards.

The load-bearing behaviours: the approval gate rejects before creating any
row, and a background crash can never strand a row at PENDING — a status the
admin panel polls forever.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.editorial.application.subtitle_generation_use_case import (
    SubtitleGenerationUseCase,
)
from src.editorial.application.video_generation_use_case import VideoGenerationUseCase
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
from src.editorial.presentation.dependencies import get_video_generation_use_case

CHAPTER_SCRIPT = "Primera frase del guion. Segunda frase del guion."


class FakeTTSClient:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def generate_speech(self, text: str, language: str, output_path: str) -> int:
        self.calls.append((text, language))
        if self.error:
            raise self.error
        with open(output_path, "wb") as f:
            f.write(b"fake-audio")
        return 4000

    def get_audio_duration(self, audio_path: str) -> int:
        return 4000


class FakeImageClient:
    def search_image(self, query: str):
        return None

    def download_image(self, url: str, output_path: str) -> None:
        pass

    def create_fallback_image(self, text: str, output_path: str) -> None:
        with open(output_path, "wb") as f:
            f.write(b"fake-image")


class FakeCompositor:
    def composite(
        self, audio_path, visual_path, subtitle_path, output_path, duration_seconds=None
    ) -> None:
        with open(output_path, "wb") as f:
            f.write(b"fake-video" * 1000)


class FakeLLMClient:
    def complete(self, prompt: str) -> str:
        return "First sentence. Second sentence."


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
def use_case(tts, tmp_path):
    return VideoGenerationUseCase(
        tts_client=tts,
        image_client=FakeImageClient(),
        compositor=FakeCompositor(),
        subtitle_use_case=SubtitleGenerationUseCase(
            FakeLLMClient(), cache_dir=tmp_path / "cache"
        ),
        subtitle_store=SubtitleStore(
            subtitle_root=tmp_path / "subtitles", audio_root=tmp_path / "audio"
        ),
        video_root=tmp_path / "videos_generated",
    )


@pytest.fixture
def client(test_engine, use_case):
    TestSessionLocal = sessionmaker(bind=test_engine)

    def override_get_session():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    # Background work needs its own session against the same in-memory engine.
    app.dependency_overrides[get_session_factory] = lambda: TestSessionLocal
    app.dependency_overrides[get_video_generation_use_case] = lambda: use_case
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
            visual_notes="archival radar footage",
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


def _records(engine) -> list[VideoGeneration]:
    with Session(engine) as session:
        return list(session.query(VideoGeneration).all())


def test_generate_returns_202_with_pending_rows(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)

    response = client.post(f"/chapters/{chapter_id}/video/generate")

    assert response.status_code == 202
    body = response.json()
    # One row per platform, Spanish only by default.
    assert len(body) == 4
    assert {row["language"] for row in body} == {"es"}
    assert {row["platform"] for row in body} == {p.value for p in PlatformName}
    # The response reflects the state at submission time, before composition.
    assert all(row["status"] == "pending" for row in body)
    assert all(row["video_file_path"] is None for row in body)


def test_generate_runs_composition_in_the_background(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)

    client.post(f"/chapters/{chapter_id}/video/generate")

    records = _records(test_engine)
    assert len(records) == 4
    assert all(r.status == VideoGenerationStatus.GENERATED for r in records)
    assert all(r.video_file_path is not None for r in records)


def test_generate_rejects_unapproved_script_with_409(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=False)

    response = client.post(f"/chapters/{chapter_id}/video/generate")

    assert response.status_code == 409
    assert "approved" in response.json()["detail"].lower()
    assert _records(test_engine) == [], "a rejected request must create no rows"


def test_generate_unknown_chapter_returns_404(client):
    assert client.post("/chapters/no-such-id/video/generate").status_code == 404


def test_generate_honours_requested_platforms_and_languages(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)

    response = client.post(
        f"/chapters/{chapter_id}/video/generate",
        json={"platforms": ["tiktok"], "languages": ["es", "en"]},
    )

    body = response.json()
    assert len(body) == 2
    assert {row["platform"] for row in body} == {"tiktok"}
    assert {row["language"] for row in body} == {"es", "en"}


def test_generate_rejects_unsupported_language(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)

    response = client.post(
        f"/chapters/{chapter_id}/video/generate", json={"languages": ["fr"]}
    )

    assert response.status_code == 422
    assert _records(test_engine) == []


def test_generate_rejects_unknown_platform(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)

    response = client.post(
        f"/chapters/{chapter_id}/video/generate", json={"platforms": ["myspace"]}
    )

    assert response.status_code == 422
    assert _records(test_engine) == []


def test_background_failure_marks_row_failed_not_pending(test_engine, tmp_path):
    """A crash in the task must not strand the row at PENDING forever."""
    TestSessionLocal = sessionmaker(bind=test_engine)
    failing_use_case = VideoGenerationUseCase(
        tts_client=FakeTTSClient(error=RuntimeError("quota exceeded")),
        image_client=FakeImageClient(),
        compositor=FakeCompositor(),
        subtitle_use_case=SubtitleGenerationUseCase(
            FakeLLMClient(), cache_dir=tmp_path / "cache"
        ),
        subtitle_store=SubtitleStore(
            subtitle_root=tmp_path / "subtitles", audio_root=tmp_path / "audio"
        ),
        video_root=tmp_path / "videos_generated",
    )

    def override_get_session():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_session_factory] = lambda: TestSessionLocal
    app.dependency_overrides[get_video_generation_use_case] = lambda: failing_use_case
    try:
        client = TestClient(app)
        chapter_id = _seed_chapter(test_engine, script_approved=True)
        client.post(f"/chapters/{chapter_id}/video/generate")
    finally:
        app.dependency_overrides.clear()

    records = _records(test_engine)
    assert records
    assert all(r.status == VideoGenerationStatus.FAILED for r in records)
    assert all("tts" in (r.error_message or "") for r in records)


def test_run_pending_refuses_a_row_that_already_ran(client, test_engine, use_case):
    """Guards against a duplicate task redoing paid work."""
    chapter_id = _seed_chapter(test_engine, script_approved=True)
    client.post(f"/chapters/{chapter_id}/video/generate")
    generated = _records(test_engine)[0]

    with Session(test_engine) as session:
        with pytest.raises(ValueError, match="not 'pending'"):
            use_case.run_pending(session, generated.id)


def test_get_video_returns_metadata_with_size(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)
    client.post(f"/chapters/{chapter_id}/video/generate")

    response = client.get(f"/chapters/{chapter_id}/video")

    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 4
    row = rows[0]
    assert row["status"] == "generated"
    assert row["video_file_path"].endswith(".mp4")
    assert row["generated_at"] is not None
    assert row["size_mb"] is not None and row["size_mb"] > 0
    assert row["platform"] in {p.value for p in PlatformName}


def test_get_video_is_empty_before_generation(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)

    assert client.get(f"/chapters/{chapter_id}/video").json() == []


def test_get_video_unknown_chapter_returns_404(client):
    assert client.get("/chapters/no-such-id/video").status_code == 404


def test_size_is_null_when_the_file_is_missing(client, test_engine, tmp_path):
    """None, not 0 — 'file gone' must be distinguishable from 'empty file'."""
    chapter_id = _seed_chapter(test_engine, script_approved=True)
    client.post(f"/chapters/{chapter_id}/video/generate")

    for path in (tmp_path / "videos_generated").rglob("*.mp4"):
        path.unlink()

    rows = client.get(f"/chapters/{chapter_id}/video").json()
    assert all(row["size_mb"] is None for row in rows)


def test_retry_creates_linked_attempts_for_failed_rows(test_engine, tmp_path):
    TestSessionLocal = sessionmaker(bind=test_engine)
    tts = FakeTTSClient(error=RuntimeError("quota exceeded"))
    flaky_use_case = VideoGenerationUseCase(
        tts_client=tts,
        image_client=FakeImageClient(),
        compositor=FakeCompositor(),
        subtitle_use_case=SubtitleGenerationUseCase(
            FakeLLMClient(), cache_dir=tmp_path / "cache"
        ),
        subtitle_store=SubtitleStore(
            subtitle_root=tmp_path / "subtitles", audio_root=tmp_path / "audio"
        ),
        video_root=tmp_path / "videos_generated",
    )

    def override_get_session():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_session_factory] = lambda: TestSessionLocal
    app.dependency_overrides[get_video_generation_use_case] = lambda: flaky_use_case
    try:
        client = TestClient(app)
        chapter_id = _seed_chapter(test_engine, script_approved=True)
        client.post(
            f"/chapters/{chapter_id}/video/generate", json={"platforms": ["tiktok"]}
        )
        failed = _records(test_engine)
        assert len(failed) == 1

        tts.error = None  # the transient failure clears
        response = client.post(f"/chapters/{chapter_id}/video/retry")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    retries = response.json()
    assert len(retries) == 1
    assert retries[0]["retry_of_id"] == failed[0].id

    records = _records(test_engine)
    assert len(records) == 2
    assert any(r.status == VideoGenerationStatus.GENERATED for r in records)


def test_retry_without_failures_returns_409(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)
    client.post(f"/chapters/{chapter_id}/video/generate")

    response = client.post(f"/chapters/{chapter_id}/video/retry")

    assert response.status_code == 409
    assert "no failed" in response.json()["detail"].lower()


def test_retry_unknown_generation_id_returns_404(client, test_engine):
    chapter_id = _seed_chapter(test_engine, script_approved=True)
    client.post(f"/chapters/{chapter_id}/video/generate")

    response = client.post(
        f"/chapters/{chapter_id}/video/retry",
        json={"video_generation_id": "no-such-id"},
    )

    assert response.status_code == 404


def test_retry_unknown_chapter_returns_404(client):
    assert client.post("/chapters/no-such-id/video/retry").status_code == 404
