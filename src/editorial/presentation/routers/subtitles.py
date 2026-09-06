"""
Subtitle review endpoints — specs/subtitle-generation-and-approval/spec.md.

Chapter-scoped like the script endpoints: captions derive from the chapter's
script and a language, never from the platform, so one track per language
serves all of a chapter's platform videos.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.editorial.application.script_approval import ChapterNotFoundError
from src.editorial.application.subtitle_review_use_case import (
    ScriptNotApprovedError,
    SegmentCountMismatchError,
    SubtitleReviewUseCase,
    SubtitleSegmentEdit,
    SubtitlesNotGeneratedError,
)
from src.editorial.infrastructure.persistence.subtitle_store import StoredSubtitle
from src.editorial.infrastructure.persistence.session import get_session
from src.editorial.presentation.dependencies import get_subtitle_review_use_case

router = APIRouter(tags=["subtitles"])


class SubtitleSegmentResponse(BaseModel):
    index: int
    start: str
    end: str
    text: str


class SubtitleTrackResponse(BaseModel):
    lang: str
    edited: bool
    updated_at: Optional[datetime]
    segments: list[SubtitleSegmentResponse]


class SubtitleSegmentEditRequest(BaseModel):
    index: int
    text: str = Field(..., min_length=1)


class SubtitleUpdateRequest(BaseModel):
    lang: str
    segments: list[SubtitleSegmentEditRequest] = Field(..., min_length=1)


def _to_response(track: StoredSubtitle) -> SubtitleTrackResponse:
    return SubtitleTrackResponse(
        lang=track.language,
        edited=track.edited,
        updated_at=track.updated_at,
        segments=[
            SubtitleSegmentResponse(
                index=line.index,
                start=line.start_time,
                end=line.end_time,
                text=line.text,
            )
            for line in track.draft.subtitle_lines
        ],
    )


@router.post(
    "/chapters/{chapter_id}/subtitles/generate",
    response_model=list[SubtitleTrackResponse],
)
def generate_subtitles(
    chapter_id: str,
    session: Session = Depends(get_session),
    use_case: SubtitleReviewUseCase = Depends(get_subtitle_review_use_case),
) -> list[SubtitleTrackResponse]:
    """
    Generate Spanish and English subtitle tracks.

    Timing is measured from the synthesized narration, not estimated. Returns
    409 unless the script is approved. Already-generated tracks are returned
    untouched, so calling twice cannot discard an editor's corrections.
    """
    try:
        tracks = use_case.generate(session, chapter_id)
    except ChapterNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ScriptNotApprovedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return [_to_response(track) for track in tracks]


@router.get("/chapters/{chapter_id}/subtitles", response_model=list[SubtitleTrackResponse])
def get_subtitles(
    chapter_id: str,
    session: Session = Depends(get_session),
    use_case: SubtitleReviewUseCase = Depends(get_subtitle_review_use_case),
) -> list[SubtitleTrackResponse]:
    """Stored subtitle tracks; an empty list before generation."""
    try:
        tracks = use_case.get(session, chapter_id)
    except ChapterNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return [_to_response(track) for track in tracks]


@router.post(
    "/chapters/{chapter_id}/subtitles/update", response_model=SubtitleTrackResponse
)
def update_subtitles(
    chapter_id: str,
    request: SubtitleUpdateRequest,
    session: Session = Depends(get_session),
    use_case: SubtitleReviewUseCase = Depends(get_subtitle_review_use_case),
) -> SubtitleTrackResponse:
    """
    Replace segment text, preserving timing.

    Segments are matched by index and the count must equal the stored
    track's, so timing cannot drift from the audio it was measured against.
    A mismatch or blank text is a 422.
    """
    try:
        track = use_case.update(
            session,
            chapter_id,
            request.lang,
            [
                SubtitleSegmentEdit(index=segment.index, text=segment.text)
                for segment in request.segments
            ],
        )
    except ChapterNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except SubtitlesNotGeneratedError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (SegmentCountMismatchError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _to_response(track)
