"""
Tests for JinaScraperAdapter — the default ISourceScraper implementation
(design.md Decision 7), per specs/research-agent/spec.md. Jina's reader
service returns raw text/markdown, not structured metadata, so this
adapter's extraction_confidence is always "baja" and it never invents a
description beyond what was fetched.
"""
from src.editorial.core.ports import ScrapedDocument
from src.editorial.infrastructure.scraping.jina_scraper import JinaScraperAdapter


class FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


class FakeHttpClient:
    def __init__(self, response: FakeResponse):
        self._response = response
        self.last_url = None
        self.last_headers = None

    def get(self, url, headers=None, timeout=None):
        self.last_url = url
        self.last_headers = headers
        return self._response


def test_fetch_returns_a_scraped_document_on_success():
    client = FakeHttpClient(FakeResponse(200, "# AARO 2024 Annual Report\n\nFull body text here."))
    adapter = JinaScraperAdapter(api_key="test-key", client=client)

    document = adapter.fetch("https://www.aaro.mil/reports/2024.pdf")

    assert isinstance(document, ScrapedDocument)
    assert document.title == "AARO 2024 Annual Report"
    assert "Full body text here." in document.extracted_text
    assert document.source_url == "https://www.aaro.mil/reports/2024.pdf"
    assert document.extraction_confidence == "baja"


def test_fetch_requests_the_jina_reader_endpoint_with_auth_header():
    client = FakeHttpClient(FakeResponse(200, "# Title\nbody"))
    adapter = JinaScraperAdapter(api_key="test-key", client=client)

    adapter.fetch("https://www.aaro.mil/reports/2024.pdf")

    assert client.last_url == "https://r.jina.ai/https://www.aaro.mil/reports/2024.pdf"
    assert client.last_headers["Authorization"] == "Bearer test-key"


def test_fetch_infers_doc_type_from_pdf_extension():
    client = FakeHttpClient(FakeResponse(200, "# Title\nbody"))
    adapter = JinaScraperAdapter(api_key="", client=client)

    document = adapter.fetch("https://www.aaro.mil/reports/2024.pdf")

    assert document.doc_type == "report"


def test_fetch_infers_doc_type_from_video_extension():
    client = FakeHttpClient(FakeResponse(200, "Caption: gimbal footage released by DoD."))
    adapter = JinaScraperAdapter(api_key="", client=client)

    document = adapter.fetch("https://www.aaro.mil/videos/gimbal.mp4")

    assert document.doc_type == "video"


def test_fetch_infers_doc_type_from_image_extension():
    client = FakeHttpClient(FakeResponse(200, "Caption: radar screenshot."))
    adapter = JinaScraperAdapter(api_key="", client=client)

    document = adapter.fetch("https://www.aaro.mil/images/radar.jpg")

    assert document.doc_type == "photo"


def test_fetch_returns_none_on_non_200_response():
    client = FakeHttpClient(FakeResponse(404, ""))
    adapter = JinaScraperAdapter(api_key="", client=client)

    assert adapter.fetch("https://www.aaro.mil/missing.pdf") is None


def test_fetch_returns_none_when_page_requires_login():
    client = FakeHttpClient(FakeResponse(401, ""))
    adapter = JinaScraperAdapter(api_key="", client=client)

    assert adapter.fetch("https://protected.example.com/doc.pdf") is None


def test_fetch_returns_none_when_body_is_empty():
    client = FakeHttpClient(FakeResponse(200, "   "))
    adapter = JinaScraperAdapter(api_key="", client=client)

    assert adapter.fetch("https://www.aaro.mil/blank.pdf") is None


def test_fetch_never_pads_or_invents_content_for_a_short_ocr_failure(): # noqa: E501
    """When the underlying document is a poorly-scanned PDF, Jina's reader
    may return very little usable text. The adapter must pass that through
    honestly (low confidence) rather than inventing content to fill the gap."""
    client = FakeHttpClient(FakeResponse(200, "??? scan artifact ???"))
    adapter = JinaScraperAdapter(api_key="", client=client)

    document = adapter.fetch("https://www.aaro.mil/scanned.pdf")

    assert document.extracted_text.strip() == "??? scan artifact ???"
    assert document.extraction_confidence == "baja"


def test_fetch_uses_a_generic_title_when_no_markdown_heading_is_present():
    client = FakeHttpClient(FakeResponse(200, "Just plain text with no heading."))
    adapter = JinaScraperAdapter(api_key="", client=client)

    document = adapter.fetch("https://www.aaro.mil/reports/untitled.pdf")

    assert document.title == "untitled.pdf"


def test_fetch_accepts_a_query_without_changing_the_request():
    """research-query-scoping: Jina's reader has no query mode — passing a
    query is a documented no-op, not an error, and must not alter the
    outbound request in any way."""
    client = FakeHttpClient(FakeResponse(200, "# Title\nbody"))
    adapter = JinaScraperAdapter(api_key="test-key", client=client)

    document = adapter.fetch("https://www.aaro.mil/reports/2024.pdf", query="missile silos")

    assert client.last_url == "https://r.jina.ai/https://www.aaro.mil/reports/2024.pdf"
    assert client.last_headers["Authorization"] == "Bearer test-key"
    assert document is not None
    assert document.title == "Title"


def test_fetch_with_and_without_a_query_produces_the_same_request():
    client_without_query = FakeHttpClient(FakeResponse(200, "# Title\nbody"))
    adapter_without_query = JinaScraperAdapter(api_key="test-key", client=client_without_query)
    client_with_query = FakeHttpClient(FakeResponse(200, "# Title\nbody"))
    adapter_with_query = JinaScraperAdapter(api_key="test-key", client=client_with_query)

    adapter_without_query.fetch("https://www.aaro.mil/reports/2024.pdf")
    adapter_with_query.fetch("https://www.aaro.mil/reports/2024.pdf", query="missile silos")

    assert client_without_query.last_url == client_with_query.last_url
    assert client_without_query.last_headers == client_with_query.last_headers
