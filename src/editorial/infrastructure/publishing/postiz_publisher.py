"""
PostizPublisherAdapter — the default ISocialPublisher implementation
(design.md Decision 7: Postiz self-hosted first). Raw HTTP via an
injectable client, mirroring the Phase 4 scraper adapters.

Never raises: any failure (non-200 response, network error) is converted
into PublishResult(success=False, ...) so PublishingUseCase can record it
as a failed attempt rather than crashing.

Note: the request/response shape below is a good-faith approximation of
Postiz's public API — verify the exact wire format against Postiz's
current API reference before pointing this at a real self-hosted instance.
"""
from datetime import datetime
from typing import Optional

import httpx

from src.editorial.core.ports import PublishResult

DEFAULT_TIMEOUT_SECONDS = 30


class PostizPublisherAdapter:
    def __init__(self, api_key: str, base_url: str, client: Optional[httpx.Client] = None):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client()

    def publish(
        self, platform: str, content: str, scheduled_at: Optional[datetime] = None
    ) -> PublishResult:
        payload = {
            "integration": platform,
            "content": content,
            "type": "schedule" if scheduled_at is not None else "now",
        }
        if scheduled_at is not None:
            payload["date"] = scheduled_at.isoformat()

        try:
            response = self._client.post(
                f"{self._base_url}/api/posts",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
        except Exception as error:  # noqa: BLE001 - any transport failure is a publish failure
            return PublishResult(success=False, error_message=str(error))

        if response.status_code != 200:
            return PublishResult(
                success=False,
                error_message=f"Postiz returned HTTP {response.status_code}",
            )

        return PublishResult(success=True, external_post_id=response.json().get("id"))
