import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.editorial.infrastructure.persistence.models import (
    Base,
    Document,
    Story,
    Chapter,
    PlatformVersion,
    PublishRecord,
    PlatformName,
    ApprovalStatus,
)


@pytest.fixture
def engine():
    """In-memory SQLite engine with the editorial schema applied."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as session:
        yield session


def _make_document(**overrides) -> Document:
    defaults = dict(
        title="AARO 2024 Annual Report",
        agency="AARO",
        doc_type="report",
        published_date="2024-03-01",
        source_url="https://www.aaro.mil/reports/2024",
        extracted_text="Full extracted text of the report.",
        extraction_confidence="alta",
    )
    defaults.update(overrides)
    return Document(**defaults)


def test_document_can_be_created_with_required_fields(session):
    """Requirement 1.2: Document stores the fields the research-agent spec extracts."""
    document = _make_document()

    session.add(document)
    session.commit()

    persisted = session.get(Document, document.id)
    assert persisted is not None
    assert persisted.title == "AARO 2024 Annual Report"
    assert persisted.agency == "AARO"
    assert persisted.doc_type == "report"
    assert persisted.published_date == "2024-03-01"
    assert persisted.source_url == "https://www.aaro.mil/reports/2024"
    assert persisted.extracted_text == "Full extracted text of the report."
    assert persisted.created_at is not None


def test_document_source_ficha_id_is_optional(session):
    """Requirement 1.2 / Design Decision 3: source_ficha_id references the ingestion
    pipeline's FichaEstructurada by id, but is optional for documents that originate
    directly from research-agent scraping rather than manual ingestion."""
    scraped_document = _make_document()
    manually_ingested_document = _make_document(source_ficha_id="ficha-123")

    session.add_all([scraped_document, manually_ingested_document])
    session.commit()

    assert session.get(Document, scraped_document.id).source_ficha_id is None
    assert session.get(Document, manually_ingested_document.id).source_ficha_id == "ficha-123"


def test_story_belongs_to_document(session):
    """Requirement 1.2: Story references its source Document (design's Document -> Story chain)."""
    document = _make_document()
    story = Story(document=document, summary="A pilot reports an unidentified radar contact.")

    session.add(document)
    session.add(story)
    session.commit()

    persisted_document = session.get(Document, document.id)
    assert len(persisted_document.stories) == 1
    assert persisted_document.stories[0].summary == "A pilot reports an unidentified radar contact."
    assert persisted_document.stories[0].document_id == document.id


def test_chapters_are_ordered_by_chapter_index(session):
    """Requirement 1.2 / story-writing spec: chapters must preserve their sequence
    so playback/publishing order matches the narrative's cliffhanger structure."""
    document = _make_document()
    story = Story(document=document, summary="Multi-chapter case.")
    chapter_two = Chapter(
        story=story,
        chapter_index=2,
        title="Part 2",
        script="..." * 10,
        source_citation="AARO, report, 2024-03-01",
    )
    chapter_one = Chapter(
        story=story,
        chapter_index=1,
        title="Part 1",
        script="..." * 10,
        source_citation="AARO, report, 2024-03-01",
    )

    session.add_all([document, story, chapter_two, chapter_one])
    session.commit()

    persisted_story = session.get(Story, story.id)
    assert [chapter.chapter_index for chapter in persisted_story.chapters] == [1, 2]


def test_platform_version_defaults_to_pending_review(session):
    """Requirement 1.2 / Design Decision 5: every PlatformVersion starts pending_review
    so nothing reaches the publisher without an explicit approval transition."""
    document = _make_document()
    story = Story(document=document, summary="Case summary.")
    chapter = Chapter(
        story=story,
        chapter_index=1,
        title="Part 1",
        script="Spoken script.",
        source_citation="AARO, report, 2024-03-01",
    )
    platform_version = PlatformVersion(
        chapter=chapter,
        platform=PlatformName.TIKTOK,
        content="On-screen hook + script + hashtags.",
    )

    session.add_all([document, story, chapter, platform_version])
    session.commit()

    persisted = session.get(PlatformVersion, platform_version.id)
    assert persisted.status == ApprovalStatus.PENDING_REVIEW


@pytest.mark.parametrize(
    "status",
    [
        ApprovalStatus.PENDING_REVIEW,
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
        ApprovalStatus.PUBLISHED,
        ApprovalStatus.FAILED,
    ],
)
def test_platform_version_accepts_every_approval_status(session, status):
    """Requirement 1.2 / Design Decision 5: the status enum must cover the full
    pending_review -> approved/rejected -> published/failed lifecycle."""
    document = _make_document()
    story = Story(document=document, summary="Case summary.")
    chapter = Chapter(
        story=story,
        chapter_index=1,
        title="Part 1",
        script="Spoken script.",
        source_citation="AARO, report, 2024-03-01",
    )
    platform_version = PlatformVersion(
        chapter=chapter,
        platform=PlatformName.X,
        content="Thread content.",
        status=status,
    )

    session.add_all([document, story, chapter, platform_version])
    session.commit()

    assert session.get(PlatformVersion, platform_version.id).status == status


def test_publish_record_links_to_platform_version_and_stores_post_id(session):
    """Requirement 1.2 / publishing spec: every publish outcome is recorded against
    its PlatformVersion, including the API-returned post id for later metrics correlation."""
    document = _make_document()
    story = Story(document=document, summary="Case summary.")
    chapter = Chapter(
        story=story,
        chapter_index=1,
        title="Part 1",
        script="Spoken script.",
        source_citation="AARO, report, 2024-03-01",
    )
    platform_version = PlatformVersion(
        chapter=chapter,
        platform=PlatformName.FACEBOOK,
        content="Long-form post.",
        status=ApprovalStatus.PUBLISHED,
    )
    publish_record = PublishRecord(
        platform_version=platform_version,
        external_post_id="fb_post_789",
        status=ApprovalStatus.PUBLISHED,
    )

    session.add_all([document, story, chapter, platform_version, publish_record])
    session.commit()

    persisted_version = session.get(PlatformVersion, platform_version.id)
    assert len(persisted_version.publish_records) == 1
    assert persisted_version.publish_records[0].external_post_id == "fb_post_789"


def test_deleting_document_cascades_to_dependent_rows(session):
    """Requirement 1.2: deleting a Document should not orphan its Story/Chapter/
    PlatformVersion/PublishRecord chain."""
    document = _make_document()
    story = Story(document=document, summary="Case summary.")
    chapter = Chapter(
        story=story,
        chapter_index=1,
        title="Part 1",
        script="Spoken script.",
        source_citation="AARO, report, 2024-03-01",
    )
    platform_version = PlatformVersion(
        chapter=chapter,
        platform=PlatformName.INSTAGRAM,
        content="Carousel content.",
    )
    publish_record = PublishRecord(platform_version=platform_version)

    session.add_all([document, story, chapter, platform_version, publish_record])
    session.commit()

    session.delete(document)
    session.commit()

    assert session.get(Story, story.id) is None
    assert session.get(Chapter, chapter.id) is None
    assert session.get(PlatformVersion, platform_version.id) is None
    assert session.get(PublishRecord, publish_record.id) is None
