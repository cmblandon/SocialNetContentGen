"""
Approve/reject endpoints — the Phase 3 stand-in for the real admin panel
(Phase 6). Per specs/editorial-orchestration/spec.md: a human decision here
is what the (future) publisher's run_if_approved gate observes.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.editorial.application.approval_gate import (
    AlreadyDecidedError,
    approve_platform_version,
    reject_platform_version,
)
from src.editorial.infrastructure.persistence.models import PlatformVersion
from src.editorial.infrastructure.persistence.session import get_session

router = APIRouter(prefix="/platform-versions", tags=["approval"])


@router.post("/{platform_version_id}/approve")
def approve(platform_version_id: str, session: Session = Depends(get_session)) -> dict:
    _ensure_exists(session, platform_version_id)
    try:
        approve_platform_version(session, platform_version_id)
    except AlreadyDecidedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"id": platform_version_id, "status": "approved"}


@router.post("/{platform_version_id}/reject")
def reject(platform_version_id: str, session: Session = Depends(get_session)) -> dict:
    _ensure_exists(session, platform_version_id)
    try:
        reject_platform_version(session, platform_version_id)
    except AlreadyDecidedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"id": platform_version_id, "status": "rejected"}


def _ensure_exists(session: Session, platform_version_id: str) -> None:
    if session.get(PlatformVersion, platform_version_id) is None:
        raise HTTPException(status_code=404, detail="PlatformVersion not found")
