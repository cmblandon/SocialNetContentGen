"""
Tests for StoryWritingUseCase — per specs/story-writing/spec.md.

The LLM does the actual creative writing (hook/development/close, chapter
splitting, cliffhangers) — this use case's job is prompting it with the
source document, parsing its structured JSON output, and enforcing the
requirements that ARE mechanically checkable: chapter length, a citation on
every chapter, no quoted text absent from the source document (fabricated
quotes), and no sensationalist/overstated phrasing.
"""
import json

import pytest

from src.editorial.application.story_writing_use_case import (
    MAX_CHAPTER_WORDS,
    MIN_CHAPTER_WORDS,
    StoryWritingUseCase,
)
from src.editorial.core.entities import ChapterDraft, StoryDraft
from src.editorial.core.exceptions import StoryGenerationError

DOCUMENT_TEXT = (
    "A pilot reported an unidentified radar contact over the Pacific. "
    'The incident log states: "radar contact was lost at 0200 hours" '
    "before the aircraft returned to base without further incident."
)


def _words(count: int) -> str:
    return " ".join(["word"] * count)


def _valid_script(extra: str = "") -> str:
    """A script within the 150-220 word range."""
    base = _words(180)
    return f"{base} {extra}".strip()


def _chapter(
    title="Part 1",
    script=None,
    visual_notes="Show the radar log on screen.",
    source_citation="AARO, report, 2024-03-01",
):
    return {
        "title": title,
        "script": script if script is not None else _valid_script(),
        "visual_notes": visual_notes,
        "source_citation": source_citation,
    }


class FakeLLMClient:
    def __init__(self, response_text: str):
        self._response_text = response_text
        self.last_prompt: str | None = None

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response_text


def _use_case(response_payload: dict) -> tuple[StoryWritingUseCase, FakeLLMClient]:
    llm = FakeLLMClient(json.dumps(response_payload))
    return StoryWritingUseCase(llm_client=llm), llm


def test_generates_single_chapter_for_short_document():
    payload = {"summary": "A radar contact goes unexplained.", "chapters": [_chapter()]}
    use_case, _ = _use_case(payload)

    draft = use_case.write_story(
        document_text=DOCUMENT_TEXT,
        agency="AARO",
        doc_type="report",
        published_date="2024-03-01",
        narrative_angle="military witness + radar corroboration",
    )

    assert isinstance(draft, StoryDraft)
    assert draft.summary == "A radar contact goes unexplained."
    assert len(draft.chapters) == 1
    assert isinstance(draft.chapters[0], ChapterDraft)
    assert draft.chapters[0].title == "Part 1"


def test_generates_multiple_chapters_for_long_document():
    payload = {
        "summary": "A multi-part case.",
        "chapters": [
            _chapter(title="Part 1"),
            _chapter(title="Part 2"),
            _chapter(title="Part 3"),
        ],
    }
    use_case, _ = _use_case(payload)

    draft = use_case.write_story(
        document_text=DOCUMENT_TEXT,
        agency="AARO",
        doc_type="report",
        published_date="2024-03-01",
        narrative_angle="lengthy case with multiple annexes",
    )

    assert [c.title for c in draft.chapters] == ["Part 1", "Part 2", "Part 3"]


def test_assigns_sequential_chapter_indices_by_order():
    payload = {"summary": "s", "chapters": [_chapter(title="A"), _chapter(title="B")]}
    use_case, _ = _use_case(payload)

    draft = use_case.write_story(
        document_text=DOCUMENT_TEXT,
        agency="AARO",
        doc_type="report",
        published_date="2024-03-01",
        narrative_angle="angle",
    )

    assert [c.chapter_index for c in draft.chapters] == [1, 2]


def test_prompt_includes_document_text_agency_and_narrative_angle():
    payload = {"summary": "s", "chapters": [_chapter()]}
    use_case, llm = _use_case(payload)

    use_case.write_story(
        document_text=DOCUMENT_TEXT,
        agency="AARO",
        doc_type="report",
        published_date="2024-03-01",
        narrative_angle="military witness + radar corroboration",
    )

    assert DOCUMENT_TEXT in llm.last_prompt
    assert "AARO" in llm.last_prompt
    assert "military witness + radar corroboration" in llm.last_prompt


def test_raises_when_llm_returns_invalid_json():
    llm = FakeLLMClient("not valid json")
    use_case = StoryWritingUseCase(llm_client=llm)

    with pytest.raises(StoryGenerationError):
        use_case.write_story(
            document_text=DOCUMENT_TEXT,
            agency="AARO",
            doc_type="report",
            published_date="2024-03-01",
            narrative_angle="angle",
        )


def test_raises_when_chapter_script_is_too_short():
    payload = {"summary": "s", "chapters": [_chapter(script=_words(50))]}
    use_case, _ = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.write_story(
            document_text=DOCUMENT_TEXT,
            agency="AARO",
            doc_type="report",
            published_date="2024-03-01",
            narrative_angle="angle",
        )


def test_raises_when_chapter_script_is_too_long():
    payload = {"summary": "s", "chapters": [_chapter(script=_words(250))]}
    use_case, _ = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.write_story(
            document_text=DOCUMENT_TEXT,
            agency="AARO",
            doc_type="report",
            published_date="2024-03-01",
            narrative_angle="angle",
        )


def test_raises_when_chapter_is_missing_source_citation():
    payload = {"summary": "s", "chapters": [_chapter(source_citation="")]}
    use_case, _ = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.write_story(
            document_text=DOCUMENT_TEXT,
            agency="AARO",
            doc_type="report",
            published_date="2024-03-01",
            narrative_angle="angle",
        )


def test_raises_when_chapter_contains_a_quote_absent_from_the_source_document():
    fabricated_quote = 'The pilot said "we made direct contact with the occupants"'
    payload = {
        "summary": "s",
        "chapters": [_chapter(script=_valid_script(extra=fabricated_quote))],
    }
    use_case, _ = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.write_story(
            document_text=DOCUMENT_TEXT,
            agency="AARO",
            doc_type="report",
            published_date="2024-03-01",
            narrative_angle="angle",
        )


def test_accepts_a_quote_that_appears_verbatim_in_the_source_document():
    genuine_quote = 'The log states: "radar contact was lost at 0200 hours"'
    payload = {
        "summary": "s",
        "chapters": [_chapter(script=_valid_script(extra=genuine_quote))],
    }
    use_case, _ = _use_case(payload)

    draft = use_case.write_story(
        document_text=DOCUMENT_TEXT,
        agency="AARO",
        doc_type="report",
        published_date="2024-03-01",
        narrative_angle="angle",
    )

    assert genuine_quote in draft.chapters[0].script


@pytest.mark.parametrize(
    "overstated_phrase",
    [
        "this is definitive proof of extraterrestrial contact",
        "the government admitted the object was alien technology",
    ],
)
def test_raises_when_chapter_contains_an_overstated_claim(overstated_phrase):
    payload = {
        "summary": "s",
        "chapters": [_chapter(script=_valid_script(extra=overstated_phrase))],
    }
    use_case, _ = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.write_story(
            document_text=DOCUMENT_TEXT,
            agency="AARO",
            doc_type="report",
            published_date="2024-03-01",
            narrative_angle="angle",
        )


def test_raises_when_chapter_is_missing_visual_directives():
    payload = {"summary": "s", "chapters": [_chapter(visual_notes="")]}
    use_case, _ = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.write_story(
            document_text=DOCUMENT_TEXT,
            agency="AARO",
            doc_type="report",
            published_date="2024-03-01",
            narrative_angle="angle",
        )


def test_accepts_visual_directives_in_chapter():
    visual_directives = "Show declassified radar log on screen with timestamp overlay. Transition to archival footage of military base at 0200 hours."
    payload = {
        "summary": "s",
        "chapters": [_chapter(visual_notes=visual_directives)],
    }
    use_case, _ = _use_case(payload)

    draft = use_case.write_story(
        document_text=DOCUMENT_TEXT,
        agency="AARO",
        doc_type="report",
        published_date="2024-03-01",
        narrative_angle="angle",
    )

    assert draft.chapters[0].visual_notes == visual_directives


def test_prompt_includes_reel_optimization_constraints():
    payload = {"summary": "s", "chapters": [_chapter()]}
    use_case, llm = _use_case(payload)

    use_case.write_story(
        document_text=DOCUMENT_TEXT,
        agency="AARO",
        doc_type="report",
        published_date="2024-03-01",
        narrative_angle="angle",
    )

    assert "150–220 words" in llm.last_prompt
    assert "visual directives" in llm.last_prompt
    assert "pacing cues" in llm.last_prompt


# --- regeneration on validation failure (local-curation-model, task 6.x) -----


class ScriptedLLMClient:
    """Returns a different response per call, recording the prompts it saw."""

    def __init__(self, *responses: str):
        self._responses = list(responses)
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        # Repeat the last response once exhausted, so "always fails" is easy
        # to express.
        return self._responses[min(len(self.prompts), len(self._responses)) - 1]


def _payload(word_count: int) -> str:
    return json.dumps(
        {"summary": "s", "chapters": [_chapter(script=_words(word_count))]}
    )


def test_retries_with_the_reason_when_a_chapter_is_too_short():
    """
    Measured behaviour that makes local generation viable: a small model
    produced 121, then 149, then 150 words once told what was wrong.
    """
    llm = ScriptedLLMClient(_payload(120), _payload(180))
    use_case = StoryWritingUseCase(llm_client=llm)

    draft = use_case.write_story(
        document_text=DOCUMENT_TEXT,
        agency="AARO",
        doc_type="report",
        published_date="2024-03-01",
        narrative_angle="angle",
    )

    assert len(draft.chapters[0].script.split()) == 180
    assert len(llm.prompts) == 2
    # The retry must say what was wrong, not just ask again.
    assert "120 words" in llm.prompts[1]
    assert "rejected" in llm.prompts[1]


def test_a_valid_first_attempt_never_retries():
    """A capable model pays nothing for this — no extra call is made."""
    llm = ScriptedLLMClient(_payload(180))
    use_case = StoryWritingUseCase(llm_client=llm)

    use_case.write_story(
        document_text=DOCUMENT_TEXT,
        agency="AARO",
        doc_type="report",
        published_date="2024-03-01",
        narrative_angle="angle",
    )

    assert len(llm.prompts) == 1


def test_retries_are_bounded_and_raise_the_last_error():
    """A model that cannot satisfy the constraint fails visibly, not forever."""
    llm = ScriptedLLMClient(_payload(30))
    use_case = StoryWritingUseCase(llm_client=llm, max_attempts=3)

    with pytest.raises(StoryGenerationError, match="30 words"):
        use_case.write_story(
            document_text=DOCUMENT_TEXT,
            agency="AARO",
            doc_type="report",
            published_date="2024-03-01",
            narrative_angle="angle",
        )

    assert len(llm.prompts) == 3


def test_retries_on_unparseable_output_too():
    """Small models wrap JSON in prose; that is worth one more attempt."""
    llm = ScriptedLLMClient("Claro, aquí tienes:", _payload(180))
    use_case = StoryWritingUseCase(llm_client=llm)

    draft = use_case.write_story(
        document_text=DOCUMENT_TEXT,
        agency="AARO",
        doc_type="report",
        published_date="2024-03-01",
        narrative_angle="angle",
    )

    assert draft.chapters
    assert "not valid JSON" in llm.prompts[1]


def test_the_word_range_is_never_relaxed_to_accommodate_a_weak_model():
    """
    The range is what keeps a chapter inside a 15-60s reel. Retrying the
    model is the accommodation; lowering the bar is not.
    """
    assert (MIN_CHAPTER_WORDS, MAX_CHAPTER_WORDS) == (150, 220)

    llm = ScriptedLLMClient(_payload(MIN_CHAPTER_WORDS - 1))
    with pytest.raises(StoryGenerationError):
        StoryWritingUseCase(llm_client=llm, max_attempts=1).write_story(
            document_text=DOCUMENT_TEXT,
            agency="AARO",
            doc_type="report",
            published_date="2024-03-01",
            narrative_angle="angle",
        )
