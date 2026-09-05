"""
Tests for PostizPublisherAdapter — the default ISocialPublisher
implementation (design.md Decision 7: Postiz self-hosted first). Raw HTTP
via an injectable client, mirroring the Phase 4 scraper adapters.

Note: the request/response shape here is a good-faith approximation of
Postiz's public API, not verified against live docs in this session —
confirm the exact wire format against Postiz's current API reference
before pointing this at a real self-hosted instance.
"""
from datetime import datetime, timezone

from src.editorial.core.ports import PublishResult
from src.editorial.infrastructure.publishing.postiz_publisher import (
    PostizPublisherAdapter,
)


class FakeResponse:
    def __init__(self, status_code: int, json_body: dict | None = None):
        self.status_code = status_code
        self._json_body = json_body or {}

    def json(self):
        return self._json_body


class FakeHttpClient:
    def __init__(self, response=None, exception=None):
        self._response = response
        self._exception = exception
        self.last_url = None
        self.last_json = None
        self.last_headers = None

    def post(self, url, json=None, headers=None, timeout=None):
        self.last_url = url
        self.last_json = json
        self.last_headers = headers
        if self._exception is not None:
            raise self._exception
        return self._response


def test_publish_returns_success_result_with_post_id():
    client = FakeHttpClient(response=FakeResponse(200, {"id": "postiz-post-123"}))
    adapter = PostizPublisherAdapter(api_key="test-key", base_url="https://postiz.example.com", client=client)

    result = adapter.publish(platform="tiktok", content="hook + script", scheduled_at=None)

    assert isinstance(result, PublishResult)
    assert result.success is True
    assert result.external_post_id == "postiz-post-123"
    assert result.error_message is None


def test_publish_sends_platform_content_and_auth_header():
    client = FakeHttpClient(response=FakeResponse(200, {"id": "post-1"}))
    adapter = PostizPublisherAdapter(api_key="test-key", base_url="https://postiz.example.com", client=client)

    adapter.publish(platform="x", content="thread content", scheduled_at=None)

    assert client.last_json["integration"] == "x"
    assert client.last_json["content"] == "thread content"
    assert client.last_headers["Authorization"] == "Bearer test-key"


def test_publish_includes_the_scheduled_time_when_given():
    client = FakeHttpClient(response=FakeResponse(200, {"id": "post-1"}))
    adapter = PostizPublisherAdapter(api_key="test-key", base_url="https://postiz.example.com", client=client)
    scheduled_at = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)

    adapter.publish(platform="tiktok", content="c", scheduled_at=scheduled_at)

    assert client.last_json["date"] == scheduled_at.isoformat()
    assert client.last_json["type"] == "schedule"


def test_publish_marks_as_immediate_when_no_scheduled_time_given():
    client = FakeHttpClient(response=FakeResponse(200, {"id": "post-1"}))
    adapter = PostizPublisherAdapter(api_key="test-key", base_url="https://postiz.example.com", client=client)

    adapter.publish(platform="tiktok", content="c", scheduled_at=None)

    assert client.last_json["type"] == "now"
    assert "date" not in client.last_json


def test_publish_returns_failure_result_on_non_200_response():
    client = FakeHttpClient(response=FakeResponse(500, {}))
    adapter = PostizPublisherAdapter(api_key="test-key", base_url="https://postiz.example.com", client=client)

    result = adapter.publish(platform="tiktok", content="c", scheduled_at=None)

    assert result.success is False
    assert result.external_post_id is None
    assert result.error_message is not None


def test_publish_returns_failure_result_on_connection_error_without_raising():
    client = FakeHttpClient(exception=ConnectionError("network unreachable"))
    adapter = PostizPublisherAdapter(api_key="test-key", base_url="https://postiz.example.com", client=client)

    result = adapter.publish(platform="tiktok", content="c", scheduled_at=None)

    assert result.success is False
    assert "network unreachable" in result.error_message
