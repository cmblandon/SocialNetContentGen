"""
ElevenLabsTextToSpeechClient — wraps ElevenLabs API for TTS audio generation.

Handles voice selection by language, audio generation, and duration retrieval.
"""
import logging
import os
from typing import Optional

import httpx

from src.editorial.core.exceptions import StoryGenerationError
from src.editorial.infrastructure.video.audio_duration import probe_duration_ms

logger = logging.getLogger("editorial.elevenlabs")


class ElevenLabsTextToSpeechClient:
    """Client for ElevenLabs text-to-speech API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        spanish_voice_id: Optional[str] = None,
        english_voice_id: Optional[str] = None,
        base_url: str = "https://api.elevenlabs.io/v1",
        transport: Optional[httpx.BaseTransport] = None,
    ):
        """
        Initialize ElevenLabs client.

        Args:
            api_key: ElevenLabs API key (defaults to ELEVENLABS_API_KEY env var)
            spanish_voice_id: Voice ID for Spanish (defaults to ELEVENLABS_SPANISH_VOICE_ID env var)
            english_voice_id: Voice ID for English (defaults to ELEVENLABS_ENGLISH_VOICE_ID env var)
            base_url: ElevenLabs API base URL
        """
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise StoryGenerationError(
                "ELEVENLABS_API_KEY not set. Set via environment variable or constructor."
            )

        self.spanish_voice_id: str = (
            spanish_voice_id or os.getenv("ELEVENLABS_SPANISH_VOICE_ID") or ""
        )
        self.english_voice_id: str = english_voice_id or os.getenv("ELEVENLABS_ENGLISH_VOICE_ID") or ""

        if not self.spanish_voice_id or not self.english_voice_id:
            raise StoryGenerationError(
                "Spanish and English voice IDs must be configured. "
                "Set ELEVENLABS_SPANISH_VOICE_ID and ELEVENLABS_ENGLISH_VOICE_ID."
            )

        self.base_url = base_url
        # Timeout is generous because synthesizing a chapter of narration is
        # not fast, but bounded: without one, httpx waits forever and a
        # hung request would strand a generation at PENDING.
        # `transport` is how contract tests drive the real request path —
        # URL building, headers, error handling — instead of patching post().
        self._client = httpx.Client(
            headers={"xi-api-key": self.api_key}, timeout=120.0, transport=transport
        )

    def close(self) -> None:
        """Release the HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> "ElevenLabsTextToSpeechClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def generate_speech(self, text: str, language: str, output_path: str) -> int:
        """
        Generate speech audio from text.

        Args:
            text: Text to convert to speech
            language: Language code ('es' or 'en')
            output_path: Path to save the audio file

        Returns:
            Duration of generated audio in milliseconds

        Raises:
            StoryGenerationError: If API request fails
        """
        voice_id = self._get_voice_id(language)

        try:
            response = self._client.post(
                f"{self.base_url}/text-to-speech/{voice_id}",
                json={
                    "text": text,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
            )
            response.raise_for_status()

            # Save audio file
            audio_data = response.content
            with open(output_path, "wb") as f:
                f.write(audio_data)
            logger.info(
                "ElevenLabs returned %d bytes for voice %s", len(audio_data), voice_id
            )

        except httpx.HTTPError as error:
            logger.error("ElevenLabs TTS request failed for voice %s: %s", voice_id, error)
            raise StoryGenerationError(f"ElevenLabs TTS request failed: {error}") from error

        # Measured from the file just written, not estimated from the text:
        # subtitle timing is built on this number.
        return self.get_audio_duration(output_path)

    def get_audio_duration(self, audio_path: str) -> int:
        """
        Get the measured duration of an audio file in milliseconds.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in milliseconds, as reported by ffprobe

        Raises:
            StoryGenerationError: If the file cannot be measured
        """
        return probe_duration_ms(audio_path)

    def _get_voice_id(self, language: str) -> str:
        """Get voice ID for the given language."""
        if language == "es":
            return self.spanish_voice_id
        elif language == "en":
            return self.english_voice_id
        else:
            raise StoryGenerationError(f"Unsupported language: {language}")

    def __del__(self):
        # Backstop only. __del__ runs at GC's discretion and can fire during
        # interpreter shutdown when httpx's internals are already torn down,
        # so close()/the context manager are the real release path; this just
        # avoids leaking a pool when a caller forgets both.
        client = getattr(self, "_client", None)
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
