"""
FirecrawlScraperAdapter — the fallback ISourceScraper used when Jina fails
on a protected/complex page (design.md Decision 7). Implemented via raw
HTTP against Firecrawl's /v1/extract API rather than the firecrawl-py SDK,
so both scraper adapters share the same lightweight httpx-based shape.

Note: the request/response shape below is a good-faith approximation of
Firecrawl's public /v1/extract API — verify the exact wire format against
Firecrawl's current API reference before pointing this at the real service.
"""
from typing import Optional

import httpx

from src.editorial.core.ports import ScrapedDocument
from src.editorial.infrastructure.scraping.doc_type import infer_doc_type_from_url

FIRECRAWL_EXTRACT_URL = "https://api.firecrawl.dev/v1/extract"
DEFAULT_TIMEOUT_SECONDS = 60


class FirecrawlScraperAdapter:
    def __init__(self, api_key: str, client: Optional[httpx.Client] = None):
        self._api_key = api_key
        self._client = client or httpx.Client()

    def fetch(self, source_url: str) -> Optional[ScrapedDocument]:
        response = self._client.post(
            FIRECRAWL_EXTRACT_URL,
            json={"urls": [source_url]},
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            return None

        body = response.json()
        if not body.get("success"):
            return None

        data = body.get("data", {})
        summary = data.get("summary", "")
        if not summary.strip():
            return None

        return ScrapedDocument(
            title=data.get("title", ""),
            agency=data.get("agency", ""),
            doc_type=data.get("doc_type") or infer_doc_type_from_url(source_url),
            extracted_text=summary,
            source_url=source_url,
            published_date=data.get("published_date"),
            extraction_confidence="alta",
        )
