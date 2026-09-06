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

        # Deliberately not cached. Timing is derived from audio_duration_ms,
        # which changes every time narration is re-synthesized, so a cached
        # draft keyed on (script, language) would hand back timing measured
        # against different audio — captions silently out of sync with speech,
        # which is the failure measuring the audio existed to prevent. The
        # computation here is pure and cheap; the expensive part is the LLM
        # translation, and that is what _translate_script caches.
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

        return SubtitleDraft(language=language, subtitle_lines=subtitle_lines)

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
        translated_script = self.translate_script(script, source_language, target_language)
        return self.generate_subtitles(translated_script, target_language, audio_duration_ms)

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
        """
        Translate script from source to target language using the LLM.

        Cached on disk: this is the only expensive step here, and a
        translation of a fixed script is stable, unlike subtitle timing.
        """
        cached = self._get_cached_translation(script, source_lang, target_lang)
        if cached is not None:
            return cached

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

        translated = translated.strip()
        self._cache_translation(script, source_lang, target_lang, translated)
        return translated

    def _translation_cache_path(self, script: str, source_lang: str, target_lang: str) -> Path:
        key = hashlib.md5(f"{script}:{source_lang}:{target_lang}".encode()).hexdigest()
        return self._cache_dir / f"{key}.translation.json"

    def _get_cached_translation(
        self, script: str, source_lang: str, target_lang: str
    ) -> Optional[str]:
        path = self._translation_cache_path(script, source_lang, target_lang)
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # A damaged cache entry is not worth failing a generation over —
            # the translation can simply be redone.
            return None

        translated = payload.get("translated")
        return translated if isinstance(translated, str) and translated.strip() else None

    def _cache_translation(
        self, script: str, source_lang: str, target_lang: str, translated: str
    ) -> None:
        path = self._translation_cache_path(script, source_lang, target_lang)
        try:
            path.write_text(
                json.dumps(
                    {
                        "source_language": source_lang,
                        "target_language": target_lang,
                        "translated": translated,
                    }
                ),
                encoding="utf-8",
            )
        except OSError:
            # Caching is an optimization; failing to write it must not fail
            # the generation that produced a perfectly good translation.
            pass
