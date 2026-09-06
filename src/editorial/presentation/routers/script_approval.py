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
    return [
        ChapterScriptResponse(**vars(summary))
        for summary in list_chapters_with_scripts(session)
    ]


@router.post("/chapters/{chapter_id}/script/approve", response_model=ScriptApprovalResponse)
def approve_script(
    chapter_id: str, session: Session = Depends(get_session)
) -> ScriptApprovalResponse:
    try:
        outcome = approve_chapter_script(session, chapter_id)
    except ChapterNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return ScriptApprovalResponse(**vars(outcome))


@router.post("/chapters/{chapter_id}/script/reject", response_model=ScriptApprovalResponse)
def reject_script(
    chapter_id: str, session: Session = Depends(get_session)
) -> ScriptApprovalResponse:
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
    try:
        outcome = update_chapter_script(session, chapter_id, request.script_text)
    except ChapterNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except EmptyScriptError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return ScriptApprovalResponse(**vars(outcome))
