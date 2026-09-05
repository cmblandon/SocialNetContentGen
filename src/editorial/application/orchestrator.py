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

from sqlalchemy.orm import Session

from src.editorial.application.approval_gate import persist_story
from src.editorial.application.case_curation_use_case import CaseCurationUseCase
from src.editorial.application.platform_adaptation_use_case import (
    PlatformAdaptationUseCase,
)
from src.editorial.application.research_agent_use_case import ResearchAgentUseCase
from src.editorial.application.story_writing_use_case import StoryWritingUseCase
from src.editorial.infrastructure.persistence.models import Document
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


def run_research_cycle(
    session: Session,
    source_urls: list[str],
    research_agent: ResearchAgentUseCase,
    case_curation: CaseCurationUseCase,
    story_writing_use_case: StoryWritingUseCase,
    platform_adaptation_use_case: PlatformAdaptationUseCase,
    memory_store: ProjectMemoryStore,
) -> CycleSummary:
    """
    Real input path (Phase 4), replacing the Phase 2 manual-curation CLI
    fixture: discover -> curate -> (only advanced documents) write/adapt/
    persist via run_cycle. A document that curation discards or has
    already evaluated never reaches story-writing.
    """
    research_result = research_agent.discover(source_urls)

    documents_with_angles: list[tuple[Document, str]] = []
    for scraped_document in research_result.documents:
        curation_result = case_curation.curate(scraped_document)
        if curation_result is None or not curation_result.advanced:
            continue

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
        documents_with_angles.append((document, curation_result.narrative_angle))

    return run_cycle(
        session=session,
        documents_with_angles=documents_with_angles,
        story_writing_use_case=story_writing_use_case,
        platform_adaptation_use_case=platform_adaptation_use_case,
        memory_store=memory_store,
    )
