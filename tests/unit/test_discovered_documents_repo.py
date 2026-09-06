"""
Tests for discovered_documents_repo — the persistence helpers backing
DiscoveredDocument checkpoints (research-pipeline-checkpointing design.md
Decision 1).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.editorial.core.ports import ScrapedDocument
from src.editorial.infrastructure.persistence.discovered_documents_repo import (
    count_checkpoints_by_status,
    create_pending_checkpoint,
    find_checkpoint_by_source_url,
    find_checkpoints_by_status,
    mark_checkpoint_advanced,
    mark_checkpoint_discarded,
    mark_checkpoint_failed,
)
from src.editorial.infrastructure.persistence.models import Base, CurationStatus, DiscoveredDocument


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _scraped_document(**overrides) -> ScrapedDocument:
    defaults = dict(
        title="AARO 2024 Annual Report",
        agency="AARO",
        doc_type="report",
        extracted_text="Full text.",
        published_date="2024-03-01",
        source_url="https://www.aaro.mil/reports/2024.pdf",
        extraction_confidence="baja",
    )
    defaults.update(overrides)
    return ScrapedDocument(**defaults)


def test_create_pending_checkpoint_persists_a_pending_row():
    session = _session()
    document = _scraped_document()

    checkpoint = create_pending_checkpoint(session, document)

    assert checkpoint.status == CurationStatus.PENDING
    reloaded = session.get(DiscoveredDocument, checkpoint.id)
    assert reloaded.title == document.title
    assert reloaded.agency == document.agency
    assert reloaded.doc_type == document.doc_type
    assert reloaded.extracted_text == document.extracted_text
    assert reloaded.published_date == document.published_date
    assert reloaded.source_url == document.source_url
    assert reloaded.extraction_confidence == document.extraction_confidence
    assert reloaded.status == CurationStatus.PENDING


def test_find_checkpoint_by_source_url_returns_the_matching_row():
    session = _session()
    checkpoint = create_pending_checkpoint(session, _scraped_document(source_url="https://x.example/a"))

    found = find_checkpoint_by_source_url(session, "https://x.example/a")

    assert found is not None
    assert found.id == checkpoint.id


def test_find_checkpoint_by_source_url_returns_none_when_absent():
    session = _session()

    assert find_checkpoint_by_source_url(session, "https://x.example/missing") is None


def test_find_checkpoint_by_source_url_returns_none_for_a_falsy_url():
    session = _session()

    assert find_checkpoint_by_source_url(session, None) is None
    assert find_checkpoint_by_source_url(session, "") is None


def test_find_checkpoints_by_status_filters_by_the_given_statuses():
    session = _session()
    pending = create_pending_checkpoint(session, _scraped_document(title="Pending", source_url="u1"))
    failed = create_pending_checkpoint(session, _scraped_document(title="Failed", source_url="u2"))
    advanced = create_pending_checkpoint(session, _scraped_document(title="Advanced", source_url="u3"))
    discarded = create_pending_checkpoint(session, _scraped_document(title="Discarded", source_url="u4"))
    mark_checkpoint_failed(session, failed, "boom")
    mark_checkpoint_advanced(session, advanced, document_id="doc-1", narrative_angle="angle")
    mark_checkpoint_discarded(session, discarded)

    results = find_checkpoints_by_status(session, [CurationStatus.PENDING, CurationStatus.FAILED])

    assert {r.id for r in results} == {pending.id, failed.id}


def test_mark_checkpoint_failed_sets_status_and_error_message():
    session = _session()
    checkpoint = create_pending_checkpoint(session, _scraped_document())

    mark_checkpoint_failed(session, checkpoint, "Anthropic credit balance too low")

    reloaded = session.get(DiscoveredDocument, checkpoint.id)
    assert reloaded.status == CurationStatus.FAILED
    assert reloaded.error_message == "Anthropic credit balance too low"


def test_mark_checkpoint_discarded_sets_status():
    session = _session()
    checkpoint = create_pending_checkpoint(session, _scraped_document())

    mark_checkpoint_discarded(session, checkpoint)

    reloaded = session.get(DiscoveredDocument, checkpoint.id)
    assert reloaded.status == CurationStatus.DISCARDED


def test_mark_checkpoint_advanced_sets_status_document_id_and_narrative_angle():
    session = _session()
    checkpoint = create_pending_checkpoint(session, _scraped_document())

    mark_checkpoint_advanced(session, checkpoint, document_id="doc-123", narrative_angle="a strong angle")

    reloaded = session.get(DiscoveredDocument, checkpoint.id)
    assert reloaded.status == CurationStatus.ADVANCED
    assert reloaded.document_id == "doc-123"
    assert reloaded.narrative_angle == "a strong angle"


def test_count_checkpoints_by_status_counts_only_matching_rows():
    session = _session()
    c1 = create_pending_checkpoint(session, _scraped_document(title="P1", source_url="u1"))
    c2 = create_pending_checkpoint(session, _scraped_document(title="P2", source_url="u2"))
    c3 = create_pending_checkpoint(session, _scraped_document(title="F1", source_url="u3"))
    mark_checkpoint_failed(session, c3, "boom")

    assert count_checkpoints_by_status(session, CurationStatus.PENDING) == 2
    assert count_checkpoints_by_status(session, CurationStatus.FAILED) == 1
    assert count_checkpoints_by_status(session, CurationStatus.ADVANCED) == 0
