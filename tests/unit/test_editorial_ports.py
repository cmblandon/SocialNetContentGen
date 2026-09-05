"""
Structural conformance tests for the editorial ports (design.md Decision 7).

These ports are declared @runtime_checkable so conformance can be verified
with isinstance() against both a conforming fake and a non-conforming one,
without either fake needing to inherit from the Protocol.
"""
from src.editorial.core.ports import (
    ILLMClient,
    ISocialPublisher,
    ISourceScraper,
    PublishResult,
    ScrapedDocument,
)


class FakeScraper:
    def fetch(self, source_url: str):
        return None


class IncompleteScraper:
    """Deliberately missing fetch() — must NOT satisfy ISourceScraper."""


def test_conforming_scraper_satisfies_protocol():
    assert isinstance(FakeScraper(), ISourceScraper)


def test_non_conforming_object_does_not_satisfy_scraper_protocol():
    assert not isinstance(IncompleteScraper(), ISourceScraper)


class FakePublisher:
    def publish(self, platform, content, scheduled_at=None):
        return PublishResult(success=True, external_post_id="123")


def test_conforming_publisher_satisfies_protocol():
    assert isinstance(FakePublisher(), ISocialPublisher)


def test_non_conforming_object_does_not_satisfy_publisher_protocol():
    assert not isinstance(object(), ISocialPublisher)


class FakeLLMClient:
    def complete(self, prompt: str) -> str:
        return "response"


def test_conforming_llm_client_satisfies_protocol():
    assert isinstance(FakeLLMClient(), ILLMClient)


def test_non_conforming_object_does_not_satisfy_llm_client_protocol():
    assert not isinstance(object(), ILLMClient)


def test_scraped_document_holds_required_research_agent_fields():
    """Requirement per specs/research-agent: title, agency, doc type, and
    extracted text/summary are mandatory; date/url/confidence are optional."""
    document = ScrapedDocument(
        title="AARO 2024 Annual Report",
        agency="AARO",
        doc_type="report",
        extracted_text="Full text.",
    )

    assert document.published_date is None
    assert document.source_url is None
    assert document.extraction_confidence is None


def test_publish_result_carries_error_without_a_post_id_on_failure():
    """Requirement per specs/publishing: a failed publish attempt must be
    reportable without fabricating a post id."""
    result = PublishResult(success=False, error_message="account limit reached")

    assert result.external_post_id is None
    assert result.error_message == "account limit reached"
