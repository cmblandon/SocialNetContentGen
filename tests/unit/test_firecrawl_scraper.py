"""
Tests for FirecrawlScraperAdapter — the fallback ISourceScraper used when
Jina fails on a protected/complex page (design.md Decision 7). Implemented
via raw HTTP against Firecrawl's /v1/extract API rather than the
firecrawl-py SDK (task 4.1 note). Its structured (AI-driven) extraction
means extraction_confidence is "alta" on success, unlike Jina's "baja".

Note: the exact request/response shape here is a good-faith approximation
of Firecrawl's public /v1/extract API, not verified against live docs in
this session — confirm the wire format against Firecrawl's current API
reference before this adapter is used against the real service.
"""
from src.editorial.core.ports import ScrapedDocument
from src.editorial.infrastructure.scraping.firecrawl_scraper import (
    FirecrawlScraperAdapter,
)


class FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None):
        self.status_code = status_code
        self._json_body = json_body or {}

    def json(self):
        return self._json_body


class FakeHttpClient:
    def __init__(self, response: FakeResponse):
        self._response = response
        self.last_url = None
        self.last_json = None
        self.last_headers = None

    def post(self, url, json=None, headers=None, timeout=None):
        self.last_url = url
        self.last_json = json
        self.last_headers = headers
        return self._response


def _success_response(**overrides) -> FakeResponse:
    data = {
        "title": "AARO 2024 Annual Report",
        "agency": "AARO",
        "doc_type": "report",
        "published_date": "2024-03-01",
        "summary": "Full extracted summary text.",
    }
    data.update(overrides)
    return FakeResponse(200, {"success": True, "data": data})


def test_fetch_returns_a_structured_scraped_document_on_success():
    client = FakeHttpClient(_success_response())
    adapter = FirecrawlScraperAdapter(api_key="test-key", client=client)

    document = adapter.fetch("https://theblackvault.com/documentarchive/some-case/")

    assert isinstance(document, ScrapedDocument)
    assert document.title == "AARO 2024 Annual Report"
    assert document.agency == "AARO"
    assert document.doc_type == "report"
    assert document.published_date == "2024-03-01"
    assert document.extracted_text == "Full extracted summary text."
    assert document.extraction_confidence == "alta"
    assert document.source_url == "https://theblackvault.com/documentarchive/some-case/"


def test_fetch_sends_the_url_and_auth_header():
    client = FakeHttpClient(_success_response())
    adapter = FirecrawlScraperAdapter(api_key="test-key", client=client)

    adapter.fetch("https://theblackvault.com/documentarchive/some-case/")

    assert client.last_json["urls"] == ["https://theblackvault.com/documentarchive/some-case/"]
    assert client.last_headers["Authorization"] == "Bearer test-key"


def test_fetch_returns_none_on_non_200_response():
    client = FakeHttpClient(FakeResponse(500, {}))
    adapter = FirecrawlScraperAdapter(api_key="test-key", client=client)

    assert adapter.fetch("https://theblackvault.com/documentarchive/some-case/") is None


def test_fetch_returns_none_when_extraction_was_unsuccessful():
    client = FakeHttpClient(FakeResponse(200, {"success": False}))
    adapter = FirecrawlScraperAdapter(api_key="test-key", client=client)

    assert adapter.fetch("https://theblackvault.com/documentarchive/some-case/") is None


def test_fetch_returns_none_when_summary_is_missing_or_empty():
    client = FakeHttpClient(_success_response(summary=""))
    adapter = FirecrawlScraperAdapter(api_key="test-key", client=client)

    assert adapter.fetch("https://theblackvault.com/documentarchive/some-case/") is None
