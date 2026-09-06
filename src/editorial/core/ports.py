"""
Ports (interfaces/contracts) for the editorial bounded context — "Archivo Desclasificado".

Mirrors the style of src/core/ports.py (typing.Protocol, structural typing):
the editorial core only depends on these abstractions, never on concrete
scraper/publisher/LLM implementations. Declared @runtime_checkable so
conformance can be verified with isinstance() in tests (see design.md,
Decision 7).
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable


@dataclass
class ScrapedDocument:
    """
    Structured record produced by research-agent for one discovered document.
    Mirrors the fields specs/research-agent/spec.md requires: title, agency,
    doc type, and full text/summary are mandatory; the rest are optional
    because not every source exposes them.
    """

    title: str
    agency: str
    doc_type: str
    extracted_text: str
    published_date: Optional[str] = None
    source_url: Optional[str] = None
    extraction_confidence: Optional[str] = None


@runtime_checkable
class ISourceScraper(Protocol):
    """
    Contract for discovering and extracting a document from an official source.
    Implementations: JinaScraperAdapter (default), FirecrawlScraperAdapter (fallback).
    """

    def fetch(self, source_url: str, query: Optional[str] = None) -> Optional[ScrapedDocument]:
        """
        Fetches and extracts a structured record from source_url.
        Returns None when the source is inaccessible, login-protected, or
        cannot be verified as an official/primary source — per
        specs/research-agent/spec.md, this is a discard, not an error.

        `query` (research-query-scoping) is an optional topic/focus hint an
        implementation MAY use to guide extraction toward relevant content
        instead of the whole page — not every implementation supports this
        (e.g. JinaScraperAdapter's reader has no query mode and ignores it).
        """
        ...


@dataclass
class PublishResult:
    """Outcome of one publish/schedule attempt against a social API."""

    success: bool
    external_post_id: Optional[str] = None
    error_message: Optional[str] = None


@runtime_checkable
class ISocialPublisher(Protocol):
    """
    Contract for scheduling/publishing approved content to a social network.
    Implementations: PostizPublisherAdapter (default), Ayrshare/Blotato adapters.
    """

    def publish(
        self, platform: str, content: str, scheduled_at: Optional[datetime] = None
    ) -> PublishResult:
        """
        Publishes or schedules content on the given platform. Never called by
        PublishingUseCase unless the corresponding PlatformVersion.status is
        already APPROVED (see specs/publishing/spec.md).
        """
        ...


@runtime_checkable
class ILLMClient(Protocol):
    """
    Contract for the cloud LLM used by story-writing and platform-adaptation.
    Distinct from src/core/ports.py's ILLMClient (local-MLX depuration): this
    one is a generic text-completion call, since the editorial use cases own
    prompt construction and output validation themselves.
    """

    def complete(self, prompt: str) -> str:
        """Sends prompt to the cloud LLM and returns its raw text response."""
        ...


@runtime_checkable
class ITextToSpeechClient(Protocol):
    """
    Contract for the TTS provider used by video-generation.
    Implementation: ElevenLabsTextToSpeechClient.
    """

    def generate_speech(self, text: str, language: str, output_path: str) -> int:
        """
        Synthesizes `text` in `language` ('es' or 'en') and writes the audio
        to output_path. Returns the audio duration in milliseconds, which
        subtitle timing depends on — so it must be measured from the written
        audio, never estimated from the input text.
        """
        ...

    def get_audio_duration(self, audio_path: str) -> int:
        """
        Returns the measured duration of an existing audio file, in
        milliseconds. Lets a retry re-derive timing from audio a previous
        attempt already synthesized instead of paying for TTS again.
        """
        ...


@runtime_checkable
class IImageClient(Protocol):
    """
    Contract for the visual source used by video-generation. Search returning
    None is a normal outcome (no match, no API key, provider down), not an
    error — the caller falls back to a generated color+text image per
    specs/video-generation-from-script.
    """

    def search_image(self, query: str) -> Optional[str]:
        """Returns a URL for the best match, or None when there is none."""
        ...

    def download_image(self, url: str, output_path: str) -> None:
        """Downloads the image at `url` to output_path."""
        ...

    def create_fallback_image(self, text: str, output_path: str) -> None:
        """Writes a solid-color image with `text` overlaid to output_path."""
        ...


@runtime_checkable
class IVideoCompositor(Protocol):
    """
    Contract for the video assembler used by video-generation.
    Implementation: FFmpegCompositor.
    """

    def composite(
        self,
        audio_path: str,
        visual_path: str,
        subtitle_path: Optional[str],
        output_path: str,
        duration_seconds: Optional[int] = None,
    ) -> None:
        """Assembles audio + visual + subtitles into an MP4 at output_path."""
        ...
