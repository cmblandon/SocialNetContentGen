"""
SubtitleGenerationUseCase — generates SRT subtitles from approved scripts.

Produces bilingual (Spanish + English) subtitles with accurate timing.
Timing is derived from TTS audio duration (ElevenLabs API).
"""
import hashlib
import json
import re
from pathlib import Path
from typing import Optional

from src.editorial.core.entities import SubtitleDraft, SubtitleLine
from src.editorial.core.exceptions import StoryGenerationError
from src.editorial.core.ports import ILLMClient


def _ms_to_srt_time(milliseconds: int) -> str:
    """Convert milliseconds to SRT timecode format (HH:MM:SS,mmm)."""
    total_seconds = milliseconds // 1000
    ms = milliseconds % 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


class SubtitleGenerationUseCase:
    """Generates bilingual subtitles from approved scripts."""

    def __init__(self, llm_client: ILLMClient, cache_dir: Optional[Path] = None):
        self._llm_client = llm_client
        self._cache_dir = cache_dir or Path("data/subtitle_cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def generate_subtitles(
        self, script: str, language: str, audio_duration_ms: int
    ) -> SubtitleDraft:
        """
        Generate subtitles for a script in the given language.

        Args:
            script: The approved chapter script
            language: Language code ('es' or 'en')
            audio_duration_ms: Duration of TTS audio in milliseconds

        Returns:
            SubtitleDraft with SRT subtitle lines
        """
        if language not in ("es", "en"):
            raise StoryGenerationError(f"Unsupported language: {language}")

        cached = self._get_cached_subtitles(script, language)
        if cached:
            return cached

        # Split script into sentences for subtitle lines
        sentences = self._split_into_sentences(script)
        if not sentences:
            raise StoryGenerationError(f"Script could not be split into sentences: {script}")

        # Distribute the measured audio duration across sentences in
        # proportion to their length: speech time tracks word count, so an
        # even split would leave a one-word sentence on screen as long as a
        # thirty-word one and drift further with every line.
        weights = [max(1, len(sentence.split())) for sentence in sentences]
        total_weight = sum(weights)

        subtitle_lines: list[SubtitleLine] = []
        elapsed_ms = 0

        for index, (sentence, weight) in enumerate(zip(sentences, weights), start=1):
            start_ms = elapsed_ms
            if index == len(sentences):
                # The last line absorbs rounding so the subtitles end exactly
                # with the audio.
                end_ms = audio_duration_ms
            else:
                end_ms = start_ms + (audio_duration_ms * weight) // total_weight
            elapsed_ms = end_ms

            subtitle_lines.append(
                SubtitleLine(
                    index=index,
                    start_time=_ms_to_srt_time(start_ms),
                    end_time=_ms_to_srt_time(end_ms),
                    text=sentence.strip(),
                )
            )

        draft = SubtitleDraft(language=language, subtitle_lines=subtitle_lines)
        self._cache_subtitles(script, language, draft)
        return draft

    def translate_and_generate_subtitles(
        self, script: str, source_language: str, target_language: str, audio_duration_ms: int
    ) -> SubtitleDraft:
        """
        Generate subtitles by first translating the script.

        Args:
            script: The original script
            source_language: Source language code ('es' or 'en')
            target_language: Target language code ('es' or 'en')
            audio_duration_ms: Duration of TTS audio in milliseconds

        Returns:
            SubtitleDraft with translated subtitle lines
        """
        if source_language == target_language:
            return self.generate_subtitles(script, source_language, audio_duration_ms)

        cached = self._get_cached_subtitles(script, target_language)
        if cached:
            return cached

        translated_script = self._translate_script(script, source_language, target_language)
        draft = self.generate_subtitles(translated_script, target_language, audio_duration_ms)
        self._cache_subtitles(script, target_language, draft)
        return draft

    def translate_script(self, script: str, source_language: str, target_language: str) -> str:
        """
        Translate a script between supported languages.

        Exposed because video generation needs the translated narration for
        TTS as well as for subtitles — otherwise an English video would be
        Spanish text read aloud by an English voice.
        """
        if source_language == target_language:
            return script
        return self._translate_script(script, source_language, target_language)

    def _split_into_sentences(self, script: str) -> list[str]:
        """Split script into sentences, roughly at periods/question marks/exclamation marks."""
        # Simple regex-based split; can be improved with NLP library if needed
        sentences = re.split(r"(?<=[.!?])\s+", script.strip())
        return [s for s in sentences if s.strip()]

    def _translate_script(self, script: str, source_lang: str, target_lang: str) -> str:
        """Translate script from source to target language using LLM."""
        lang_names = {"es": "Spanish", "en": "English"}
        prompt = f"""\
Translate the following {lang_names[source_lang]} script to {lang_names[target_lang]}. \
Keep it concise and maintain the pacing cues. Return ONLY the translated text, no explanations.

{script}
"""
        translated = self._llm_client.complete(prompt)
        if not translated.strip():
            raise StoryGenerationError(
                f"Translation failed: LLM returned empty response for {source_lang} → {target_lang}"
            )
        return translated.strip()

    def _get_cache_key(self, script: str, language: str) -> str:
        """Generate a cache key from script and language."""
        content = f"{script}:{language}"
        return hashlib.md5(content.encode()).hexdigest()

    def _get_cached_subtitles(self, script: str, language: str) -> Optional[SubtitleDraft]:
        """Retrieve cached subtitles if they exist."""
        cache_key = self._get_cache_key(script, language)
        cache_file = self._cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file) as f:
                data = json.load(f)
            lines = [
                SubtitleLine(
                    index=line["index"],
                    start_time=line["start_time"],
                    end_time=line["end_time"],
                    text=line["text"],
                )
                for line in data["subtitle_lines"]
            ]
            return SubtitleDraft(language=data["language"], subtitle_lines=lines)
        except Exception as e:
            raise StoryGenerationError(f"Failed to load cached subtitles: {e}") from e

    def _cache_subtitles(self, script: str, language: str, draft: SubtitleDraft) -> None:
        """Cache generated subtitles for future reuse."""
        cache_key = self._get_cache_key(script, language)
        cache_file = self._cache_dir / f"{cache_key}.json"

        data = {
            "language": draft.language,
            "subtitle_lines": [
                {
                    "index": line.index,
                    "start_time": line.start_time,
                    "end_time": line.end_time,
                    "text": line.text,
                }
                for line in draft.subtitle_lines
            ],
        }

        try:
            with open(cache_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            raise StoryGenerationError(f"Failed to cache subtitles: {e}") from e
