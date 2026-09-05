"""
GET /publish-records — the read model the admin panel (Phase 6) will
consume for the editorial calendar view.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.editorial.infrastructure.persistence.models import PublishRecord
from src.editorial.infrastructure.persistence.session import get_session

router = APIRouter(tags=["publish-records"])


class PublishRecordResponse(BaseModel):
    id: str
    platform_version_id: str
    platform: str
    status: str
    external_post_id: Optional[str]
    scheduled_at: Optional[datetime]
    published_at: Optional[datetime]
    error_message: Optional[str]


@router.get("/publish-records", response_model=list[PublishRecordResponse])
def list_publish_records(session: Session = Depends(get_session)) -> list[PublishRecordResponse]:
    records = session.execute(select(PublishRecord)).scalars().all()
    return [
        PublishRecordResponse(
            id=record.id,
            platform_version_id=record.platform_version_id,
            platform=record.platform_version.platform.value,
            status=record.status.value,
            external_post_id=record.external_post_id,
            scheduled_at=record.scheduled_at,
            published_at=record.published_at,
            error_message=record.error_message,
        )
        for record in records
    ]
