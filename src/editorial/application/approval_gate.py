"""
Persists a drafted story/platform-adaptations and enforces the mandatory
human-approval gate — per specs/editorial-orchestration/spec.md ("Block on
explicit human approval before publishing") and design.md Decision 5.

There is no publisher (Phase 5) yet, so the gate is expressed generically:
`run_if_approved` only ever invokes its `action` callback when the
PlatformVersion's persisted status is APPROVED, and raises otherwise. Once
Phase 5 builds a real publisher, it calls this exact function rather than
checking status itself, so "never publish without approval" stays true by
construction wherever publishing is triggered from.
"""
import json
from dataclasses import asdict
from typing import Callable, TypeVar

from sqlalchemy.orm import Session

from src.editorial.core.entities import PlatformAdaptations, StoryDraft
from src.editorial.infrastructure.persistence.models import (
    ApprovalStatus,
    Chapter,
    Document,
    PlatformName,
    PlatformVersion,
    Story,
)

T = TypeVar("T")


class ApprovalRequiredError(Exception):
    """Raised when an action requiring approval is attempted on a
    PlatformVersion that is not (yet) APPROVED."""


class AlreadyDecidedError(Exception):
    """Raised when approve/reject is attempted on a PlatformVersion that
    has already left PENDING_REVIEW — decisions are not reversible through
    this path (a human editing history is a separate, explicit action)."""


def persist_story(
    session: Session,
    document: Document,
    story_draft: StoryDraft,
    platform_adaptations_by_chapter: list[PlatformAdaptations],
) -> Story:
    story = Story(document=document, summary=story_draft.summary)
    session.add(story)

    for chapter_draft, adaptations in zip(story_draft.chapters, platform_adaptations_by_chapter):
        chapter = Chapter(
            story=story,
            chapter_index=chapter_draft.chapter_index,
            title=chapter_draft.title,
            script=chapter_draft.script,
            visual_notes=chapter_draft.visual_notes,
            source_citation=chapter_draft.source_citation,
        )
        session.add(chapter)

        for platform_name, adaptation in (
            (PlatformName.TIKTOK, adaptations.tiktok),
            (PlatformName.INSTAGRAM, adaptations.instagram),
            (PlatformName.X, adaptations.x),
            (PlatformName.FACEBOOK, adaptations.facebook),
        ):
            session.add(
                PlatformVersion(
                    chapter=chapter,
                    platform=platform_name,
                    content=json.dumps(asdict(adaptation)),
                    status=ApprovalStatus.PENDING_REVIEW,
                )
            )

    session.commit()
    return story


def approve_platform_version(session: Session, platform_version_id: str) -> None:
    platform_version = session.get(PlatformVersion, platform_version_id)
    _require_pending_review(platform_version)
    platform_version.status = ApprovalStatus.APPROVED
    session.commit()


def reject_platform_version(session: Session, platform_version_id: str) -> None:
    platform_version = session.get(PlatformVersion, platform_version_id)
    _require_pending_review(platform_version)
    platform_version.status = ApprovalStatus.REJECTED
    session.commit()


def _require_pending_review(platform_version: PlatformVersion) -> None:
    if platform_version.status != ApprovalStatus.PENDING_REVIEW:
        raise AlreadyDecidedError(
            f"PlatformVersion {platform_version.id} was already decided "
            f"(status='{platform_version.status.value}')."
        )


def run_if_approved(
    session: Session,
    platform_version_id: str,
    action: Callable[[PlatformVersion], T],
) -> T:
    platform_version = session.get(PlatformVersion, platform_version_id)
    if platform_version.status != ApprovalStatus.APPROVED:
        raise ApprovalRequiredError(
            f"PlatformVersion {platform_version_id} is '{platform_version.status.value}', "
            "not 'approved' — refusing to proceed."
        )
    return action(platform_version)
