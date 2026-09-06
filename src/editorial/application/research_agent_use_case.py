"""
ResearchAgentUseCase — per specs/research-agent/spec.md.

Processes a list of candidate source URLs (already identified by the
operator, or a future listing step — autonomous crawling of a source's
listing pages is out of scope here, see the test module's docstring):
enforces the official-source allowlist, dedups against
/casos_cubiertos.md before ever fetching, and falls back from the primary
scraper to the fallback scraper on failure. Never interprets or rewrites
what a scraper extracted.

research-query-scoping (design.md Decision 2): discover() accepts an
optional `query`. When one is given and a fallback_scraper is configured,
discover() tries the fallback scraper BEFORE the primary for that call,
because this codebase's only wiring (see get_research_agent() in
presentation/routers/research.py) assumes fallback_scraper is the
query-capable adapter (FirecrawlScraperAdapter) and primary_scraper is not
(JinaScraperAdapter, which accepts but ignores query). This class never
inspects which concrete adapter it was given — the inversion is a plain
boolean decision ("was a query given, and is there a fallback"), not a
capability check. If ResearchAgentUseCase is ever wired with a different
pair of scrapers (e.g. primary/fallback swapped, or a third adapter with
different query support), this ordering heuristic must be revisited — see
design.md's Risks section.
"""
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from src.editorial.core.ports import ISourceScraper, ScrapedDocument
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore

ALLOWED_SOURCE_DOMAINS = (
    "war.gov",
    "cia.gov",
    "archives.gov",
    "aaro.mil",
    "odni.gov",
    "theblackvault.com",
)


@dataclass
class ResearchDiscard:
    source_url: str
    reason: str


@dataclass
class ResearchResult:
    documents: list[ScrapedDocument] = field(default_factory=list)
    discarded: list[ResearchDiscard] = field(default_factory=list)


def _is_allowed_source(source_url: str) -> bool:
    hostname = urlparse(source_url).hostname or ""
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in ALLOWED_SOURCE_DOMAINS)


class ResearchAgentUseCase:
    def __init__(
        self,
        primary_scraper: ISourceScraper,
        fallback_scraper: Optional[ISourceScraper],
        memory_store: ProjectMemoryStore,
    ):
        self._primary_scraper = primary_scraper
        self._fallback_scraper = fallback_scraper
        self._memory_store = memory_store

    def discover(self, source_urls: list[str], query: Optional[str] = None) -> ResearchResult:
        result = ResearchResult()
        already_covered = self._memory_store.read_casos_cubiertos()

        # research-query-scoping (design.md Decision 2): when a query is given
        # and a fallback scraper is configured, try the fallback first — in
        # this codebase's only wiring the fallback slot holds the
        # query-capable adapter (Firecrawl). With no query, or no fallback
        # configured, the order is unchanged from before this change
        # (primary, then fallback).
        if query and self._fallback_scraper is not None:
            first_scraper, second_scraper = self._fallback_scraper, self._primary_scraper
        else:
            first_scraper, second_scraper = self._primary_scraper, self._fallback_scraper

        for source_url in source_urls:
            if not _is_allowed_source(source_url):
                result.discarded.append(
                    ResearchDiscard(source_url, "not an official/verifiable source")
                )
                continue

            if source_url in already_covered:
                continue

            document = first_scraper.fetch(source_url, query=query)
            if document is None and second_scraper is not None:
                document = second_scraper.fetch(source_url, query=query)

            if document is None:
                result.discarded.append(
                    ResearchDiscard(source_url, "inaccessible or unverifiable")
                )
                continue

            result.documents.append(document)

        return result
