"""
Video library endpoints — specs/video-file-persistence/spec.md.

Library-wide rather than chapter-scoped: these serve storage management
(what exists, how much disk it uses, what to delete), not the per-chapter
editorial flow that /chapters/{id}/video covers.
"""
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.editorial.application.script_approval import ChapterNotFoundError
from src.editorial.application.video_management import (
    DEFAULT_LARGEST_LIMIT,
    MAX_LARGEST_LIMIT,
    VideoFileNotAvailableError,
    VideoFileOutsideRootError,
    VideoGenerationNotFoundError,
    delete_video,
    get_chapter_audit_trail,
    get_storage_stats,
    list_videos,
    resolve_playable_video_path,
)
from src.editorial.infrastructure.persistence.models import VideoGenerationStatus
from src.editorial.infrastructure.persistence.session import get_session
from src.editorial.presentation.dependencies import get_video_root

router = APIRouter(tags=["video-management"])


class VideoListItemResponse(BaseModel):
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


class VideoDeletionResponse(BaseModel):
    video_generation_id: str
    video_file_deleted: bool
    subtitle_file_deleted: bool
    video_file_retained_reason: Optional[str]
    subtitle_file_retained_reason: Optional[str]


class LargestVideoResponse(BaseModel):
    id: str
    chapter_id: str
    platform: str
    language: str
    size_mb: float
    video_file_path: str


class VideoStatsResponse(BaseModel):
    total_storage_mb: float
    count_by_status: dict[str, int]
    largest_videos: list[LargestVideoResponse]
    missing_on_disk: int
    disk_free_mb: Optional[float]
    disk_total_mb: Optional[float]


class AuditEntryResponse(BaseModel):
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


@router.get("/videos", response_model=list[VideoListItemResponse])
def list_all_videos(
    status: Optional[VideoGenerationStatus] = Query(
        default=None, description="Filter by generation status."
    ),
    session: Session = Depends(get_session),
) -> list[VideoListItemResponse]:
    """
    Every generated video, newest first, excluding deleted ones.

    Only `status` filters server-side; platform, language and date are the
    caller's to apply.
    """
    return [
        VideoListItemResponse(**vars(item)) for item in list_videos(session, status)
    ]


# Declared before /videos/{video_id} so the literal path is not captured by
# the path parameter.
@router.get("/videos/stats", response_model=VideoStatsResponse)
def video_stats(
    largest_limit: int = Query(
        default=DEFAULT_LARGEST_LIMIT, ge=1, le=MAX_LARGEST_LIMIT
    ),
    session: Session = Depends(get_session),
    video_root: Path = Depends(get_video_root),
) -> VideoStatsResponse:
    """
    Storage usage, counts by status, largest videos, and disk capacity.

    Counts come from the database and sizes from disk, so `missing_on_disk`
    reports rows marked generated whose file has vanished. Disk capacity is
    null, never 0, when it cannot be read.
    """
    stats = get_storage_stats(
        session, largest_limit=largest_limit, video_root=video_root
    )
    return VideoStatsResponse(
        total_storage_mb=stats.total_storage_mb,
        count_by_status=stats.count_by_status,
        largest_videos=[LargestVideoResponse(**vars(v)) for v in stats.largest_videos],
        missing_on_disk=stats.missing_on_disk,
        disk_free_mb=stats.disk_free_mb,
        disk_total_mb=stats.disk_total_mb,
    )


@router.get("/videos/{video_id}/file")
def download_video_file(
    video_id: str,
    session: Session = Depends(get_session),
    video_root: Path = Depends(get_video_root),
) -> FileResponse:
    """
    Serve the MP4 itself.

    The admin panel cannot play `video_file_path` directly — it is a path on
    the server's filesystem, not a URL. Starlette's FileResponse honours
    Range requests, so the player can seek without pulling the whole file.
    """
    try:
        path = resolve_playable_video_path(session, video_id, video_root)
    except (VideoGenerationNotFoundError, VideoFileNotAvailableError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except VideoFileOutsideRootError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error

    return FileResponse(path, media_type="video/mp4", filename=path.name)


@router.delete("/videos/{video_id}", response_model=VideoDeletionResponse)
def delete_one_video(
    video_id: str, session: Session = Depends(get_session)
) -> VideoDeletionResponse:
    """
    Delete a video's files and mark the record deleted.

    Soft delete: the row is retained so the retry lineage the audit trail
    reports stays intact. Shared narration and canonical subtitles are never
    removed, and a per-platform file is kept when another live record still
    points at it — the response says which and why.
    """
    try:
        outcome = delete_video(session, video_id)
    except VideoGenerationNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return VideoDeletionResponse(**vars(outcome))


@router.get("/chapters/{chapter_id}/audit", response_model=list[AuditEntryResponse])
def chapter_audit_trail(
    chapter_id: str, session: Session = Depends(get_session)
) -> list[AuditEntryResponse]:
    """
    Every generation attempt for a chapter, oldest first.

    Includes deleted attempts and retry lineage. `triggered_by` is always
    null: this service has no authentication, so no caller identity exists.
    """
    try:
        entries = get_chapter_audit_trail(session, chapter_id)
    except ChapterNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return [AuditEntryResponse(**vars(entry)) for entry in entries]
