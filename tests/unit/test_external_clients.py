"""
Tests for external service clients: ElevenLabs TTS and Unsplash images.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.editorial.core.exceptions import StoryGenerationError
from src.editorial.infrastructure.external.elevenlabs_client import ElevenLabsTextToSpeechClient
from src.editorial.infrastructure.external.unsplash_client import UnsplashImageClient


class TestElevenLabsTextToSpeechClient:
    """Tests for ElevenLabs TTS client."""

    def test_raises_when_api_key_missing(self):
        """Test that missing API key raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(StoryGenerationError, match="ELEVENLABS_API_KEY"):
                ElevenLabsTextToSpeechClient()

    def test_raises_when_voice_ids_missing(self):
        """Test that missing voice IDs raise error."""
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key"}, clear=True):
            with pytest.raises(
                StoryGenerationError, match="ELEVENLABS_SPANISH_VOICE_ID"
            ):
                ElevenLabsTextToSpeechClient()

    def test_initializes_with_all_env_vars(self):
        """Test initialization with environment variables."""
        env_vars = {
            "ELEVENLABS_API_KEY": "test-key",
            "ELEVENLABS_SPANISH_VOICE_ID": "es-voice-123",
            "ELEVENLABS_ENGLISH_VOICE_ID": "en-voice-456",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            client = ElevenLabsTextToSpeechClient()
            assert client.api_key == "test-key"
            assert client.spanish_voice_id == "es-voice-123"
            assert client.english_voice_id == "en-voice-456"

    def test_initializes_with_constructor_args(self):
        """Test initialization with constructor arguments."""
        client = ElevenLabsTextToSpeechClient(
            api_key="key",
            spanish_voice_id="es-id",
            english_voice_id="en-id",
        )
        assert client.api_key == "key"
        assert client.spanish_voice_id == "es-id"
        assert client.english_voice_id == "en-id"

    def test_close_releases_the_connection_pool(self):
        client = ElevenLabsTextToSpeechClient(
            api_key="key", spanish_voice_id="es", english_voice_id="en"
        )
        assert client._client.is_closed is False

        client.close()

        assert client._client.is_closed is True

    def test_works_as_a_context_manager(self):
        with ElevenLabsTextToSpeechClient(
            api_key="key", spanish_voice_id="es", english_voice_id="en"
        ) as client:
            inner = client._client
            assert inner.is_closed is False
        assert inner.is_closed is True

    def test_request_timeout_is_bounded(self):
        """Without a timeout a hung TTS call strands a generation at PENDING."""
        client = ElevenLabsTextToSpeechClient(
            api_key="key", spanish_voice_id="es", english_voice_id="en"
        )
        assert client._client.timeout.read is not None

    def test_get_audio_duration_measures_the_file(self):
        """Duration comes from ffprobe, not from a text-length estimate."""
        client = ElevenLabsTextToSpeechClient(
            api_key="key",
            spanish_voice_id="es-id",
            english_voice_id="en-id",
        )
        with patch(
            "src.editorial.infrastructure.external.elevenlabs_client.probe_duration_ms",
            return_value=4321,
        ) as probe:
            assert client.get_audio_duration("/tmp/audio.mp3") == 4321
        probe.assert_called_once_with("/tmp/audio.mp3")

    def test_generate_speech_returns_measured_duration(self):
        """generate_speech reports the written file's real duration."""
        client = ElevenLabsTextToSpeechClient(
            api_key="key",
            spanish_voice_id="es-id",
            english_voice_id="en-id",
        )

        response = MagicMock()
        response.content = b"fake-mp3-bytes"
        response.raise_for_status = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "out.mp3")
            with patch.object(client._client, "post", return_value=response):
                with patch(
                    "src.editorial.infrastructure.external.elevenlabs_client.probe_duration_ms",
                    return_value=7500,
                ):
                    duration = client.generate_speech("hola", "es", output_path)

            assert duration == 7500
            assert Path(output_path).read_bytes() == b"fake-mp3-bytes"

    def test_get_voice_id_spanish(self):
        """Test voice ID retrieval for Spanish."""
        client = ElevenLabsTextToSpeechClient(
            api_key="key",
            spanish_voice_id="es-voice",
            english_voice_id="en-voice",
        )
        assert client._get_voice_id("es") == "es-voice"

    def test_get_voice_id_english(self):
        """Test voice ID retrieval for English."""
        client = ElevenLabsTextToSpeechClient(
            api_key="key",
            spanish_voice_id="es-voice",
            english_voice_id="en-voice",
        )
        assert client._get_voice_id("en") == "en-voice"

    def test_raises_for_unsupported_language(self):
        """Test that unsupported language raises error."""
        client = ElevenLabsTextToSpeechClient(
            api_key="key",
            spanish_voice_id="es-voice",
            english_voice_id="en-voice",
        )
        with pytest.raises(StoryGenerationError, match="Unsupported language"):
            client._get_voice_id("fr")


class TestUnsplashImageClient:
    """Tests for Unsplash image client."""

    def test_initializes_with_cache_dir(self):
        """Test initialization creates cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            client = UnsplashImageClient(cache_dir=cache_dir)
            assert cache_dir.exists()

    def test_search_returns_none_without_api_key(self):
        """Test that search returns None when API key is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = UnsplashImageClient(access_key=None, cache_dir=Path(tmpdir))
            result = client.search_image("test query")
            assert result is None

    def test_caches_search_result(self):
        """Test that search results are cached."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = UnsplashImageClient(
                access_key="test-key",
                cache_dir=Path(tmpdir),
            )

            # Manually cache a URL
            query = "radar"
            url = "https://images.unsplash.com/photo-123"
            client._cache_url(query, url)

            # Retrieve from cache
            cached = client._get_cached_url(query)
            assert cached == url

    def test_wrap_text_single_line(self):
        """Test text wrapping for short text."""
        text = "Hello world"
        wrapped = UnsplashImageClient._wrap_text(text, 50)
        assert len(wrapped) == 1
        assert wrapped[0] == "Hello world"

    def test_wrap_text_multiple_lines(self):
        """Test text wrapping for long text."""
        text = "This is a longer sentence that should be wrapped across multiple lines"
        wrapped = UnsplashImageClient._wrap_text(text, 20)
        assert len(wrapped) > 1
        # Each line should not exceed width
        for line in wrapped:
            assert len(line) <= 25  # Add some buffer

    @pytest.mark.skipif(
        __import__("importlib.util").util.find_spec("PIL") is None,
        reason="Pillow not installed - this test requires it",
    )
    def test_create_fallback_image_error_handling(self):
        """Test fallback image creation error handling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = UnsplashImageClient(cache_dir=Path(tmpdir))
            # Use invalid path to trigger error
            with pytest.raises(StoryGenerationError, match="Failed to create fallback image"):
                client.create_fallback_image("test", "/invalid/path/image.jpg")

    @pytest.mark.skipif(
        not __import__("importlib.util").util.find_spec("PIL"),
        reason="Pillow not installed",
    )
    def test_create_fallback_image_with_pillow(self):
        """Test fallback image creation when Pillow is available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "fallback.jpg")
            client = UnsplashImageClient(cache_dir=Path(tmpdir))

            client.create_fallback_image("Fallback Image Text", output_path)

            # Verify file was created
            assert Path(output_path).exists()
            assert Path(output_path).stat().st_size > 0
