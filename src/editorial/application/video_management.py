"""
Video library management — listing, deletion, storage stats, and the audit
trail (specs/video-file-persistence/spec.md).

Free functions rather than a class because, unlike video generation, nothing
here has a swappable external collaborator to inject: the dependencies are
SQLAlchemy and the filesystem. Mirrors script_approval.py.

Deletion is soft. `retry_of_id` is a self-referential foreign key with no
cascade, so removing an attempt that other attempts reference would either
violate referential integrity or orphan the retry chain the audit trail is
required to report. The file goes; the row stays and is filtered from
listings.
"""
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.editorial.application.script_approval import ChapterNotFoundError
from src.editorial.infrastructure.persistence.models import (
    Chapter,
    PlatformVersion,
    VideoGeneration,
    VideoGenerationStatus,
)

DEFAULT_LARGEST_LIMIT = 10
MAX_LARGEST_LIMIT = 100


class VideoGenerationNotFoundError(Exception):
    """Raised when a video record does not exist, or has already been deleted."""


@dataclass
class VideoListItem:
    id: str
    chapter_id: str
    chapter_title: str
    platform_version_id: str
    platform: str
    language: str
    status: str
    video_file_path: Optional[str]
    subtitle_file_path: Optional[str]
    size_mb: Optional[float]
    error_message: Optional[str]
    retry_of_id: Optional[str]
    created_at: datetime
    generated_at: Optional[datetime]


@dataclass
class VideoDeletionOutcome:
    video_generation_id: str
    video_file_deleted: bool
    subtitle_file_deleted: bool
    video_file_retained_reason: Optional[str] = None
    subtitle_file_retained_reason: Optional[str] = None


@dataclass
class LargestVideoItem:
    id: str
    chapter_id: str
    platform: str
    language: str
    size_mb: float
    video_file_path: str


@dataclass
class VideoStorageStats:
    total_storage_mb: float
    count_by_status: dict[str, int]
    largest_videos: list[LargestVideoItem]
    missing_on_disk: int


@dataclass
class AuditEntry:
    video_generation_id: str
    platform: str
    language: str
    status: str
    triggered_by: Optional[str]
    triggered_at: datetime
    completed_at: Optional[datetime]
    deleted_at: Optional[datetime]
    retry_of_id: Optional[str]
    error_message: Optional[str]


def file_size_mb(path: Optional[str]) -> Optional[float]:
    """
    Size on disk, or None when there is no readable file.

    None rather than 0.0 so a caller can distinguish "never generated" and
    "file is gone" from "generated an empty file".
    """
    if not path:
        return None
    try:
        return round(os.path.getsize(path) / (1024 * 1024), 3)
    except OSError:
        return None


def list_videos(
    session: Session, status: Optional[VideoGenerationStatus] = None
) -> list[VideoListItem]:
    """Newest first. Soft-deleted records are excluded; the audit trail keeps them."""
    query = (
        select(VideoGeneration)
        .where(VideoGeneration.deleted_at.is_(None))
        .order_by(VideoGeneration.created_at.desc())
    )
    if status is not None:
        query = query.where(VideoGeneration.status == status)

    return [_to_list_item(record) for record in session.execute(query).scalars().all()]


def delete_video(session: Session, video_generation_id: str) -> VideoDeletionOutcome:
    """
    Remove a video's files and mark its record deleted.

    Only the paths recorded on this row are touched, and both point inside
    `data/videos_generated/`. The shared narration audio and canonical
    subtitle track live under `data/audio/` and `data/subtitles/` and are
    never referenced here, so a chapter's other platform videos cannot be
    broken by this call.
    """
    record = session.get(VideoGeneration, video_generation_id)
    if record is None or record.deleted_at is not None:
        raise VideoGenerationNotFoundError(
            f"VideoGeneration {video_generation_id} does not exist or is already deleted."
        )

    video_deleted, video_reason = _remove_if_unshared(
        session, record, record.video_file_path, "video_file_path"
    )
    subtitle_deleted, subtitle_reason = _remove_if_unshared(
        session, record, record.subtitle_file_path, "subtitle_file_path"
    )

    record.deleted_at = datetime.now(timezone.utc)
    session.commit()

    return VideoDeletionOutcome(
        video_generation_id=record.id,
        video_file_deleted=video_deleted,
        subtitle_file_deleted=subtitle_deleted,
        video_file_retained_reason=video_reason,
        subtitle_file_retained_reason=subtitle_reason,
    )


def get_storage_stats(
    session: Session, largest_limit: int = DEFAULT_LARGEST_LIMIT
) -> VideoStorageStats:
    """
    Storage usage across non-deleted records.

    Counts come from the database and sizes from disk, so a file removed
    outside this API shows up as a record counted in `count_by_status` but
    contributing nothing to `total_storage_mb`. `missing_on_disk` surfaces
    that gap rather than leaving the two numbers quietly inconsistent.
    """
    largest_limit = max(1, min(largest_limit, MAX_LARGEST_LIMIT))

    records = (
        session.execute(
            select(VideoGeneration).where(VideoGeneration.deleted_at.is_(None))
        )
        .scalars()
        .all()
    )

    count_by_status = {status.value: 0 for status in VideoGenerationStatus}
    total_mb = 0.0
    missing_on_disk = 0
    sized: list[LargestVideoItem] = []

    for record in records:
        count_by_status[record.status.value] += 1
        path = record.video_file_path
        size = file_size_mb(path)

        if path is None or size is None:
            # Only a GENERATED record is expected to have a file; a pending or
            # failed one having none is normal, not a missing file.
            if record.status == VideoGenerationStatus.GENERATED:
                missing_on_disk += 1
            continue

        total_mb += size
        sized.append(
            LargestVideoItem(
                id=record.id,
                chapter_id=record.platform_version.chapter_id,
                platform=record.platform_version.platform.value,
                language=record.language,
                size_mb=size,
                video_file_path=path,
            )
        )

    sized.sort(key=lambda item: item.size_mb, reverse=True)

    return VideoStorageStats(
        total_storage_mb=round(total_mb, 3),
        count_by_status=count_by_status,
        largest_videos=sized[:largest_limit],
        missing_on_disk=missing_on_disk,
    )


def get_chapter_audit_trail(session: Session, chapter_id: str) -> list[AuditEntry]:
    """
    Every generation attempt for a chapter, oldest first.

    Includes soft-deleted attempts: an audit trail that hid deleted work
    could not answer what was produced. `triggered_by` is always None — this
    service has no authentication, so no caller identity exists to record.
    """
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise ChapterNotFoundError(f"Chapter {chapter_id} does not exist.")

    records = (
        session.execute(
            select(VideoGeneration)
            .join(PlatformVersion)
            .where(PlatformVersion.chapter_id == chapter_id)
            .order_by(VideoGeneration.created_at.asc())
        )
        .scalars()
        .all()
    )

    return [
        AuditEntry(
            video_generation_id=record.id,
            platform=record.platform_version.platform.value,
            language=record.language,
            status=record.status.value,
            triggered_by=None,
            triggered_at=record.created_at,
            completed_at=record.generated_at,
            deleted_at=record.deleted_at,
            retry_of_id=record.retry_of_id,
            error_message=record.error_message,
        )
        for record in records
    ]


def _remove_if_unshared(
    session: Session, record: VideoGeneration, path: Optional[str], column: str
) -> tuple[bool, Optional[str]]:
    """
    Unlink `path` unless another live record still points at it.

    Two records can hold the same path: nothing stops generating twice for the
    same platform and language, and a retry deliberately reuses the failed
    attempt's paths. Unlinking without this check would delete a file a
    surviving record still advertises as present.
    """
    if not path:
        return False, None

    sibling = session.execute(
        select(VideoGeneration.id)
        .where(
            VideoGeneration.id != record.id,
            VideoGeneration.deleted_at.is_(None),
            getattr(VideoGeneration, column) == path,
        )
        .limit(1)
    ).scalar_one_or_none()

    if sibling is not None:
        return False, f"still referenced by VideoGeneration {sibling}"

    try:
        os.remove(path)
    except FileNotFoundError:
        # Already gone: the record still gets marked deleted, since the goal
        # state (no file, row retired) is what the caller asked for.
        return False, "file was already absent"
    except OSError as error:
        return False, f"could not be removed: {error}"

    return True, None


def _to_list_item(record: VideoGeneration) -> VideoListItem:
    return VideoListItem(
        id=record.id,
        chapter_id=record.platform_version.chapter_id,
        chapter_title=record.platform_version.chapter.title,
        platform_version_id=record.platform_version_id,
        platform=record.platform_version.platform.value,
        language=record.language,
        status=record.status.value,
        video_file_path=record.video_file_path,
        subtitle_file_path=record.subtitle_file_path,
        size_mb=file_size_mb(record.video_file_path),
        error_message=record.error_message,
        retry_of_id=record.retry_of_id,
        created_at=record.created_at,
        generated_at=record.generated_at,
    )
