"""
Structural conformance tests for the editorial ports (design.md Decision 7).

These ports are declared @runtime_checkable so conformance can be verified
with isinstance() against both a conforming fake and a non-conforming one,
without either fake needing to inherit from the Protocol.
"""
from src.editorial.core.ports import (
    IImageClient,
    ILLMClient,
    ISocialPublisher,
    ISourceScraper,
    ITextToSpeechClient,
    IVideoCompositor,
    PublishResult,
    ScrapedDocument,
)


class FakeScraper:
    def fetch(self, source_url: str):
        return None


class IncompleteScraper:
    """Deliberately missing fetch() — must NOT satisfy ISourceScraper."""


def test_conforming_scraper_satisfies_protocol():
    assert isinstance(FakeScraper(), ISourceScraper)


def test_non_conforming_object_does_not_satisfy_scraper_protocol():
    assert not isinstance(IncompleteScraper(), ISourceScraper)


class FakePublisher:
    def publish(self, platform, content, scheduled_at=None):
        return PublishResult(success=True, external_post_id="123")


def test_conforming_publisher_satisfies_protocol():
    assert isinstance(FakePublisher(), ISocialPublisher)


def test_non_conforming_object_does_not_satisfy_publisher_protocol():
    assert not isinstance(object(), ISocialPublisher)


class FakeLLMClient:
    def complete(self, prompt: str) -> str:
        return "response"


def test_conforming_llm_client_satisfies_protocol():
    assert isinstance(FakeLLMClient(), ILLMClient)


def test_non_conforming_object_does_not_satisfy_llm_client_protocol():
    assert not isinstance(object(), ILLMClient)


class FakeTextToSpeechClient:
    def generate_speech(self, text: str, language: str, output_path: str) -> int:
        return 1000

    def get_audio_duration(self, audio_path: str) -> int:
        return 1000


class PartialTextToSpeechClient:
    """Has generate_speech but not get_audio_duration — the retry path calls
    the latter, so a half-implemented client must not satisfy the port."""

    def generate_speech(self, text: str, language: str, output_path: str) -> int:
        return 1000


def test_conforming_tts_client_satisfies_protocol():
    assert isinstance(FakeTextToSpeechClient(), ITextToSpeechClient)


def test_partial_tts_client_does_not_satisfy_protocol():
    assert not isinstance(PartialTextToSpeechClient(), ITextToSpeechClient)


class FakeImageClient:
    def search_image(self, query: str):
        return None

    def download_image(self, url: str, output_path: str) -> None:
        return None

    def create_fallback_image(self, text: str, output_path: str) -> None:
        return None


class PartialImageClient:
    """Missing create_fallback_image — the fallback is what guarantees a
    video is always producible, so this must not pass as an image client."""

    def search_image(self, query: str):
        return None

    def download_image(self, url: str, output_path: str) -> None:
        return None


def test_conforming_image_client_satisfies_protocol():
    assert isinstance(FakeImageClient(), IImageClient)


def test_partial_image_client_does_not_satisfy_protocol():
    assert not isinstance(PartialImageClient(), IImageClient)


class FakeCompositor:
    def composite(
        self, audio_path, visual_path, subtitle_path, output_path, duration_seconds=None
    ) -> None:
        return None


def test_conforming_compositor_satisfies_protocol():
    assert isinstance(FakeCompositor(), IVideoCompositor)


def test_non_conforming_object_does_not_satisfy_compositor_protocol():
    assert not isinstance(object(), IVideoCompositor)


class PartialLLMClient:
    """Has no complete() — must NOT satisfy ILLMClient. A curation provider
    that swaps in a half-implemented client would otherwise fail only at the
    first real document."""

    def generate(self, prompt: str) -> str:
        return ""


def test_partial_llm_client_does_not_satisfy_protocol():
    assert not isinstance(PartialLLMClient(), ILLMClient)


def test_ollama_adapter_satisfies_the_llm_port():
    from src.editorial.infrastructure.llm.ollama_llm_client import OllamaLLMClient

    assert isinstance(OllamaLLMClient(), ILLMClient)


def test_real_adapters_satisfy_their_ports(tmp_path):
    """The shipped adapters, not just the fakes, conform structurally."""
    from src.editorial.infrastructure.external.elevenlabs_client import (
        ElevenLabsTextToSpeechClient,
    )
    from src.editorial.infrastructure.external.unsplash_client import UnsplashImageClient
    from src.editorial.infrastructure.video.ffmpeg_compositor import FFmpegCompositor

    tts = ElevenLabsTextToSpeechClient(
        api_key="key", spanish_voice_id="es", english_voice_id="en"
    )
    assert isinstance(tts, ITextToSpeechClient)
    # cache_dir is tmp-scoped: the client mkdirs it on construction, and a
    # test must not create directories under the real data/ tree.
    assert isinstance(UnsplashImageClient(cache_dir=tmp_path / "unsplash"), IImageClient)
    assert isinstance(FFmpegCompositor(), IVideoCompositor)


def test_scraped_document_holds_required_research_agent_fields():
    """Requirement per specs/research-agent: title, agency, doc type, and
    extracted text/summary are mandatory; date/url/confidence are optional."""
    document = ScrapedDocument(
        title="AARO 2024 Annual Report",
        agency="AARO",
        doc_type="report",
        extracted_text="Full text.",
    )

    assert document.published_date is None
    assert document.source_url is None
    assert document.extraction_confidence is None


def test_publish_result_carries_error_without_a_post_id_on_failure():
    """Requirement per specs/publishing: a failed publish attempt must be
    reportable without fabricating a post id."""
    result = PublishResult(success=False, error_message="account limit reached")

    assert result.external_post_id is None
    assert result.error_message == "account limit reached"
