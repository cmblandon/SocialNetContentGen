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
from src.editorial.application.research_agent_use_case import ResearchAgentUseCase
from src.editorial.core.ports import ScrapedDocument
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore


class FakeScraper:
    def __init__(self, documents_by_url: dict):
        self._documents_by_url = documents_by_url
        self.fetched_urls: list[str] = []

    def fetch(self, source_url: str):
        self.fetched_urls.append(source_url)
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
