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


def test_timing_is_never_cached_across_different_audio_durations():
    """
    Regression: a draft cache keyed on (script, language) returned timing
    measured against different audio, silently desyncing captions from speech
    — the exact failure that measuring the audio exists to prevent.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(FakeLLMClient(), cache_dir=Path(tmpdir))
        script = "Una frase. Otra frase."

        first = use_case.generate_subtitles(script, "es", audio_duration_ms=4000)
        second = use_case.generate_subtitles(script, "es", audio_duration_ms=10000)

        assert first.subtitle_lines[-1].end_time == "00:00:04,000"
        assert second.subtitle_lines[-1].end_time == "00:00:10,000"


def test_translation_is_cached_so_the_llm_is_called_once():
    """The LLM call is the expensive step, and a fixed script's translation
    is stable — unlike its timing."""
    llm = FakeLLMClient({"Hola mundo.": "Hello world."})
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(llm, cache_dir=Path(tmpdir))

        use_case.translate_and_generate_subtitles(
            "Hola mundo.", "es", "en", audio_duration_ms=2000
        )
        use_case.translate_and_generate_subtitles(
            "Hola mundo.", "es", "en", audio_duration_ms=9000
        )

        assert llm.call_count == 1


def test_cached_translation_does_not_freeze_timing():
    """Reusing a cached translation must still re-time against the new audio."""
    llm = FakeLLMClient({"Hola mundo.": "Hello world."})
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(llm, cache_dir=Path(tmpdir))

        first = use_case.translate_and_generate_subtitles(
            "Hola mundo.", "es", "en", audio_duration_ms=2000
        )
        second = use_case.translate_and_generate_subtitles(
            "Hola mundo.", "es", "en", audio_duration_ms=9000
        )

        assert first.subtitle_lines[-1].end_time == "00:00:02,000"
        assert second.subtitle_lines[-1].end_time == "00:00:09,000"


def test_translation_cache_is_written_as_valid_json():
    llm = FakeLLMClient({"Hola mundo.": "Hello world."})
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(llm, cache_dir=Path(tmpdir))
        use_case.translate_script("Hola mundo.", "es", "en")

        cache_files = list(Path(tmpdir).glob("*.translation.json"))
        assert len(cache_files) == 1

        payload = json.loads(cache_files[0].read_text(encoding="utf-8"))
        assert payload["translated"] == "Hello world."
        assert payload["source_language"] == "es"
        assert payload["target_language"] == "en"


def test_corrupt_translation_cache_falls_back_to_retranslating():
    llm = FakeLLMClient({"Hola mundo.": "Hello world."})
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(llm, cache_dir=Path(tmpdir))
        use_case.translate_script("Hola mundo.", "es", "en")
        list(Path(tmpdir).glob("*.translation.json"))[0].write_text("{not json")

        assert use_case.translate_script("Hola mundo.", "es", "en") == "Hello world."
        assert llm.call_count == 2


def test_translations_are_cached_per_language_pair():
    llm = FakeLLMClient({"Hola.": "Hello."})
    with tempfile.TemporaryDirectory() as tmpdir:
        use_case = SubtitleGenerationUseCase(llm, cache_dir=Path(tmpdir))

        use_case.translate_script("Hola.", "es", "en")
        use_case.translate_script("Hola.", "en", "es")

        assert len(list(Path(tmpdir).glob("*.translation.json"))) == 2
