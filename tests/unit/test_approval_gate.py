"""
Tests for persisting a drafted story/platform-adaptations and the
human-approval gate — per specs/editorial-orchestration/spec.md ("Block on
explicit human approval before publishing") and design.md Decision 5: the
gate is enforced structurally via the persisted PlatformVersion.status, not
by trusting the agent's own behavior.

There is no publisher yet (Phase 5), so "resumes toward publishing" is
tested here as: an arbitrary downstream action only ever runs when the
status is APPROVED, and never otherwise.
"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.editorial.application.approval_gate import (
    AlreadyDecidedError,
    ApprovalRequiredError,
    approve_platform_version,
    persist_story,
    reject_platform_version,
    run_if_approved,
)
from src.editorial.core.entities import (
    ChapterDraft,
    FacebookAdaptation,
    InstagramAdaptation,
    PlatformAdaptations,
    StoryDraft,
    TikTokAdaptation,
    XAdaptation,
)
from src.editorial.infrastructure.persistence.models import (
    ApprovalStatus,
    Base,
    Document,
    PlatformName,
    PlatformVersion,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def document(session):
    document = Document(
        title="AARO 2024 Annual Report",
        agency="AARO",
        doc_type="report",
        extracted_text="Full text.",
    )
    session.add(document)
    session.commit()
    return document


def _adaptations() -> PlatformAdaptations:
    return PlatformAdaptations(
        tiktok=TikTokAdaptation(script="s", on_screen_hook_lines=["a", "b"], hashtags=["#a", "#b", "#c"], description="d"),
        instagram=InstagramAdaptation(carousel_slides=["1", "2", "3", "4", "5", "6"]),
        x=XAdaptation(tweets=["t1", "t2", "t3", "t4"]),
        facebook=FacebookAdaptation(post="p?"),
    )


def _story_draft() -> StoryDraft:
    return StoryDraft(
        summary="A radar contact goes unexplained.",
        chapters=[
            ChapterDraft(
                title="Part 1",
                script="Chapter script.",
                visual_notes="Show the radar log.",
                source_citation="AARO, report, 2024-03-01",
                chapter_index=1,
            )
        ],
    )


def test_persisting_a_story_creates_all_four_platform_versions_as_pending_review(session, document):
    story = persist_story(session, document, _story_draft(), [_adaptations()])

    chapter = story.chapters[0]
    assert len(chapter.platform_versions) == 4
    assert {pv.platform for pv in chapter.platform_versions} == set(PlatformName)
    assert all(pv.status == ApprovalStatus.PENDING_REVIEW for pv in chapter.platform_versions)


def test_persisted_platform_version_content_round_trips_the_adaptation(session, document):
    story = persist_story(session, document, _story_draft(), [_adaptations()])

    tiktok_version = next(
        pv for pv in story.chapters[0].platform_versions if pv.platform == PlatformName.TIKTOK
    )
    content = json.loads(tiktok_version.content)
    assert content["hashtags"] == ["#a", "#b", "#c"]


def test_approve_transitions_status_to_approved(session, document):
    story = persist_story(session, document, _story_draft(), [_adaptations()])
    platform_version_id = story.chapters[0].platform_versions[0].id

    approve_platform_version(session, platform_version_id)

    updated = session.get(PlatformVersion, platform_version_id)
    assert updated.status == ApprovalStatus.APPROVED


def test_reject_transitions_status_to_rejected(session, document):
    story = persist_story(session, document, _story_draft(), [_adaptations()])
    platform_version_id = story.chapters[0].platform_versions[0].id

    reject_platform_version(session, platform_version_id)

    updated = session.get(PlatformVersion, platform_version_id)
    assert updated.status == ApprovalStatus.REJECTED


def test_run_if_approved_raises_and_never_calls_the_action_when_pending_review(session, document):
    story = persist_story(session, document, _story_draft(), [_adaptations()])
    platform_version_id = story.chapters[0].platform_versions[0].id
    calls = []

    with pytest.raises(ApprovalRequiredError):
        run_if_approved(session, platform_version_id, action=lambda pv: calls.append(pv.id))

    assert calls == []


def test_run_if_approved_raises_and_never_calls_the_action_when_rejected(session, document):
    story = persist_story(session, document, _story_draft(), [_adaptations()])
    platform_version_id = story.chapters[0].platform_versions[0].id
    reject_platform_version(session, platform_version_id)
    calls = []

    with pytest.raises(ApprovalRequiredError):
        run_if_approved(session, platform_version_id, action=lambda pv: calls.append(pv.id))

    assert calls == []


def test_approve_raises_when_the_platform_version_was_already_decided(session, document):
    story = persist_story(session, document, _story_draft(), [_adaptations()])
    platform_version_id = story.chapters[0].platform_versions[0].id
    approve_platform_version(session, platform_version_id)

    with pytest.raises(AlreadyDecidedError):
        approve_platform_version(session, platform_version_id)


def test_reject_raises_when_the_platform_version_was_already_decided(session, document):
    story = persist_story(session, document, _story_draft(), [_adaptations()])
    platform_version_id = story.chapters[0].platform_versions[0].id
    reject_platform_version(session, platform_version_id)

    with pytest.raises(AlreadyDecidedError):
        reject_platform_version(session, platform_version_id)


def test_run_if_approved_calls_the_action_exactly_once_when_approved(session, document):
    story = persist_story(session, document, _story_draft(), [_adaptations()])
    platform_version_id = story.chapters[0].platform_versions[0].id
    approve_platform_version(session, platform_version_id)
    calls = []

    result = run_if_approved(session, platform_version_id, action=lambda pv: calls.append(pv.id) or "published")

    assert calls == [platform_version_id]
    assert result == "published"
