"""
The editorial orchestrator's cycle logic — per specs/editorial-orchestration/
spec.md. Ties together readiness-checking, delegation to the writer/
platform-adapter use cases, persistence behind the approval gate, project-
memory bookkeeping, and the end-of-cycle summary.

Delegation to the LLM-driven deep agent graph (orchestrator_agents.py) and
this deterministic cycle logic are deliberately separate: judgment calls
(is this angle strong? is this script good?) belong to the agent; the
mechanically-checkable bookkeeping here does not need an LLM in the loop
and must behave identically every time (design.md Decision 6).
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from src.editorial.application.approval_gate import persist_story
from src.editorial.application.case_curation_use_case import CaseCurationUseCase
from src.editorial.application.platform_adaptation_use_case import (
    PlatformAdaptationUseCase,
)
from src.editorial.application.research_agent_use_case import ResearchAgentUseCase
from src.editorial.application.story_writing_use_case import StoryWritingUseCase
from src.editorial.core.ports import ScrapedDocument
from src.editorial.infrastructure.persistence.discovered_documents_repo import (
    create_pending_checkpoint,
    find_checkpoints_by_status,
    mark_checkpoint_advanced,
    mark_checkpoint_discarded,
    mark_checkpoint_failed,
)
from src.editorial.infrastructure.persistence.models import CurationStatus, DiscoveredDocument, Document
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore

MIN_EXTRACTED_TEXT_WORDS = 20


class DocumentNotReadyError(Exception):
    """Raised when a document is ambiguous, incomplete, or its official
    origin can't be verified — per specs/editorial-orchestration/spec.md,
    such a document must be discarded or escalated, never written from."""


def ensure_document_is_ready_for_writing(document: Document) -> None:
    if not document.agency or not document.agency.strip():
        raise DocumentNotReadyError(
            f"Document {document.id} has no verifiable issuing agency."
        )
    if not document.doc_type or not document.doc_type.strip():
        raise DocumentNotReadyError(f"Document {document.id} has no document type.")
    if len((document.extracted_text or "").split()) < MIN_EXTRACTED_TEXT_WORDS:
        raise DocumentNotReadyError(
            f"Document {document.id} has insufficient extracted text "
            f"(fewer than {MIN_EXTRACTED_TEXT_WORDS} words) to write from responsibly."
        )


@dataclass
class CycleSummary:
    documents_reviewed: int = 0
    stories_created: int = 0
    chapters_generated: int = 0
    pending_approval_platform_version_ids: list[str] = field(default_factory=list)
    discarded_document_ids: list[str] = field(default_factory=list)

    def merge(self, other: "CycleSummary") -> "CycleSummary":
        """Accumulates another CycleSummary into this one in place — used
        when run_cycle is invoked once per advancing document (design.md
        Decision 2) instead of once per batch, so the caller-visible total
        is still a single CycleSummary."""
        self.documents_reviewed += other.documents_reviewed
        self.stories_created += other.stories_created
        self.chapters_generated += other.chapters_generated
        self.pending_approval_platform_version_ids.extend(other.pending_approval_platform_version_ids)
        self.discarded_document_ids.extend(other.discarded_document_ids)
        return self


def run_cycle(
    session: Session,
    documents_with_angles: list[tuple[Document, str]],
    story_writing_use_case: StoryWritingUseCase,
    platform_adaptation_use_case: PlatformAdaptationUseCase,
    memory_store: ProjectMemoryStore,
) -> CycleSummary:
    summary = CycleSummary()
    today = date.today().isoformat()

    for document, narrative_angle in documents_with_angles:
        summary.documents_reviewed += 1

        try:
            ensure_document_is_ready_for_writing(document)
        except DocumentNotReadyError as error:
            summary.discarded_document_ids.append(document.id)
            memory_store.append_caso_cubierto(
                f"{today} | {document.id} | discarded | {error}"
            )
            continue

        story_draft = story_writing_use_case.write_story(
            document_text=document.extracted_text,
            agency=document.agency,
            doc_type=document.doc_type,
            published_date=document.published_date,
            narrative_angle=narrative_angle,
        )
        summary.stories_created += 1
        summary.chapters_generated += len(story_draft.chapters)

        platform_adaptations_by_chapter = [
            platform_adaptation_use_case.adapt_chapter(
                script=chapter.script, source_citation=chapter.source_citation
            )
            for chapter in story_draft.chapters
        ]

        story = persist_story(
            session, document, story_draft, platform_adaptations_by_chapter
        )
        for chapter in story.chapters:
            for platform_version in chapter.platform_versions:
                summary.pending_approval_platform_version_ids.append(platform_version.id)

        memory_store.append_caso_cubierto(
            f"{today} | {document.id} | advanced | story generated, "
            f"{len(story_draft.chapters)} chapter(s) pending approval"
        )

    return summary


def _process_checkpointed_document(
    session: Session,
    scraped_document: ScrapedDocument,
    checkpoint: DiscoveredDocument,
    case_curation: CaseCurationUseCase,
    story_writing_use_case: StoryWritingUseCase,
    platform_adaptation_use_case: PlatformAdaptationUseCase,
    memory_store: ProjectMemoryStore,
) -> CycleSummary:
    """
    Curates one already-checkpointed document and, if it advances, writes/
    adapts/persists it IMMEDIATELY via a single-element run_cycle call —
    research-pipeline-checkpointing design.md Decision 2. Shared by
    run_research_cycle (fresh discovery) and run_resume_cycle (reprocessing
    PENDING/FAILED checkpoints with no scraping involved), so the two entry
    points can't drift apart.

    Any exception from case_curation.curate() (LLM error, network failure,
    a deliberately-raised CurationError for malformed output, etc.) is
    caught here and isolates this one document — it does not propagate to
    the caller, and does not stop the remaining documents in the same
    batch from being processed.
    """
    try:
        curation_result = case_curation.curate(scraped_document)
    except Exception as error:  # noqa: BLE001 - intentionally broad: ANY
        # curation-stage failure must be isolated per document, not just
        # the specific exception types CaseCurationUseCase happens to
        # raise today (an unguarded LLM client call can raise anything,
        # e.g. anthropic.BadRequestError).
        mark_checkpoint_failed(session, checkpoint, str(error))
        return CycleSummary()

    if curation_result is None or not curation_result.advanced:
        # None: already evaluated previously (casos_cubiertos.md dedup,
        # done inside curate() before it ever calls the LLM) — treated the
        # same as an explicit discard: a final, non-retryable outcome.
        mark_checkpoint_discarded(session, checkpoint)
        return CycleSummary()

    document = Document(
        title=scraped_document.title,
        agency=scraped_document.agency,
        doc_type=scraped_document.doc_type,
        published_date=scraped_document.published_date,
        source_url=scraped_document.source_url,
        extracted_text=scraped_document.extracted_text,
        extraction_confidence=scraped_document.extraction_confidence,
    )
    session.add(document)
    session.commit()

    summary = run_cycle(
        session=session,
        documents_with_angles=[(document, curation_result.narrative_angle)],
        story_writing_use_case=story_writing_use_case,
        platform_adaptation_use_case=platform_adaptation_use_case,
        memory_store=memory_store,
    )

    mark_checkpoint_advanced(
        session, checkpoint, document_id=document.id, narrative_angle=curation_result.narrative_angle
    )

    return summary


def run_research_cycle(
    session: Session,
    source_urls: list[str],
    research_agent: ResearchAgentUseCase,
    case_curation: CaseCurationUseCase,
    story_writing_use_case: StoryWritingUseCase,
    platform_adaptation_use_case: PlatformAdaptationUseCase,
    memory_store: ProjectMemoryStore,
    query: Optional[str] = None,
) -> CycleSummary:
    """
    Real input path (Phase 4): discover -> checkpoint -> curate -> (only
    advanced documents) write/adapt/persist, via the shared per-document
    helper (research-pipeline-checkpointing design.md Decision 2/3). Every
    document discover() returns is checkpointed as PENDING before curation
    is ever attempted, so a curation-stage failure never loses it — and one
    document's curation failure doesn't stop the rest of the batch (see
    _process_checkpointed_document). Source URLs already checkpointed as
    PENDING/FAILED from a previous run are skipped before discover() is
    even called, so a retried call with the same URLs doesn't re-scrape
    them (design.md Decision 4).

    research-query-scoping: `query` is forwarded unchanged to
    research_agent.discover() — this function has no opinion on what a
    query does or how scraper order is decided, that's entirely
    ResearchAgentUseCase's concern (see its module docstring).
    """
    non_terminal_checkpoints = find_checkpoints_by_status(
        session, [CurationStatus.PENDING, CurationStatus.FAILED]
    )
    already_checkpointed_urls = {
        checkpoint.source_url for checkpoint in non_terminal_checkpoints if checkpoint.source_url
    }
    urls_to_discover = [url for url in source_urls if url not in already_checkpointed_urls]

    research_result = research_agent.discover(urls_to_discover, query=query)

    summary = CycleSummary()
    for scraped_document in research_result.documents:
        checkpoint = create_pending_checkpoint(session, scraped_document)
        summary.merge(
            _process_checkpointed_document(
                session=session,
                scraped_document=scraped_document,
                checkpoint=checkpoint,
                case_curation=case_curation,
                story_writing_use_case=story_writing_use_case,
                platform_adaptation_use_case=platform_adaptation_use_case,
                memory_store=memory_store,
            )
        )

    return summary


def run_resume_cycle(
    session: Session,
    case_curation: CaseCurationUseCase,
    story_writing_use_case: StoryWritingUseCase,
    platform_adaptation_use_case: PlatformAdaptationUseCase,
    memory_store: ProjectMemoryStore,
) -> CycleSummary:
    """
    Reprocesses every checkpointed document still in a retryable state
    (PENDING or FAILED) through curation -> writing -> adaptation, with NO
    scraping involved at all — this is what lets an operator recover after
    fixing whatever broke (e.g. topping up LLM credit) without re-spending
    scraper calls (design.md Decision 3). Reuses the exact same
    per-document helper run_research_cycle uses, so the two entry points
    can't drift apart. Returns a zeroed CycleSummary, not an error, when
    nothing is pending/failed.
    """
    summary = CycleSummary()
    checkpoints = find_checkpoints_by_status(session, [CurationStatus.PENDING, CurationStatus.FAILED])

    for checkpoint in checkpoints:
        scraped_document = ScrapedDocument(
            title=checkpoint.title,
            agency=checkpoint.agency,
            doc_type=checkpoint.doc_type,
            extracted_text=checkpoint.extracted_text,
            published_date=checkpoint.published_date,
            source_url=checkpoint.source_url,
            extraction_confidence=checkpoint.extraction_confidence,
        )
        summary.merge(
            _process_checkpointed_document(
                session=session,
                scraped_document=scraped_document,
                checkpoint=checkpoint,
                case_curation=case_curation,
                story_writing_use_case=story_writing_use_case,
                platform_adaptation_use_case=platform_adaptation_use_case,
                memory_store=memory_store,
            )
        )

    return summary
