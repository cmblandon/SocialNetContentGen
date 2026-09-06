"""
Tests for ResearchAgentUseCase — per specs/research-agent/spec.md.

Scope note: "discovering new documents from a source" is implemented here
as processing a caller-supplied list of candidate URLs (already identified
by the operator or a future listing step), not as autonomously crawling a
site's listing pages for new links — that would be a much larger scraping
project and is out of scope for this phase. What IS in scope and tested:
the source allowlist, dedup-before-extraction against /casos_cubiertos.md,
the Jina-then-Firecrawl fallback, discard-and-report on inaccessible
sources, and passing extracted text through without interpretation.
"""
from typing import Optional

from src.editorial.application.research_agent_use_case import ResearchAgentUseCase
from src.editorial.core.ports import ScrapedDocument
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore


class FakeScraper:
    def __init__(
        self,
        documents_by_url: dict,
        call_log: Optional[list[str]] = None,
        name: str = "scraper",
    ):
        self._documents_by_url = documents_by_url
        self.fetched_urls: list[str] = []
        self.fetched_queries: list[Optional[str]] = []
        self._call_log = call_log
        self._name = name

    def fetch(self, source_url: str, query: Optional[str] = None):
        self.fetched_urls.append(source_url)
        self.fetched_queries.append(query)
        if self._call_log is not None:
            self._call_log.append(self._name)
        return self._documents_by_url.get(source_url)


def _document(**overrides) -> ScrapedDocument:
    defaults = dict(
        title="AARO 2024 Annual Report",
        agency="AARO",
        doc_type="report",
        extracted_text="Full text exactly as extracted, no rewriting.",
    )
    defaults.update(overrides)
    return ScrapedDocument(**defaults)


def test_discards_a_url_outside_the_official_source_allowlist(tmp_path):
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    primary = FakeScraper({})
    use_case = ResearchAgentUseCase(primary_scraper=primary, fallback_scraper=None, memory_store=memory_store)

    result = use_case.discover(["https://random-blog.example.com/ufo-post"])

    assert result.documents == []
    assert len(result.discarded) == 1
    assert result.discarded[0].source_url == "https://random-blog.example.com/ufo-post"
    assert primary.fetched_urls == []  # never even attempted to fetch a disallowed source


def test_skips_a_url_already_recorded_in_casos_cubiertos_without_fetching(tmp_path):
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    memory_store.append_caso_cubierto("2026-09-01 | https://www.aaro.mil/reports/2023.pdf | advanced | score 18/25")
    primary = FakeScraper({})
    use_case = ResearchAgentUseCase(primary_scraper=primary, fallback_scraper=None, memory_store=memory_store)

    result = use_case.discover(["https://www.aaro.mil/reports/2023.pdf"])

    assert result.documents == []
    assert result.discarded == []
    assert primary.fetched_urls == []  # dedup happens before extraction


def test_extracts_a_new_allowed_document_via_the_primary_scraper(tmp_path):
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    url = "https://www.aaro.mil/reports/2024.pdf"
    primary = FakeScraper({url: _document()})
    use_case = ResearchAgentUseCase(primary_scraper=primary, fallback_scraper=None, memory_store=memory_store)

    result = use_case.discover([url])

    assert len(result.documents) == 1
    assert result.documents[0].extracted_text == "Full text exactly as extracted, no rewriting."


def test_falls_back_to_the_secondary_scraper_when_the_primary_fails(tmp_path):
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    url = "https://www.cia.gov/readingroom/some-case"
    primary = FakeScraper({})  # returns None for every url
    fallback = FakeScraper({url: _document(extraction_confidence="alta")})
    use_case = ResearchAgentUseCase(primary_scraper=primary, fallback_scraper=fallback, memory_store=memory_store)

    result = use_case.discover([url])

    assert primary.fetched_urls == [url]
    assert fallback.fetched_urls == [url]
    assert len(result.documents) == 1
    assert result.documents[0].extraction_confidence == "alta"


def test_discards_and_reports_when_both_scrapers_fail(tmp_path):
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    url = "https://www.archives.gov/some-record"
    primary = FakeScraper({})
    fallback = FakeScraper({})
    use_case = ResearchAgentUseCase(primary_scraper=primary, fallback_scraper=fallback, memory_store=memory_store)

    result = use_case.discover([url])

    assert result.documents == []
    assert len(result.discarded) == 1
    assert result.discarded[0].source_url == url


def test_does_not_alter_the_extracted_text_of_a_discovered_document(tmp_path):
    """Requirement: the research agent does not interpret or write content
    — it must pass through exactly what the scraper extracted."""
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    url = "https://www.aaro.mil/reports/2024.pdf"
    original_text = "The pilot reported an unidentified radar contact at 0200 hours."
    primary = FakeScraper({url: _document(extracted_text=original_text)})
    use_case = ResearchAgentUseCase(primary_scraper=primary, fallback_scraper=None, memory_store=memory_store)

    result = use_case.discover([url])

    assert result.documents[0].extracted_text == original_text


def test_with_a_query_and_both_scrapers_configured_the_fallback_is_tried_first_and_wins(tmp_path):
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    url = "https://www.aaro.mil/reports/2024.pdf"
    call_log: list[str] = []
    primary = FakeScraper({url: _document()}, call_log=call_log, name="primary")
    fallback = FakeScraper({url: _document(extraction_confidence="alta")}, call_log=call_log, name="fallback")
    use_case = ResearchAgentUseCase(primary_scraper=primary, fallback_scraper=fallback, memory_store=memory_store)

    result = use_case.discover([url], query="missile silo incidents")

    assert call_log == ["fallback"]  # fallback alone satisfied it; primary never tried
    assert fallback.fetched_urls == [url]
    assert fallback.fetched_queries == ["missile silo incidents"]
    assert primary.fetched_urls == []
    assert len(result.documents) == 1
    assert result.documents[0].extraction_confidence == "alta"


def test_with_a_query_the_primary_is_tried_only_after_the_fallback_returns_none(tmp_path):
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    url = "https://www.aaro.mil/reports/2024.pdf"
    call_log: list[str] = []
    fallback = FakeScraper({}, call_log=call_log, name="fallback")  # returns None for every url
    primary = FakeScraper({url: _document()}, call_log=call_log, name="primary")
    use_case = ResearchAgentUseCase(primary_scraper=primary, fallback_scraper=fallback, memory_store=memory_store)

    result = use_case.discover([url], query="missile silo incidents")

    assert call_log == ["fallback", "primary"]
    assert fallback.fetched_queries == ["missile silo incidents"]
    assert primary.fetched_urls == [url]
    assert primary.fetched_queries == ["missile silo incidents"]
    assert len(result.documents) == 1


def test_with_a_query_but_no_fallback_scraper_the_primary_is_used_and_receives_the_query(tmp_path):
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    url = "https://www.aaro.mil/reports/2024.pdf"
    primary = FakeScraper({url: _document()})
    use_case = ResearchAgentUseCase(primary_scraper=primary, fallback_scraper=None, memory_store=memory_store)

    result = use_case.discover([url], query="missile silo incidents")

    assert primary.fetched_urls == [url]
    assert primary.fetched_queries == ["missile silo incidents"]
    assert len(result.documents) == 1


def test_with_no_query_the_default_primary_then_fallback_order_is_unchanged(tmp_path):
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    url = "https://www.cia.gov/readingroom/some-case"
    call_log: list[str] = []
    primary = FakeScraper({}, call_log=call_log, name="primary")  # returns None -> triggers fallback
    fallback = FakeScraper({url: _document()}, call_log=call_log, name="fallback")
    use_case = ResearchAgentUseCase(primary_scraper=primary, fallback_scraper=fallback, memory_store=memory_store)

    result = use_case.discover([url])  # query omitted entirely

    assert call_log == ["primary", "fallback"]  # unchanged from today
    assert primary.fetched_queries == [None]
    assert fallback.fetched_queries == [None]
    assert len(result.documents) == 1
