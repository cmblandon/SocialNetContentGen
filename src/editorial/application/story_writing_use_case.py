"""
StoryWritingUseCase — turns a curated document into a StoryDraft.

Per specs/story-writing/spec.md: the creative writing (hook, development,
close, chapter splitting, cliffhangers) is the LLM's job. This use case's
job is to prompt it with the source material, parse its structured output,
and enforce the requirements that are mechanically checkable — anything
that fails these checks means the draft cannot be trusted and must be
regenerated or escalated, never silently passed through.
"""
import json
import logging
import re
from typing import Optional

from src.editorial.core.entities import ChapterDraft, StoryDraft
from src.editorial.core.exceptions import StoryGenerationError
from src.editorial.core.ports import ILLMClient

logger = logging.getLogger("editorial.story_writing")

MIN_CHAPTER_WORDS = 150
MAX_CHAPTER_WORDS = 220

# Enough for a small model to converge (measured: 121 -> 149 -> 150 words),
# few enough that a model which simply cannot satisfy the constraint fails
# quickly rather than burning minutes of local inference.
DEFAULT_MAX_ATTEMPTS = 3

_RETRY_SUFFIX = """\
Your previous attempt was rejected: {reason}

Fix exactly that problem and respond again with the same JSON shape. Count \
the words in each script before answering — a script outside the required \
range is rejected again. Aim for 185 words per chapter."""

# Phrases that overstate what a source document establishes (per
# specs/story-writing/spec.md: "no lenguaje sensacionalista que tergiverse
# el documento"). Matched case-insensitively as substrings.
_OVERSTATED_PHRASES = (
    "definitive proof",
    "the government admitted",
    "irrefutable evidence",
    "prueba definitiva",
    "el gobierno admitió",
)

_QUOTE_PATTERN = re.compile(r'"([^"]+)"')

_PROMPT_TEMPLATE = """\
You are the writer agent of "Archivo Desclasificado". Convert the official \
document below into a hook-driven, fact-bound story optimized for short-form \
video (TikTok/Instagram Reels, 15–60 seconds).

CRITICAL CONSTRAINTS:
- Each chapter MUST be 150–220 words (approximately 60–90 seconds at natural \
speaking pace).
- MUST include visual directives: concrete suggestions for visuals (e.g., \
"archival footage of military radar", "declassified document on screen", \
"news clip from 1985").
- MUST include pacing cues: where to pause, emphasize, or transition.
- Never invent details or attribute quotes not present in the document.

Agency: {agency}
Document type: {doc_type}
Published date: {published_date}
Narrative angle: {narrative_angle}

Document text:
{document_text}

Respond with JSON matching this shape:
{{"summary": "...", "chapters": [{{"title": "...", "script": "...", \
"visual_notes": "visual directives and pacing cues here", \
"source_citation": "..."}}]}}
"""


class StoryWritingUseCase:
    def __init__(self, llm_client: ILLMClient, max_attempts: int = DEFAULT_MAX_ATTEMPTS):
        self._llm_client = llm_client
        self._max_attempts = max(1, max_attempts)

    def write_story(
        self,
        document_text: str,
        agency: str,
        doc_type: str,
        published_date: Optional[str],
        narrative_angle: str,
    ) -> StoryDraft:
        """
        Generate a story, retrying with the validation failure fed back.

        A small local model cannot satisfy the word-count range from a single
        instruction — measured output went 121, then 149, then 150 words as
        the reason was returned to it. Telling the model what was wrong is
        what makes local generation viable; the requirement itself is never
        relaxed to accommodate a weaker model.

        A capable model satisfies the constraints on the first attempt and
        never enters the loop, so this costs cloud callers nothing.
        """
        prompt = _PROMPT_TEMPLATE.format(
            agency=agency,
            doc_type=doc_type,
            published_date=published_date,
            narrative_angle=narrative_angle,
            document_text=document_text,
        )

        last_error: Optional[StoryGenerationError] = None
        for attempt in range(1, self._max_attempts + 1):
            raw_response = self._llm_client.complete(prompt)
            try:
                return self._build_draft(raw_response, document_text)
            except StoryGenerationError as error:
                last_error = error
                logger.info(
                    "Story draft rejected on attempt %d/%d: %s",
                    attempt,
                    self._max_attempts,
                    error,
                )
                prompt = f"{prompt}\n\n{_RETRY_SUFFIX.format(reason=error)}"

        # Bounded: a model that cannot satisfy the constraint fails visibly
        # rather than looping, and the caller sees the actual reason.
        assert last_error is not None
        raise last_error

    def _build_draft(self, raw_response: str, document_text: str) -> StoryDraft:
        payload = self._parse_json(raw_response)
        chapters = [
            self._build_chapter(raw_chapter, index, document_text)
            for index, raw_chapter in enumerate(payload.get("chapters", []), start=1)
        ]
        return StoryDraft(summary=payload.get("summary", ""), chapters=chapters)

    def _parse_json(self, raw_response: str) -> dict:
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError as error:
            raise StoryGenerationError(
                f"LLM response is not valid JSON: {error}"
            ) from error

    def _build_chapter(
        self, raw_chapter: dict, chapter_index: int, document_text: str
    ) -> ChapterDraft:
        script = raw_chapter.get("script", "")
        source_citation = raw_chapter.get("source_citation", "")
        visual_notes = raw_chapter.get("visual_notes", "")

        self._validate_word_count(script, chapter_index)
        self._validate_source_citation(source_citation, chapter_index)
        self._validate_no_fabricated_quotes(script, document_text, chapter_index)
        self._validate_no_overstated_claims(script, chapter_index)
        self._validate_visual_directives(visual_notes, chapter_index)

        return ChapterDraft(
            title=raw_chapter.get("title", ""),
            script=script,
            visual_notes=visual_notes,
            source_citation=source_citation,
            chapter_index=chapter_index,
        )

    def _validate_word_count(self, script: str, chapter_index: int) -> None:
        word_count = len(script.split())
        if not (MIN_CHAPTER_WORDS <= word_count <= MAX_CHAPTER_WORDS):
            raise StoryGenerationError(
                f"Chapter {chapter_index} script has {word_count} words; "
                f"must be between {MIN_CHAPTER_WORDS} and {MAX_CHAPTER_WORDS}."
            )

    def _validate_source_citation(self, source_citation: str, chapter_index: int) -> None:
        if not source_citation.strip():
            raise StoryGenerationError(
                f"Chapter {chapter_index} is missing its source citation."
            )

    def _validate_no_fabricated_quotes(
        self, script: str, document_text: str, chapter_index: int
    ) -> None:
        document_text_lower = document_text.lower()
        for quote in _QUOTE_PATTERN.findall(script):
            if quote.lower() not in document_text_lower:
                raise StoryGenerationError(
                    f'Chapter {chapter_index} attributes a quote not found '
                    f'in the source document: "{quote}"'
                )

    def _validate_no_overstated_claims(self, script: str, chapter_index: int) -> None:
        script_lower = script.lower()
        for phrase in _OVERSTATED_PHRASES:
            if phrase in script_lower:
                raise StoryGenerationError(
                    f"Chapter {chapter_index} contains overstated phrasing: "
                    f'"{phrase}"'
                )

    def _validate_visual_directives(self, visual_notes: str, chapter_index: int) -> None:
        if not visual_notes.strip():
            raise StoryGenerationError(
                f"Chapter {chapter_index} is missing visual directives. "
                f"Must include concrete visual suggestions (e.g., 'archival footage', 'document on screen')."
            )
