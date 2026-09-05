"""
JinaScraperAdapter — the default ISourceScraper implementation (design.md
Decision 7). Jina AI Reader (https://r.jina.ai/<url>) returns readable
text/markdown, not structured metadata, so this adapter's job is limited
to lightweight, honest parsing: a best-effort title, the raw body as
extracted_text, and doc_type inferred from the URL. It never speculates
about content it can't read — a poorly-OCR'd source is passed through with
extraction_confidence="baja" rather than embellished.
"""
from typing import Optional

import httpx

from src.editorial.core.ports import ScrapedDocument
from src.editorial.infrastructure.scraping.doc_type import infer_doc_type_from_url

JINA_READER_BASE_URL = "https://r.jina.ai/"
DEFAULT_TIMEOUT_SECONDS = 30


class JinaScraperAdapter:
    def __init__(self, api_key: str = "", client: Optional[httpx.Client] = None):
        self._api_key = api_key
        self._client = client or httpx.Client()

    def fetch(self, source_url: str) -> Optional[ScrapedDocument]:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

        response = self._client.get(
            f"{JINA_READER_BASE_URL}{source_url}",
            headers=headers,
            timeout=DEFAULT_TIMEOUT_SECONDS,
        )

        if response.status_code != 200:
            return None

        body = response.text
        if not body.strip():
            return None

        return ScrapedDocument(
            title=self._extract_title(body, source_url),
            agency="",
            doc_type=infer_doc_type_from_url(source_url),
            extracted_text=body,
            source_url=source_url,
            extraction_confidence="baja",
        )

    def _extract_title(self, body: str, source_url: str) -> str:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        return source_url.rstrip("/").rsplit("/", maxsplit=1)[-1]
