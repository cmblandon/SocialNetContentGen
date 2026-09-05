"""
ResearchAgentUseCase — per specs/research-agent/spec.md.

Processes a list of candidate source URLs (already identified by the
operator, or a future listing step — autonomous crawling of a source's
listing pages is out of scope here, see the test module's docstring):
enforces the official-source allowlist, dedups against
/casos_cubiertos.md before ever fetching, and falls back from the primary
scraper to the fallback scraper on failure. Never interprets or rewrites
what a scraper extracted.
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

    def discover(self, source_urls: list[str]) -> ResearchResult:
        result = ResearchResult()
        already_covered = self._memory_store.read_casos_cubiertos()

        for source_url in source_urls:
            if not _is_allowed_source(source_url):
                result.discarded.append(
                    ResearchDiscard(source_url, "not an official/verifiable source")
                )
                continue

            if source_url in already_covered:
                continue

            document = self._primary_scraper.fetch(source_url)
            if document is None and self._fallback_scraper is not None:
                document = self._fallback_scraper.fetch(source_url)

            if document is None:
                result.discarded.append(
                    ResearchDiscard(source_url, "inaccessible or unverifiable")
                )
                continue

            result.documents.append(document)

        return result
