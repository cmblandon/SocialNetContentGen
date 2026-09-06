"""
Script review endpoints — specs/script-approval-workflow/spec.md.

Chapter-scoped rather than platform-version-scoped (unlike approval.py, which
gates publishing per platform version): the script is one shared text on the
Chapter, so one decision fans out to all of its platform versions. See
application/script_approval.py for why.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.editorial.application.script_approval import (
    ChapterNotFoundError,
    EmptyScriptError,
    NoPlatformVersionsError,
    approve_chapter_script,
    list_chapters_with_scripts,
    reject_chapter_script,
    update_chapter_script,
)
from src.editorial.infrastructure.persistence.session import get_session

router = APIRouter(tags=["script-approval"])


class ScriptUpdateRequest(BaseModel):
    script_text: str = Field(..., min_length=1, description="Replacement script text")


class ScriptApprovalResponse(BaseModel):
    chapter_id: str
    script_approved: bool
    script_approved_at: Optional[datetime]
    platform_versions_updated: int


class ChapterScriptResponse(BaseModel):
    id: str
    title: str
    script: str
    visual_notes: Optional[str]
    source_citation: str
    script_approved: bool
    script_approved_at: Optional[datetime]
    created_at: datetime
    word_count: int


@router.get("/chapters/pending/scripts", response_model=list[ChapterScriptResponse])
def list_pending_scripts(
    session: Session = Depends(get_session),
) -> list[ChapterScriptResponse]:
    """
    Chapters awaiting or holding script approval.

    Includes already-approved chapters so an editor can see and revisit a
    decision; a chapter drops out only once every platform version reaches a
    terminal state.
    """
    return [
        ChapterScriptResponse(**vars(summary))
        for summary in list_chapters_with_scripts(session)
    ]


@router.post("/chapters/{chapter_id}/script/approve", response_model=ScriptApprovalResponse)
def approve_script(
    chapter_id: str, session: Session = Depends(get_session)
) -> ScriptApprovalResponse:
    """
    Approve a chapter's script, unblocking subtitle and video generation.

    Writes the decision to every platform version of the chapter, since they
    share one script. Returns 409 for a chapter with no platform versions —
    there would be nowhere to record the approval.
    """
    try:
        outcome = approve_chapter_script(session, chapter_id)
    except ChapterNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except NoPlatformVersionsError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return ScriptApprovalResponse(**vars(outcome))


@router.post("/chapters/{chapter_id}/script/reject", response_model=ScriptApprovalResponse)
def reject_script(
    chapter_id: str, session: Session = Depends(get_session)
) -> ScriptApprovalResponse:
    """Withdraw approval, returning the chapter to the review queue."""
    try:
        outcome = reject_chapter_script(session, chapter_id)
    except ChapterNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return ScriptApprovalResponse(**vars(outcome))


@router.post("/chapters/{chapter_id}/script/update", response_model=ScriptApprovalResponse)
def update_script(
    chapter_id: str,
    request: ScriptUpdateRequest,
    session: Session = Depends(get_session),
) -> ScriptApprovalResponse:
    """
    Replace the script text.

    Always resets approval, including when the chapter is already approved:
    the narrated text must be text a human read. Blank text is rejected with
    422, since an empty script would produce a silent video.
    """
    try:
        outcome = update_chapter_script(session, chapter_id, request.script_text)
    except ChapterNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except EmptyScriptError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return ScriptApprovalResponse(**vars(outcome))
