"""
Approve/reject/publish endpoints. Per enhance-admin-panel-ui's design.md
Decision 1 (amending specs/editorial-orchestration/spec.md's original
"approving... proceeds to publishing" requirement): approve() only records
the approval decision — it no longer invokes PublishingUseCase. Publishing
is the separate, explicit publish() action below, gated the same way
PublishingUseCase.publish() always was (approval_gate.run_if_approved). If
no optimal_time is configured for the platform yet, publishing proposes one
and holds rather than publishing immediately (see PublishingUseCase) — that
is not treated as an error here.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.editorial.application.approval_gate import (
    AlreadyDecidedError,
    ApprovalRequiredError,
    approve_platform_version,
    reject_platform_version,
)
from src.editorial.application.publishing_use_case import PublishingUseCase
from src.editorial.infrastructure.persistence.models import PlatformVersion
from src.editorial.infrastructure.persistence.session import get_session
from src.editorial.presentation.dependencies import get_publishing_use_case

router = APIRouter(prefix="/platform-versions", tags=["approval"])


@router.post("/{platform_version_id}/approve")
def approve(platform_version_id: str, session: Session = Depends(get_session)) -> dict:
    _ensure_exists(session, platform_version_id)
    try:
        approve_platform_version(session, platform_version_id)
    except AlreadyDecidedError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"id": platform_version_id, "status": "approved"}


@router.post("/{platform_version_id}/publish")
def publish(
    platform_version_id: str,
    session: Session = Depends(get_session),
    publishing_use_case: PublishingUseCase = Depends(get_publishing_use_case),
) -> dict:
    _ensure_exists(session, platform_version_id)
    try:
        outcome = publishing_use_case.publish(session, platform_version_id)
    except ApprovalRequiredError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    return {
        "published": outcome.published,
        "external_post_id": outcome.external_post_id,
        "error_message": outcome.error_message,
        "proposed_time": outcome.proposed_time,
    }


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
