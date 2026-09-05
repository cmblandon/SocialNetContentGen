"""
Tests for PublishingUseCase — per specs/publishing/spec.md. Reuses
approval_gate.run_if_approved (design.md Decision 5) so a PlatformVersion
that isn't APPROVED can never reach the publisher. Scheduling uses an
"optimal_time:<platform>=HH:MM" line in calendario.md when present;
otherwise it proposes one and does not publish, per the spec's explicit
"propose and hold for approval, don't publish immediately" requirement.
"""
from datetime import date, datetime, time, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.editorial.application.approval_gate import (
    ApprovalRequiredError,
    approve_platform_version,
    persist_story,
)
from src.editorial.application.publishing_use_case import PublishingUseCase
from src.editorial.core.entities import (
    ChapterDraft,
    FacebookAdaptation,
    InstagramAdaptation,
    PlatformAdaptations,
    StoryDraft,
    TikTokAdaptation,
    XAdaptation,
)
from src.editorial.core.ports import PublishResult
from src.editorial.infrastructure.persistence.models import (
    ApprovalStatus,
    Base,
    Document,
    PlatformVersion,
    PublishRecord,
)
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def memory_store(tmp_path):
    return ProjectMemoryStore(memory_dir=tmp_path)


class FakePublisher:
    def __init__(self, result: PublishResult):
        self._result = result
        self.calls: list[dict] = []

    def publish(self, platform, content, scheduled_at=None):
        self.calls.append({"platform": platform, "content": content, "scheduled_at": scheduled_at})
        return self._result


def _approved_platform_version_id(session) -> str:
    document = Document(title="t", agency="AARO", doc_type="report", extracted_text="text")
    session.add(document)
    session.commit()

    story_draft = StoryDraft(
        summary="s",
        chapters=[
            ChapterDraft(title="P1", script="script", visual_notes="n", source_citation="c", chapter_index=1)
        ],
    )
    adaptations = PlatformAdaptations(
        tiktok=TikTokAdaptation(script="s", on_screen_hook_lines=["a", "b"], hashtags=["#a", "#b", "#c"], description="d"),
        instagram=InstagramAdaptation(carousel_slides=["1", "2", "3", "4", "5", "6"]),
        x=XAdaptation(tweets=["t1", "t2", "t3", "t4"]),
        facebook=FacebookAdaptation(post="p?"),
    )
    story = persist_story(session, document, story_draft, [adaptations])
    platform_version_id = next(
        pv.id for pv in story.chapters[0].platform_versions if pv.platform.value == "tiktok"
    )
    approve_platform_version(session, platform_version_id)
    return platform_version_id


def test_raises_when_the_platform_version_is_not_approved(session, memory_store):
    document = Document(title="t", agency="AARO", doc_type="report", extracted_text="text")
    session.add(document)
    session.commit()
    story_draft = StoryDraft(
        summary="s",
        chapters=[ChapterDraft(title="P1", script="script", visual_notes="n", source_citation="c", chapter_index=1)],
    )
    adaptations = PlatformAdaptations(
        tiktok=TikTokAdaptation(script="s", on_screen_hook_lines=["a", "b"], hashtags=["#a", "#b", "#c"], description="d"),
        instagram=InstagramAdaptation(carousel_slides=["1", "2", "3", "4", "5", "6"]),
        x=XAdaptation(tweets=["t1", "t2", "t3", "t4"]),
        facebook=FacebookAdaptation(post="p?"),
    )
    story = persist_story(session, document, story_draft, [adaptations])
    pending_id = story.chapters[0].platform_versions[0].id  # never approved
    publisher = FakePublisher(PublishResult(success=True, external_post_id="x"))
    use_case = PublishingUseCase(publisher=publisher, memory_store=memory_store)

    with pytest.raises(ApprovalRequiredError):
        use_case.publish(session, pending_id)

    assert publisher.calls == []


def test_proposes_a_time_and_does_not_publish_when_no_optimal_time_is_defined(session, memory_store):
    platform_version_id = _approved_platform_version_id(session)
    publisher = FakePublisher(PublishResult(success=True, external_post_id="x"))
    use_case = PublishingUseCase(publisher=publisher, memory_store=memory_store)

    outcome = use_case.publish(session, platform_version_id)

    assert outcome.published is False
    assert outcome.proposed_time is not None
    assert publisher.calls == []
    assert "optimal_time:tiktok" in memory_store.read_calendario()
    # status remains approved -- nothing was published, so the gate must
    # still allow a real publish attempt once an optimal time is set.
    assert session.get(PlatformVersion, platform_version_id).status == ApprovalStatus.APPROVED


def test_publishes_using_the_defined_optimal_time(session, memory_store):
    memory_store.append_calendario_entry("optimal_time:tiktok=18:00")
    platform_version_id = _approved_platform_version_id(session)
    publisher = FakePublisher(PublishResult(success=True, external_post_id="postiz-123"))
    use_case = PublishingUseCase(publisher=publisher, memory_store=memory_store)

    outcome = use_case.publish(session, platform_version_id)

    assert outcome.published is True
    assert outcome.external_post_id == "postiz-123"
    assert len(publisher.calls) == 1
    expected_time = datetime.combine(date.today(), time(18, 0), tzinfo=timezone.utc)
    assert publisher.calls[0]["scheduled_at"] == expected_time
    assert publisher.calls[0]["platform"] == "tiktok"


def test_records_a_successful_publish_as_a_publish_record_and_updates_status(session, memory_store):
    memory_store.append_calendario_entry("optimal_time:tiktok=18:00")
    platform_version_id = _approved_platform_version_id(session)
    publisher = FakePublisher(PublishResult(success=True, external_post_id="postiz-123"))
    use_case = PublishingUseCase(publisher=publisher, memory_store=memory_store)

    use_case.publish(session, platform_version_id)

    platform_version = session.get(PlatformVersion, platform_version_id)
    assert platform_version.status == ApprovalStatus.PUBLISHED
    record = session.query(PublishRecord).filter_by(platform_version_id=platform_version_id).one()
    assert record.external_post_id == "postiz-123"
    assert record.status == ApprovalStatus.PUBLISHED
    assert "postiz-123" in memory_store.read_calendario()


def test_records_a_failed_publish_without_retrying(session, memory_store):
    memory_store.append_calendario_entry("optimal_time:tiktok=18:00")
    platform_version_id = _approved_platform_version_id(session)
    publisher = FakePublisher(PublishResult(success=False, error_message="account limit reached"))
    use_case = PublishingUseCase(publisher=publisher, memory_store=memory_store)

    outcome = use_case.publish(session, platform_version_id)

    assert outcome.published is False
    assert outcome.error_message == "account limit reached"
    assert len(publisher.calls) == 1  # exactly once -- no automatic retry

    platform_version = session.get(PlatformVersion, platform_version_id)
    assert platform_version.status == ApprovalStatus.FAILED
    record = session.query(PublishRecord).filter_by(platform_version_id=platform_version_id).one()
    assert record.status == ApprovalStatus.FAILED
    assert record.error_message == "account limit reached"


def test_a_second_publish_attempt_after_failure_requires_re_approval(session, memory_store):
    memory_store.append_calendario_entry("optimal_time:tiktok=18:00")
    platform_version_id = _approved_platform_version_id(session)
    publisher = FakePublisher(PublishResult(success=False, error_message="rejected"))
    use_case = PublishingUseCase(publisher=publisher, memory_store=memory_store)

    use_case.publish(session, platform_version_id)

    with pytest.raises(ApprovalRequiredError):
        use_case.publish(session, platform_version_id)

    assert len(publisher.calls) == 1  # the second call never reached the publisher
