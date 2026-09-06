"""
Script approval — the gate video generation is blocked on
(specs/script-approval-workflow/spec.md).

Approval is chapter-scoped even though `script_approved` is persisted on
PlatformVersion (design.md Decision 1, which put the flag there to reuse the
existing approval infrastructure). A chapter has one `script` field shared by
all four of its platform versions, so approving "the script" is a single
editorial decision that fans out to every platform version of that chapter —
asking an editor to approve the same text four times would be busywork, not
finer control.

Editing a script always clears approval: the approved text and the stored
text must never diverge, or video generation would narrate something no one
signed off on.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.editorial.infrastructure.persistence.models import (
    ApprovalStatus,
    Chapter,
    PlatformVersion,
)

# Mirrors pending_chapters.py: a chapter stays in the review queue until every
# platform version reaches a terminal state.
_ACTIVE_STATUSES = (ApprovalStatus.PENDING_REVIEW, ApprovalStatus.APPROVED)


class ChapterNotFoundError(Exception):
    """Raised when a script action names a chapter that does not exist."""


class EmptyScriptError(Exception):
    """Raised when a script update supplies blank text — an empty script
    would produce a silent video."""


@dataclass
class ScriptApprovalOutcome:
    """State of a chapter's script after an approve/reject/update action."""

    chapter_id: str
    script_approved: bool
    script_approved_at: Optional[datetime]
    platform_versions_updated: int


@dataclass
class ChapterScriptSummary:
    """One row of the script review queue."""

    id: str
    title: str
    script: str
    visual_notes: Optional[str]
    source_citation: str
    script_approved: bool
    script_approved_at: Optional[datetime]
    created_at: datetime
    word_count: int


def approve_chapter_script(session: Session, chapter_id: str) -> ScriptApprovalOutcome:
    """Mark a chapter's script approved, stamping the approval time."""
    chapter = _require_chapter(session, chapter_id)
    approved_at = datetime.now(timezone.utc)

    for platform_version in chapter.platform_versions:
        platform_version.script_approved = True
        platform_version.script_approved_at = approved_at
    session.commit()

    return ScriptApprovalOutcome(
        chapter_id=chapter.id,
        script_approved=True,
        script_approved_at=approved_at,
        platform_versions_updated=len(chapter.platform_versions),
    )


def reject_chapter_script(session: Session, chapter_id: str) -> ScriptApprovalOutcome:
    """Withdraw approval, returning the chapter to the review queue."""
    chapter = _require_chapter(session, chapter_id)

    for platform_version in chapter.platform_versions:
        platform_version.script_approved = False
        platform_version.script_approved_at = None
    session.commit()

    return ScriptApprovalOutcome(
        chapter_id=chapter.id,
        script_approved=False,
        script_approved_at=None,
        platform_versions_updated=len(chapter.platform_versions),
    )


def update_chapter_script(
    session: Session, chapter_id: str, script_text: str
) -> ScriptApprovalOutcome:
    """
    Replace a chapter's script text and reset approval.

    Resetting is unconditional, including when the chapter was already
    approved: the whole point of the gate is that the narrated text is the
    text a human read.
    """
    chapter = _require_chapter(session, chapter_id)
    if not script_text.strip():
        raise EmptyScriptError(f"Chapter {chapter_id} was given an empty script.")

    chapter.script = script_text.strip()
    for platform_version in chapter.platform_versions:
        platform_version.script_approved = False
        platform_version.script_approved_at = None
    session.commit()

    return ScriptApprovalOutcome(
        chapter_id=chapter.id,
        script_approved=False,
        script_approved_at=None,
        platform_versions_updated=len(chapter.platform_versions),
    )


def list_chapters_with_scripts(session: Session) -> list[ChapterScriptSummary]:
    """
    The script review queue: chapters still in play, whether or not their
    script has been approved yet, so an editor can find one to approve and
    can still see what they already approved.
    """
    chapter_ids = (
        session.execute(
            select(Chapter.id)
            .join(PlatformVersion)
            .where(PlatformVersion.status.in_(_ACTIVE_STATUSES))
            .distinct()
        )
        .scalars()
        .all()
    )

    summaries = []
    for chapter_id in chapter_ids:
        chapter = _require_chapter(session, chapter_id)
        summaries.append(
            ChapterScriptSummary(
                id=chapter.id,
                title=chapter.title,
                script=chapter.script,
                visual_notes=chapter.visual_notes,
                source_citation=chapter.source_citation,
                script_approved=is_script_approved(chapter),
                script_approved_at=_approved_at(chapter),
                created_at=chapter.created_at,
                word_count=len(chapter.script.split()),
            )
        )
    return summaries


def is_script_approved(chapter: Chapter) -> bool:
    """
    True only when every platform version carries the approval. A chapter
    with no platform versions is not approved — nothing has been signed off,
    and `all([])` would otherwise claim the opposite.
    """
    if not chapter.platform_versions:
        return False
    return all(pv.script_approved for pv in chapter.platform_versions)


def _approved_at(chapter: Chapter) -> Optional[datetime]:
    stamps = [
        pv.script_approved_at for pv in chapter.platform_versions if pv.script_approved_at
    ]
    return max(stamps) if stamps else None


def _require_chapter(session: Session, chapter_id: str) -> Chapter:
    chapter = session.get(Chapter, chapter_id)
    if chapter is None:
        raise ChapterNotFoundError(f"Chapter {chapter_id} does not exist.")
    return chapter
