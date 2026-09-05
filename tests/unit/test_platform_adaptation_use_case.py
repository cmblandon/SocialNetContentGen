"""
Tests for PlatformAdaptationUseCase — per specs/platform-adaptation/spec.md.

Like StoryWritingUseCase, the LLM does the creative rewriting per platform;
this use case prompts it, parses its structured output, and enforces the
mechanically-checkable requirements (slide/tweet counts, hashtag format,
citation present where required, the chapter's spoken script left
byte-for-byte unchanged for TikTok/Reels).
"""
import json

import pytest

from src.editorial.application.platform_adaptation_use_case import (
    PlatformAdaptationUseCase,
)
from src.editorial.core.entities import PlatformAdaptations
from src.editorial.core.exceptions import StoryGenerationError

CHAPTER_SCRIPT = "word " * 180
SOURCE_CITATION = "AARO, report, 2024-03-01"


def _words(count: int) -> str:
    return " ".join(["word"] * count)


def _valid_payload(**overrides) -> dict:
    payload = {
        "tiktok": {
            "on_screen_hook_lines": ["A pilot saw something unexplained.", "The Pentagon confirmed the case."],
            "hashtags": ["#ovni", "#desclasificado", "#misterio"],
            "description": "The radar data still has no explanation. Part 2 coming soon.",
        },
        "instagram": {
            "carousel_slides": [
                "Cover: the radar contact nobody could explain.",
                "Slide 2: the pilot's report.",
                "Slide 3: the agency's response.",
                "Slide 4: what the document says.",
                "Slide 5: what remains unknown.",
                f"Source: {SOURCE_CITATION}. Follow for part 2.",
            ],
        },
        "x": {
            "tweets": [
                "A military pilot reported a radar contact that the Pentagon never fully explained, and the declassified file finally shows why.",
                "Tweet 2 with more context about the incident and the agency's internal review process.",
                "Tweet 3 describing what the document says happened next during the investigation.",
                f"Source: {SOURCE_CITATION}. Next chapter reveals the transcript.",
            ],
        },
        "facebook": {
            "post": (
                _words(200)
                + " Full context of the case is described here for readers who want the whole story in one place. "
                "What do you think really happened that night?"
            ),
        },
    }
    payload.update(overrides)
    return payload


class FakeLLMClient:
    def __init__(self, response_text: str):
        self._response_text = response_text
        self.last_prompt: str | None = None

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response_text


def _use_case(payload: dict) -> PlatformAdaptationUseCase:
    llm = FakeLLMClient(json.dumps(payload))
    return PlatformAdaptationUseCase(llm_client=llm)


def test_adapts_chapter_to_all_four_platforms():
    use_case = _use_case(_valid_payload())

    result = use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)

    assert isinstance(result, PlatformAdaptations)
    assert result.tiktok is not None
    assert result.instagram is not None
    assert result.x is not None
    assert result.facebook is not None


def test_tiktok_reuses_the_chapter_script_unchanged():
    use_case = _use_case(_valid_payload())

    result = use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)

    assert result.tiktok.script == CHAPTER_SCRIPT


def test_tiktok_has_two_on_screen_hook_lines_and_3_to_5_hashtags():
    use_case = _use_case(_valid_payload())

    result = use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)

    assert len(result.tiktok.on_screen_hook_lines) == 2
    assert 3 <= len(result.tiktok.hashtags) <= 5
    assert all(tag.startswith("#") for tag in result.tiktok.hashtags)


def test_raises_when_tiktok_has_too_few_hashtags():
    payload = _valid_payload()
    payload["tiktok"]["hashtags"] = ["#ovni", "#misterio"]
    use_case = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)


def test_raises_when_tiktok_hashtag_missing_hash_prefix():
    payload = _valid_payload()
    payload["tiktok"]["hashtags"] = ["ovni", "#desclasificado", "#misterio"]
    use_case = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)


def test_instagram_carousel_has_6_to_8_slides():
    use_case = _use_case(_valid_payload())

    result = use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)

    assert 6 <= len(result.instagram.carousel_slides) <= 8


def test_raises_when_instagram_carousel_has_too_few_slides():
    payload = _valid_payload()
    payload["instagram"]["carousel_slides"] = ["only", "four", "slides", "here"]
    use_case = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)


def test_raises_when_instagram_last_slide_missing_citation():
    payload = _valid_payload()
    payload["instagram"]["carousel_slides"][-1] = "Follow for part 2, no source mentioned here."
    use_case = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)


def test_x_thread_has_4_to_8_tweets():
    use_case = _use_case(_valid_payload())

    result = use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)

    assert 4 <= len(result.x.tweets) <= 8


def test_raises_when_x_thread_has_too_few_tweets():
    payload = _valid_payload()
    payload["x"]["tweets"] = ["one", "two", "three"]
    use_case = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)


def test_raises_when_x_first_tweet_is_too_short_to_stand_alone():
    payload = _valid_payload()
    payload["x"]["tweets"][0] = "Read this thread."
    use_case = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)


def test_raises_when_x_last_tweet_missing_citation():
    payload = _valid_payload()
    payload["x"]["tweets"][-1] = "Next chapter coming soon, stay tuned!"
    use_case = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)


def test_facebook_post_ends_with_a_question():
    use_case = _use_case(_valid_payload())

    result = use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)

    assert result.facebook.post.strip().endswith("?")


def test_raises_when_facebook_post_does_not_end_with_a_question():
    payload = _valid_payload()
    payload["facebook"]["post"] = _words(200) + " That's the whole story."
    use_case = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)


def test_raises_when_facebook_post_is_too_short():
    payload = _valid_payload()
    payload["facebook"]["post"] = "Short post. What happened?"
    use_case = _use_case(payload)

    with pytest.raises(StoryGenerationError):
        use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)


def test_raises_when_llm_returns_invalid_json():
    llm = FakeLLMClient("not valid json")
    use_case = PlatformAdaptationUseCase(llm_client=llm)

    with pytest.raises(StoryGenerationError):
        use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)


def test_prompt_includes_script_and_citation():
    llm = FakeLLMClient(json.dumps(_valid_payload()))
    use_case = PlatformAdaptationUseCase(llm_client=llm)

    use_case.adapt_chapter(script=CHAPTER_SCRIPT, source_citation=SOURCE_CITATION)

    assert CHAPTER_SCRIPT in llm.last_prompt
    assert SOURCE_CITATION in llm.last_prompt
