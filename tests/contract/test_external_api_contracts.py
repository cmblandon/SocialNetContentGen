"""
Contract tests for the ElevenLabs and Unsplash adapters (tasks 6.6, 9.6).

These replace the originally-planned "integration tests against the real
APIs". Calling paid third-party services from an automated suite is
non-deterministic, costs money on every run, needs production credentials in
CI, and fails when someone else's service is down.

The risk those tasks were aimed at is real, though: our adapters parse
payloads we wrote by hand from documentation, and a hand-written fake cannot
catch a mis-read field. So these drive the adapters' *real* request path —
httpx, URL construction, headers, status handling — against recorded response
shapes, using httpx.MockTransport rather than patching the client's methods.
That catches reading `urls.full` instead of `urls.regular`, forgetting the
Client-ID header, or treating an empty result set as an error.

FIXTURE PROVENANCE — and its limit. The payloads below are built from each
provider's published response schema, not captured from a live call. Nothing
in this repo calls the real APIs, by choice: automated or scripted calls to
paid third-party services are non-deterministic and cost money.

The cost of that choice is worth stating plainly: if ElevenLabs or Unsplash
renames a field, these tests still pass and production still breaks. That
gap closes the first time someone runs the feature with real credentials, not
in CI. If you do, and a payload differs from what is recorded here, update
these fixtures — they are the closest thing to a spec for what we expect
back.
"""
import json
from pathlib import Path

import httpx
import pytest

from src.editorial.core.exceptions import StoryGenerationError
from src.editorial.infrastructure.external.elevenlabs_client import (
    ElevenLabsTextToSpeechClient,
)
from src.editorial.infrastructure.external.unsplash_client import UnsplashImageClient

# --- Recorded response shapes ------------------------------------------------

# GET https://api.unsplash.com/search/photos
UNSPLASH_SEARCH_HIT = {
    "total": 133,
    "total_pages": 133,
    "results": [
        {
            "id": "eOLpJytrbsQ",
            "created_at": "2014-11-18T14:35:36-05:00",
            "width": 4000,
            "height": 3000,
            "color": "#A7A2A1",
            "blur_hash": "LaLXMa9Fx[D%~q%MtQM|kDRjtRIU",
            "likes": 286,
            "description": "A military radar installation at dusk",
            "urls": {
                "raw": "https://images.unsplash.com/photo-1?ixid=raw",
                "full": "https://images.unsplash.com/photo-1?ixid=full",
                "regular": "https://images.unsplash.com/photo-1?ixid=regular&w=1080",
                "small": "https://images.unsplash.com/photo-1?ixid=small&w=400",
                "thumb": "https://images.unsplash.com/photo-1?ixid=thumb&w=200",
            },
            "links": {
                "self": "https://api.unsplash.com/photos/eOLpJytrbsQ",
                "html": "https://unsplash.com/photos/eOLpJytrbsQ",
                "download": "https://unsplash.com/photos/eOLpJytrbsQ/download",
            },
            "user": {"id": "Ul0QVz12Goo", "username": "ugmonk", "name": "Jeff Sheldon"},
        }
    ],
}

UNSPLASH_SEARCH_EMPTY = {"total": 0, "total_pages": 0, "results": []}

# Unsplash returns 403 for both a bad key and an exhausted rate limit.
UNSPLASH_RATE_LIMITED = {"errors": ["Rate Limit Exceeded"]}

# POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id} returns raw
# audio bytes, not JSON. Errors come back as JSON with a `detail` object.
ELEVENLABS_AUDIO_BYTES = b"ID3\x04\x00\x00\x00\x00\x00\x00fake-mp3-frames"
ELEVENLABS_QUOTA_ERROR = {
    "detail": {
        "status": "quota_exceeded",
        "message": "You have exceeded your current quota.",
    }
}


def transport_returning(*responses: httpx.Response) -> httpx.MockTransport:
    """Replay the given responses in order, recording the requests made."""
    calls: list[httpx.Request] = []
    remaining = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    transport = httpx.MockTransport(handler)
    transport.calls = calls  # type: ignore[attr-defined]
    return transport


# --- Unsplash ----------------------------------------------------------------


def test_unsplash_search_reads_the_regular_url_from_a_real_payload(tmp_path):
    """`regular` is the 1080px render; `full` and `raw` are far too large."""
    transport = transport_returning(httpx.Response(200, json=UNSPLASH_SEARCH_HIT))
    client = UnsplashImageClient(
        access_key="key", cache_dir=tmp_path, transport=transport
    )

    url = client.search_image("archival footage of military radar")

    assert url == "https://images.unsplash.com/photo-1?ixid=regular&w=1080"


def test_unsplash_search_sends_the_documented_request(tmp_path):
    transport = transport_returning(httpx.Response(200, json=UNSPLASH_SEARCH_HIT))
    client = UnsplashImageClient(
        access_key="secret-key", cache_dir=tmp_path, transport=transport
    )

    client.search_image("military radar")

    request = transport.calls[0]  # type: ignore[attr-defined]
    assert request.url.path == "/search/photos"
    assert request.url.params["query"] == "military radar"
    assert request.url.params["per_page"] == "1"
    # Unsplash authenticates with this exact scheme, not a Bearer token.
    assert request.headers["Authorization"] == "Client-ID secret-key"


def test_unsplash_empty_results_are_not_an_error(tmp_path):
    """No match is a normal outcome that triggers the colour+text fallback."""
    transport = transport_returning(httpx.Response(200, json=UNSPLASH_SEARCH_EMPTY))
    client = UnsplashImageClient(
        access_key="key", cache_dir=tmp_path, transport=transport
    )

    assert client.search_image("something with no photos") is None


def test_unsplash_rate_limit_degrades_to_the_fallback(tmp_path):
    """403 covers both a bad key and an exhausted hourly limit."""
    transport = transport_returning(
        httpx.Response(403, json=UNSPLASH_RATE_LIMITED)
    )
    client = UnsplashImageClient(
        access_key="key", cache_dir=tmp_path, transport=transport
    )

    assert client.search_image("military radar") is None


def test_unsplash_caches_the_hit_and_stops_calling_out(tmp_path):
    transport = transport_returning(httpx.Response(200, json=UNSPLASH_SEARCH_HIT))
    client = UnsplashImageClient(
        access_key="key", cache_dir=tmp_path, transport=transport
    )

    first = client.search_image("military radar")
    second = client.search_image("military radar")

    assert first == second
    assert len(transport.calls) == 1  # type: ignore[attr-defined]


def test_unsplash_download_writes_the_body_and_follows_redirects(tmp_path):
    """Unsplash image URLs redirect to a CDN host."""
    transport = transport_returning(httpx.Response(200, content=b"\xff\xd8jpeg-bytes"))
    client = UnsplashImageClient(
        access_key="key", cache_dir=tmp_path, transport=transport
    )
    destination = tmp_path / "visual.jpg"

    client.download_image("https://images.unsplash.com/photo-1", str(destination))

    assert destination.read_bytes() == b"\xff\xd8jpeg-bytes"


def test_unsplash_download_failure_is_raised_not_swallowed(tmp_path):
    """Unlike search, a failed download is a real error: the caller asked for
    a specific file that it believed existed."""
    transport = transport_returning(httpx.Response(404, text="Not Found"))
    client = UnsplashImageClient(
        access_key="key", cache_dir=tmp_path, transport=transport
    )

    with pytest.raises(StoryGenerationError, match="Failed to download image"):
        client.download_image("https://images.unsplash.com/gone", str(tmp_path / "x.jpg"))


# --- ElevenLabs --------------------------------------------------------------


def _tts_client(transport: httpx.MockTransport) -> ElevenLabsTextToSpeechClient:
    return ElevenLabsTextToSpeechClient(
        api_key="secret-key",
        spanish_voice_id="es-voice-id",
        english_voice_id="en-voice-id",
        transport=transport,
    )


def test_elevenlabs_writes_the_raw_audio_body(tmp_path, monkeypatch):
    """The response body IS the mp3 — there is no JSON envelope to unwrap."""
    monkeypatch.setattr(
        "src.editorial.infrastructure.external.elevenlabs_client.probe_duration_ms",
        lambda path: 4000,
    )
    transport = transport_returning(
        httpx.Response(200, content=ELEVENLABS_AUDIO_BYTES)
    )
    destination = tmp_path / "narration.mp3"

    duration = _tts_client(transport).generate_speech("Hola.", "es", str(destination))

    assert destination.read_bytes() == ELEVENLABS_AUDIO_BYTES
    assert duration == 4000


def test_elevenlabs_sends_the_documented_request(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.editorial.infrastructure.external.elevenlabs_client.probe_duration_ms",
        lambda path: 4000,
    )
    transport = transport_returning(
        httpx.Response(200, content=ELEVENLABS_AUDIO_BYTES)
    )

    _tts_client(transport).generate_speech("Hola mundo.", "es", str(tmp_path / "a.mp3"))

    request = transport.calls[0]  # type: ignore[attr-defined]
    # The voice id is part of the path, so a language routing bug shows here.
    assert request.url.path == "/v1/text-to-speech/es-voice-id"
    # ElevenLabs authenticates with this header, not Authorization.
    assert request.headers["xi-api-key"] == "secret-key"
    assert json.loads(request.content)["text"] == "Hola mundo."


def test_elevenlabs_routes_english_to_the_english_voice(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.editorial.infrastructure.external.elevenlabs_client.probe_duration_ms",
        lambda path: 4000,
    )
    transport = transport_returning(
        httpx.Response(200, content=ELEVENLABS_AUDIO_BYTES)
    )

    _tts_client(transport).generate_speech("Hello.", "en", str(tmp_path / "a.mp3"))

    assert transport.calls[0].url.path == "/v1/text-to-speech/en-voice-id"  # type: ignore[attr-defined]


def test_elevenlabs_quota_exhaustion_surfaces_as_a_generation_error(tmp_path):
    """The pipeline records this on the row and the retry endpoint clears it."""
    transport = transport_returning(httpx.Response(401, json=ELEVENLABS_QUOTA_ERROR))

    with pytest.raises(StoryGenerationError, match="ElevenLabs TTS request failed"):
        _tts_client(transport).generate_speech("Hola.", "es", str(tmp_path / "a.mp3"))


def test_elevenlabs_server_error_does_not_leave_a_partial_file(tmp_path):
    transport = transport_returning(httpx.Response(500, text="Internal Server Error"))
    destination = tmp_path / "narration.mp3"

    with pytest.raises(StoryGenerationError):
        _tts_client(transport).generate_speech("Hola.", "es", str(destination))

    assert not destination.exists()
