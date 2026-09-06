"""
Tests for the video library endpoints — specs/video-file-persistence/spec.md.

The load-bearing behaviours are around deletion: it must never remove the
narration audio or canonical subtitle track that a chapter's other platform
videos depend on, and it must never remove a per-platform file that a
surviving record still points at. Deletion is soft so the retry lineage the
audit trail reports stays intact.
"""
from datetime import datetime, timezone
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
from src.editorial.infrastructure.persistence.session import get_session
from src.editorial.presentation.app import app


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


@pytest.fixture
def media_root(tmp_path):
    """Stands in for data/, so no test ever touches the real tree."""
    return tmp_path


def _seed_chapter(engine) -> str:
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
            script="Guion.",
            visual_notes="radar",
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
                    script_approved=True,
                )
            )
        session.commit()
        return chapter.id


def _add_video(
    engine,
    chapter_id: str,
    *,
    platform: PlatformName = PlatformName.TIKTOK,
    language: str = "es",
    status: VideoGenerationStatus = VideoGenerationStatus.GENERATED,
    video_path: Path | None = None,
    subtitle_path: Path | None = None,
    size_bytes: int = 1024,
    retry_of_id: str | None = None,
) -> str:
    """Create a VideoGeneration row, writing real files so sizes are real."""
    if video_path is not None:
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"x" * size_bytes)
    if subtitle_path is not None:
        subtitle_path.parent.mkdir(parents=True, exist_ok=True)
        subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nhola")

    with Session(engine) as session:
        platform_version = (
            session.query(PlatformVersion)
            .filter_by(chapter_id=chapter_id, platform=platform)
            .one()
        )
        record = VideoGeneration(
            platform_version_id=platform_version.id,
            language=language,
            status=status,
            video_file_path=str(video_path) if video_path else None,
            subtitle_file_path=str(subtitle_path) if subtitle_path else None,
            retry_of_id=retry_of_id,
        )
        if status == VideoGenerationStatus.GENERATED:
            record.generated_at = datetime.now(timezone.utc)
        session.add(record)
        session.commit()
        return record.id


def _video_paths(media_root: Path, platform: str = "tiktok", language: str = "es"):
    base = media_root / "videos_generated" / platform / language
    return base / "chapter.mp4", base / "chapter.srt"


# --- GET /videos ------------------------------------------------------------


def test_list_videos_is_empty_initially(client):
    assert client.get("/videos").json() == []


def test_list_videos_returns_metadata(client, test_engine, media_root):
    chapter_id = _seed_chapter(test_engine)
    video, srt = _video_paths(media_root)
    _add_video(test_engine, chapter_id, video_path=video, subtitle_path=srt)

    rows = client.get("/videos").json()

    assert len(rows) == 1
    row = rows[0]
    assert row["chapter_id"] == chapter_id
    assert row["chapter_title"] == "Part 1"
    assert row["platform"] == "tiktok"
    assert row["language"] == "es"
    assert row["status"] == "generated"
    assert row["size_mb"] > 0


def test_list_videos_filters_by_status(client, test_engine, media_root):
    chapter_id = _seed_chapter(test_engine)
    video, _ = _video_paths(media_root)
    _add_video(test_engine, chapter_id, video_path=video)
    _add_video(
        test_engine,
        chapter_id,
        platform=PlatformName.INSTAGRAM,
        status=VideoGenerationStatus.FAILED,
    )

    assert len(client.get("/videos", params={"status": "generated"}).json()) == 1
    assert len(client.get("/videos", params={"status": "failed"}).json()) == 1
    assert len(client.get("/videos").json()) == 2


def test_list_videos_rejects_unknown_status(client):
    assert client.get("/videos", params={"status": "banana"}).status_code == 422


def test_list_videos_excludes_deleted(client, test_engine, media_root):
    chapter_id = _seed_chapter(test_engine)
    video, srt = _video_paths(media_root)
    video_id = _add_video(test_engine, chapter_id, video_path=video, subtitle_path=srt)

    client.delete(f"/videos/{video_id}")

    assert client.get("/videos").json() == []


# --- DELETE /videos/{id} ----------------------------------------------------


def test_delete_removes_files_and_marks_row_deleted(client, test_engine, media_root):
    chapter_id = _seed_chapter(test_engine)
    video, srt = _video_paths(media_root)
    video_id = _add_video(test_engine, chapter_id, video_path=video, subtitle_path=srt)

    response = client.delete(f"/videos/{video_id}")

    assert response.status_code == 200
    assert response.json()["video_file_deleted"] is True
    assert response.json()["subtitle_file_deleted"] is True
    assert not video.exists()
    assert not srt.exists()

    with Session(test_engine) as session:
        record = session.get(VideoGeneration, video_id)
        assert record is not None, "row must be retained, not removed"
        assert record.deleted_at is not None


def test_delete_never_touches_shared_audio_or_canonical_subtitles(
    client, test_engine, media_root
):
    """A chapter's other platform videos depend on these."""
    chapter_id = _seed_chapter(test_engine)
    video, srt = _video_paths(media_root)
    shared_audio = media_root / "audio" / chapter_id / "es.mp3"
    canonical_srt = media_root / "subtitles" / chapter_id / "es.srt"
    for path in (shared_audio, canonical_srt):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"shared")

    video_id = _add_video(test_engine, chapter_id, video_path=video, subtitle_path=srt)
    client.delete(f"/videos/{video_id}")

    assert shared_audio.exists(), "shared narration must survive"
    assert canonical_srt.exists(), "canonical subtitle track must survive"


def test_delete_retains_a_file_another_record_still_points_at(
    client, test_engine, media_root
):
    """Two rows can share a path — nothing stops generating twice for the same
    platform and language after a success."""
    chapter_id = _seed_chapter(test_engine)
    video, srt = _video_paths(media_root)
    first = _add_video(test_engine, chapter_id, video_path=video, subtitle_path=srt)
    _add_video(test_engine, chapter_id, video_path=video, subtitle_path=srt)

    response = client.delete(f"/videos/{first}")

    assert response.json()["video_file_deleted"] is False
    assert "still referenced" in response.json()["video_file_retained_reason"]
    assert video.exists(), "the surviving record still advertises this file"


def test_delete_preserves_retry_lineage(client, test_engine, media_root):
    chapter_id = _seed_chapter(test_engine)
    video, srt = _video_paths(media_root)
    original = _add_video(
        test_engine, chapter_id, status=VideoGenerationStatus.FAILED
    )
    retry = _add_video(
        test_engine,
        chapter_id,
        video_path=video,
        subtitle_path=srt,
        retry_of_id=original,
    )

    assert client.delete(f"/videos/{original}").status_code == 200

    with Session(test_engine) as session:
        assert session.get(VideoGeneration, retry).retry_of_id == original


def test_delete_is_idempotent_at_the_api_boundary(client, test_engine, media_root):
    chapter_id = _seed_chapter(test_engine)
    video, srt = _video_paths(media_root)
    video_id = _add_video(test_engine, chapter_id, video_path=video, subtitle_path=srt)

    assert client.delete(f"/videos/{video_id}").status_code == 200
    assert client.delete(f"/videos/{video_id}").status_code == 404


def test_delete_tolerates_a_file_already_gone(client, test_engine, media_root):
    chapter_id = _seed_chapter(test_engine)
    video, srt = _video_paths(media_root)
    video_id = _add_video(test_engine, chapter_id, video_path=video, subtitle_path=srt)
    video.unlink()

    response = client.delete(f"/videos/{video_id}")

    assert response.status_code == 200
    assert response.json()["video_file_deleted"] is False
    assert "already absent" in response.json()["video_file_retained_reason"]
    with Session(test_engine) as session:
        assert session.get(VideoGeneration, video_id).deleted_at is not None


def test_delete_unknown_id_returns_404(client):
    assert client.delete("/videos/no-such-id").status_code == 404


def test_deleted_video_is_hidden_from_chapter_video_listing(
    client, test_engine, media_root
):
    chapter_id = _seed_chapter(test_engine)
    video, srt = _video_paths(media_root)
    video_id = _add_video(test_engine, chapter_id, video_path=video, subtitle_path=srt)

    client.delete(f"/videos/{video_id}")

    assert client.get(f"/chapters/{chapter_id}/video").json() == []


# --- GET /videos/stats ------------------------------------------------------


def test_stats_on_an_empty_library(client):
    stats = client.get("/videos/stats").json()

    assert stats["total_storage_mb"] == 0
    assert stats["count_by_status"] == {"pending": 0, "generated": 0, "failed": 0}
    assert stats["largest_videos"] == []
    assert stats["missing_on_disk"] == 0


def test_stats_totals_and_counts(client, test_engine, media_root):
    chapter_id = _seed_chapter(test_engine)
    big, _ = _video_paths(media_root, platform="tiktok")
    small, _ = _video_paths(media_root, platform="instagram")
    _add_video(test_engine, chapter_id, video_path=big, size_bytes=2 * 1024 * 1024)
    _add_video(
        test_engine,
        chapter_id,
        platform=PlatformName.INSTAGRAM,
        video_path=small,
        size_bytes=1024 * 1024,
    )
    _add_video(
        test_engine,
        chapter_id,
        platform=PlatformName.X,
        status=VideoGenerationStatus.FAILED,
    )

    stats = client.get("/videos/stats").json()

    assert stats["count_by_status"] == {"pending": 0, "generated": 2, "failed": 1}
    assert stats["total_storage_mb"] == pytest.approx(3.0, abs=0.01)
    assert [v["platform"] for v in stats["largest_videos"]] == ["tiktok", "instagram"]


def test_stats_reports_files_missing_on_disk(client, test_engine, media_root):
    """DB counts and disk sizes can diverge; the gap is surfaced, not hidden."""
    chapter_id = _seed_chapter(test_engine)
    video, _ = _video_paths(media_root)
    _add_video(test_engine, chapter_id, video_path=video)
    video.unlink()

    stats = client.get("/videos/stats").json()

    assert stats["count_by_status"]["generated"] == 1
    assert stats["total_storage_mb"] == 0
    assert stats["missing_on_disk"] == 1


def test_stats_does_not_count_pending_rows_as_missing(client, test_engine):
    """A pending row legitimately has no file yet."""
    chapter_id = _seed_chapter(test_engine)
    _add_video(test_engine, chapter_id, status=VideoGenerationStatus.PENDING)

    assert client.get("/videos/stats").json()["missing_on_disk"] == 0


def test_stats_honours_largest_limit(client, test_engine, media_root):
    chapter_id = _seed_chapter(test_engine)
    for index, platform in enumerate(PlatformName, start=1):
        path, _ = _video_paths(media_root, platform=platform.value)
        _add_video(
            test_engine,
            chapter_id,
            platform=platform,
            video_path=path,
            size_bytes=index * 1024,
        )

    stats = client.get("/videos/stats", params={"largest_limit": 2}).json()

    assert len(stats["largest_videos"]) == 2


def test_stats_rejects_out_of_range_limit(client):
    assert client.get("/videos/stats", params={"largest_limit": 0}).status_code == 422
    assert client.get("/videos/stats", params={"largest_limit": 999}).status_code == 422


def test_stats_excludes_deleted_videos(client, test_engine, media_root):
    chapter_id = _seed_chapter(test_engine)
    video, srt = _video_paths(media_root)
    video_id = _add_video(
        test_engine, chapter_id, video_path=video, subtitle_path=srt, size_bytes=1024 * 1024
    )

    client.delete(f"/videos/{video_id}")
    stats = client.get("/videos/stats").json()

    assert stats["count_by_status"]["generated"] == 0
    assert stats["total_storage_mb"] == 0


# --- GET /chapters/{id}/audit -----------------------------------------------


def test_audit_lists_attempts_oldest_first(client, test_engine, media_root):
    chapter_id = _seed_chapter(test_engine)
    first = _add_video(test_engine, chapter_id, status=VideoGenerationStatus.FAILED)
    video, srt = _video_paths(media_root)
    second = _add_video(
        test_engine, chapter_id, video_path=video, subtitle_path=srt, retry_of_id=first
    )

    entries = client.get(f"/chapters/{chapter_id}/audit").json()

    assert [e["video_generation_id"] for e in entries] == [first, second]
    assert entries[1]["retry_of_id"] == first


def test_audit_exposes_timing_and_null_triggered_by(client, test_engine, media_root):
    """No authentication exists, so attribution is null by design, not omitted."""
    chapter_id = _seed_chapter(test_engine)
    video, srt = _video_paths(media_root)
    _add_video(test_engine, chapter_id, video_path=video, subtitle_path=srt)

    entry = client.get(f"/chapters/{chapter_id}/audit").json()[0]

    assert entry["triggered_by"] is None
    assert entry["triggered_at"] is not None
    assert entry["completed_at"] is not None


def test_audit_retains_deleted_attempts(client, test_engine, media_root):
    """An audit trail that dropped deleted work could not say what was made."""
    chapter_id = _seed_chapter(test_engine)
    video, srt = _video_paths(media_root)
    video_id = _add_video(test_engine, chapter_id, video_path=video, subtitle_path=srt)

    client.delete(f"/videos/{video_id}")
    entries = client.get(f"/chapters/{chapter_id}/audit").json()

    assert len(entries) == 1
    assert entries[0]["deleted_at"] is not None


def test_audit_reports_failure_reason(client, test_engine):
    chapter_id = _seed_chapter(test_engine)
    with Session(test_engine) as session:
        platform_version = (
            session.query(PlatformVersion)
            .filter_by(chapter_id=chapter_id, platform=PlatformName.TIKTOK)
            .one()
        )
        session.add(
            VideoGeneration(
                platform_version_id=platform_version.id,
                language="es",
                status=VideoGenerationStatus.FAILED,
                error_message="tts step failed: quota exceeded",
            )
        )
        session.commit()

    entry = client.get(f"/chapters/{chapter_id}/audit").json()[0]

    assert entry["status"] == "failed"
    assert "quota exceeded" in entry["error_message"]


def test_audit_is_empty_for_a_chapter_with_no_attempts(client, test_engine):
    chapter_id = _seed_chapter(test_engine)
    assert client.get(f"/chapters/{chapter_id}/audit").json() == []


def test_audit_unknown_chapter_returns_404(client):
    assert client.get("/chapters/no-such-id/audit").status_code == 404
