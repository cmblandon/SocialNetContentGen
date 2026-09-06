"""
Tests for SubtitleGenerationUseCase — SRT subtitle generation with bilingual support.
"""
import json
import tempfile
from pathlib import Path

import pytest

from src.editorial.application.subtitle_generation_use_case import (
    SubtitleGenerationUseCase,
    _ms_to_srt_time,
)
from src.editorial.core.entities import SubtitleDraft
from src.editorial.core.exceptions import StoryGenerationError


class FakeLLMClient:
    """Mock LLM for testing translation."""

    def __init__(self, translation_map: dict[str, str] | None = None):
        self.translation_map = translation_map or {}
        self.call_count = 0

    def complete(self, prompt: str) -> str:
        self.call_count += 1
        # Simple translation lookup for testing
        for source, target in self.translation_map.items():
            if source in prompt:
                return target
        raise StoryGenerationError("Translation not found in mock")


def test_converts_milliseconds_to_srt_time():
    """Test SRT timecode format conversion."""
    assert _ms_to_srt_time(0) == "00:00:00,000"
    assert _ms_to_srt_time(1000) == "00:00:01,000"
    assert _ms_to_srt_time(61000) == "00:01:01,000"
    assert _ms_to_srt_time(3661000) == "01:01:01,000"
    assert _ms_to_srt_time(1500) == "00:00:01,500"


def test_generates_subtitles_with_correct_timing():
    """Test basic subtitle generation with timing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(FakeLLMClient(), cache_dir=Path(tmpdir))

        script = "First sentence. Second sentence. Third sentence."
        # Total duration: 3000ms for 3 sentences = 1000ms per sentence
        draft = use_case.generate_subtitles(script, "en", audio_duration_ms=3000)

        assert draft.language == "en"
        assert len(draft.subtitle_lines) == 3
        assert draft.subtitle_lines[0].text == "First sentence."
        assert draft.subtitle_lines[0].start_time == "00:00:00,000"
        assert draft.subtitle_lines[0].end_time == "00:00:01,000"
        assert draft.subtitle_lines[1].start_time == "00:00:01,000"
        assert draft.subtitle_lines[1].end_time == "00:00:02,000"
        assert draft.subtitle_lines[2].start_time == "00:00:02,000"
        assert draft.subtitle_lines[2].end_time == "00:00:03,000"


def test_generates_srt_format_correctly():
    """Test SRT file format generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(FakeLLMClient(), cache_dir=Path(tmpdir))

        script = "Hello. World."
        draft = use_case.generate_subtitles(script, "en", audio_duration_ms=2000)
        srt_output = draft.to_srt()

        assert "1\n00:00:00,000 --> 00:00:01,000\nHello." in srt_output
        assert "2\n00:00:01,000 --> 00:00:02,000\nWorld." in srt_output


def test_handles_single_sentence():
    """Test handling of single-sentence scripts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(FakeLLMClient(), cache_dir=Path(tmpdir))

        script = "This is a single sentence."
        draft = use_case.generate_subtitles(script, "es", audio_duration_ms=5000)

        assert len(draft.subtitle_lines) == 1
        assert draft.subtitle_lines[0].text == "This is a single sentence."
        assert draft.subtitle_lines[0].start_time == "00:00:00,000"
        assert draft.subtitle_lines[0].end_time == "00:00:05,000"


def test_allocates_time_in_proportion_to_sentence_length():
    """A long sentence holds the screen longer than a short one."""
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(FakeLLMClient(), cache_dir=Path(tmpdir))

        # 1 word, then 9 words -> a 10th/10ths split of 10000ms.
        script = "Uno. Dos tres cuatro cinco seis siete ocho nueve diez."
        draft = use_case.generate_subtitles(script, "es", audio_duration_ms=10000)

        assert len(draft.subtitle_lines) == 2
        assert draft.subtitle_lines[0].start_time == "00:00:00,000"
        assert draft.subtitle_lines[0].end_time == "00:00:01,000"
        assert draft.subtitle_lines[1].start_time == "00:00:01,000"
        assert draft.subtitle_lines[1].end_time == "00:00:10,000"


def test_subtitles_end_exactly_with_the_audio():
    """Rounding never leaves the last caption short of or past the audio."""
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(FakeLLMClient(), cache_dir=Path(tmpdir))

        # Three sentences over a duration that does not divide evenly.
        script = "Una frase. Otra frase mas larga aqui. Y la tercera."
        draft = use_case.generate_subtitles(script, "es", audio_duration_ms=7777)

        assert draft.subtitle_lines[-1].end_time == "00:00:07,777"


def test_subtitle_lines_are_contiguous():
    """No gaps or overlaps between consecutive captions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(FakeLLMClient(), cache_dir=Path(tmpdir))

        script = "Corta. Una frase intermedia. La ultima frase es bastante mas larga que las otras."
        draft = use_case.generate_subtitles(script, "es", audio_duration_ms=12345)

        for previous, current in zip(draft.subtitle_lines, draft.subtitle_lines[1:]):
            assert previous.end_time == current.start_time


def test_raises_for_unsupported_language():
    """Test that unsupported languages raise an error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(FakeLLMClient(), cache_dir=Path(tmpdir))

        with pytest.raises(StoryGenerationError):
            use_case.generate_subtitles("Some script.", "fr", audio_duration_ms=1000)


def test_raises_for_empty_script():
    """Test that empty scripts raise an error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(FakeLLMClient(), cache_dir=Path(tmpdir))

        with pytest.raises(StoryGenerationError):
            use_case.generate_subtitles("", "en", audio_duration_ms=1000)


def test_translation_from_spanish_to_english():
    """Test translation functionality."""
    translation_map = {
        "Hola mundo.": "Hello world.",
    }
    llm = FakeLLMClient(translation_map)

    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(llm, cache_dir=Path(tmpdir))

        script = "Hola mundo."
        draft = use_case.translate_and_generate_subtitles(
            script, "es", "en", audio_duration_ms=2000
        )

        assert draft.language == "en"
        assert len(draft.subtitle_lines) == 1
        assert "Hello world" in draft.subtitle_lines[0].text


def test_caches_generated_subtitles():
    """Test that subtitles are cached and retrieved from cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        llm = FakeLLMClient()
        use_case = SubtitleGenerationUseCase(llm, cache_dir=Path(tmpdir))

        script = "First. Second."

        # Generate subtitles (should not call LLM)
        draft1 = use_case.generate_subtitles(script, "en", audio_duration_ms=2000)
        assert len(draft1.subtitle_lines) == 2

        # Generate same script again (should use cache)
        draft2 = use_case.generate_subtitles(script, "en", audio_duration_ms=2000)
        assert draft2.subtitle_lines[0].text == draft1.subtitle_lines[0].text

        # Verify cache file exists
        cache_files = list(Path(tmpdir).glob("*.json"))
        assert len(cache_files) == 1


def test_cache_format_is_valid_json():
    """Test that cached data is valid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(FakeLLMClient(), cache_dir=Path(tmpdir))

        script = "Test. Sentence."
        draft = use_case.generate_subtitles(script, "en", audio_duration_ms=2000)

        # Check cache file content
        cache_files = list(Path(tmpdir).glob("*.json"))
        assert len(cache_files) == 1

        with open(cache_files[0]) as f:
            cached_data = json.load(f)

        assert cached_data["language"] == "en"
        assert len(cached_data["subtitle_lines"]) == 2
        assert cached_data["subtitle_lines"][0]["text"] == "Test."


def test_same_script_different_languages_cached_separately():
    """Test that same script in different languages are cached separately."""
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(FakeLLMClient(), cache_dir=Path(tmpdir))

        script = "Hello. World."

        draft_en = use_case.generate_subtitles(script, "en", audio_duration_ms=2000)
        draft_es = use_case.generate_subtitles(script, "es", audio_duration_ms=2000)

        # Both should have same content (no translation happened)
        assert draft_en.language == "en"
        assert draft_es.language == "es"

        # Check that both are cached
        cache_files = list(Path(tmpdir).glob("*.json"))
        assert len(cache_files) == 2
