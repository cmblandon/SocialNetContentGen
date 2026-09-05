"""
GET /chapters/pending — supports the content-admin-panel Approval Queue
view (specs/content-admin-panel/spec.md): every pending item must show the
source Document, the Story summary, the Chapter script, and ALL
PlatformVersions for that chapter, not a subset. Not itemized as its own
task in tasks.md's Phase 6 — added because the queue view can't be built
without a read endpoint exposing this context.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.editorial.infrastructure.persistence.models import (
    ApprovalStatus,
    Chapter,
    PlatformVersion,
)
from src.editorial.infrastructure.persistence.session import get_session

router = APIRouter(tags=["chapters"])


class DocumentSummary(BaseModel):
    id: str
    title: str
    agency: str
    doc_type: str
    published_date: str | None
    source_url: str | None


class PlatformVersionSummary(BaseModel):
    id: str
    platform: str
    content: str
    status: str


class PendingChapterResponse(BaseModel):
    id: str
    title: str
    script: str
    visual_notes: str | None
    source_citation: str
    story_summary: str
    document: DocumentSummary
    platform_versions: list[PlatformVersionSummary]


@router.get("/chapters/pending", response_model=list[PendingChapterResponse])
def list_pending_chapters(session: Session = Depends(get_session)) -> list[PendingChapterResponse]:
    chapter_ids = (
        session.execute(
            select(Chapter.id)
            .join(PlatformVersion)
            .where(PlatformVersion.status == ApprovalStatus.PENDING_REVIEW)
            .distinct()
        )
        .scalars()
        .all()
    )

    responses = []
    for chapter_id in chapter_ids:
        chapter = session.get(Chapter, chapter_id)
        responses.append(
            PendingChapterResponse(
                id=chapter.id,
                title=chapter.title,
                script=chapter.script,
                visual_notes=chapter.visual_notes,
                source_citation=chapter.source_citation,
                story_summary=chapter.story.summary,
                document=DocumentSummary(
                    id=chapter.story.document.id,
                    title=chapter.story.document.title,
                    agency=chapter.story.document.agency,
                    doc_type=chapter.story.document.doc_type,
                    published_date=chapter.story.document.published_date,
                    source_url=chapter.story.document.source_url,
                ),
                platform_versions=[
                    PlatformVersionSummary(
                        id=pv.id,
                        platform=pv.platform.value,
                        content=pv.content,
                        status=pv.status.value,
                    )
                    for pv in chapter.platform_versions
                ],
            )
        )

    return responses
