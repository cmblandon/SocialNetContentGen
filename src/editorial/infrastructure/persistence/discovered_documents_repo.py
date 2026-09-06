"""
Persistence helpers for DiscoveredDocument checkpoints (research-pipeline-
checkpointing design.md Decision 1): every document research-agent
successfully scrapes is checkpointed here immediately, before curation is
ever attempted, so a downstream curation failure never loses what was
already scraped. Plain functions taking an explicit Session, matching this
codebase's existing style for persistence-adjacent orchestration helpers
(see approval_gate.py) rather than a class-based repository.
"""
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.editorial.core.ports import ScrapedDocument
from src.editorial.infrastructure.persistence.models import CurationStatus, DiscoveredDocument


def create_pending_checkpoint(session: Session, scraped_document: ScrapedDocument) -> DiscoveredDocument:
    """
    Persists scraped_document as a new PENDING checkpoint row. Always
    creates a new row — callers are expected to have already filtered out
    source URLs with an existing non-terminal checkpoint before calling
    discover() in the first place (see run_research_cycle's pre-filter),
    so a ScrapedDocument reaching here is new.
    """
    checkpoint = DiscoveredDocument(
        title=scraped_document.title,
        agency=scraped_document.agency,
        doc_type=scraped_document.doc_type,
        published_date=scraped_document.published_date,
        source_url=scraped_document.source_url,
        extracted_text=scraped_document.extracted_text,
        extraction_confidence=scraped_document.extraction_confidence,
        status=CurationStatus.PENDING,
    )
    session.add(checkpoint)
    session.commit()
    return checkpoint


def find_checkpoint_by_source_url(session: Session, source_url: Optional[str]) -> Optional[DiscoveredDocument]:
    if not source_url:
        return None
    return session.execute(
        select(DiscoveredDocument).where(DiscoveredDocument.source_url == source_url)
    ).scalars().first()


def find_checkpoints_by_status(
    session: Session, statuses: Sequence[CurationStatus]
) -> list[DiscoveredDocument]:
    return list(
        session.execute(
            select(DiscoveredDocument).where(DiscoveredDocument.status.in_(list(statuses)))
        ).scalars()
    )


def count_checkpoints_by_status(session: Session, status: CurationStatus) -> int:
    return session.execute(
        select(func.count()).select_from(DiscoveredDocument).where(DiscoveredDocument.status == status)
    ).scalar_one()


def mark_checkpoint_failed(session: Session, checkpoint: DiscoveredDocument, error_message: str) -> None:
    checkpoint.status = CurationStatus.FAILED
    checkpoint.error_message = error_message
    session.commit()


def mark_checkpoint_discarded(session: Session, checkpoint: DiscoveredDocument) -> None:
    checkpoint.status = CurationStatus.DISCARDED
    session.commit()


def mark_checkpoint_advanced(
    session: Session,
    checkpoint: DiscoveredDocument,
    document_id: str,
    narrative_angle: Optional[str],
) -> None:
    checkpoint.status = CurationStatus.ADVANCED
    checkpoint.document_id = document_id
    checkpoint.narrative_angle = narrative_angle
    session.commit()
