"""
PlatformAdaptationUseCase — reformats a chapter for TikTok/Reels, Instagram,
X, and Facebook, per specs/platform-adaptation/spec.md.

Facts and the core spoken script are never left to the LLM to preserve:
the TikTok/Reels script is set directly from the chapter's own script
rather than trusted from the LLM's output, guaranteeing "sin cambiar los
hechos ni el guion hablado central" structurally rather than by prompt
instruction alone (design.md Decision 6).
"""
import json

from src.editorial.core.entities import (
    FacebookAdaptation,
    InstagramAdaptation,
    PlatformAdaptations,
    TikTokAdaptation,
    XAdaptation,
)
from src.editorial.core.exceptions import StoryGenerationError
from src.editorial.core.ports import ILLMClient

MIN_HASHTAGS = 3
MAX_HASHTAGS = 5
MIN_CAROUSEL_SLIDES = 6
MAX_CAROUSEL_SLIDES = 8
MIN_TWEETS = 4
MAX_TWEETS = 8
MIN_FIRST_TWEET_WORDS = 15
MIN_FACEBOOK_POST_WORDS = 150

_PROMPT_TEMPLATE = """\
You are the platform adapter of "Archivo Desclasificado". Reformat the \
chapter below for TikTok/Reels, Instagram, X, and Facebook, without \
changing any fact or the core spoken script.

Source citation: {source_citation}

Chapter script:
{script}

Respond with JSON matching this shape:
{{"tiktok": {{"on_screen_hook_lines": ["...", "..."], "hashtags": ["#...", ...], \
"description": "..."}}, "instagram": {{"carousel_slides": ["...", ...]}}, \
"x": {{"tweets": ["...", ...]}}, "facebook": {{"post": "..."}}}}
"""


class PlatformAdaptationUseCase:
    def __init__(self, llm_client: ILLMClient):
        self._llm_client = llm_client

    def adapt_chapter(self, script: str, source_citation: str) -> PlatformAdaptations:
        prompt = _PROMPT_TEMPLATE.format(source_citation=source_citation, script=script)
        raw_response = self._llm_client.complete(prompt)
        payload = self._parse_json(raw_response)

        return PlatformAdaptations(
            tiktok=self._build_tiktok(payload.get("tiktok", {}), script),
            instagram=self._build_instagram(payload.get("instagram", {}), source_citation),
            x=self._build_x(payload.get("x", {}), source_citation),
            facebook=self._build_facebook(payload.get("facebook", {})),
        )

    def _parse_json(self, raw_response: str) -> dict:
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError as error:
            raise StoryGenerationError(
                f"LLM response is not valid JSON: {error}"
            ) from error

    def _build_tiktok(self, raw: dict, script: str) -> TikTokAdaptation:
        hashtags = raw.get("hashtags", [])
        if not (MIN_HASHTAGS <= len(hashtags) <= MAX_HASHTAGS):
            raise StoryGenerationError(
                f"TikTok/Reels must have {MIN_HASHTAGS}-{MAX_HASHTAGS} hashtags, "
                f"got {len(hashtags)}."
            )
        if not all(tag.startswith("#") for tag in hashtags):
            raise StoryGenerationError("Every TikTok/Reels hashtag must start with '#'.")

        on_screen_hook_lines = raw.get("on_screen_hook_lines", [])
        if len(on_screen_hook_lines) != 2:
            raise StoryGenerationError(
                "TikTok/Reels must have exactly 2 on-screen hook lines "
                f"(the first two lines), got {len(on_screen_hook_lines)}."
            )

        description = raw.get("description", "")
        if not description.strip():
            raise StoryGenerationError("TikTok/Reels description must not be empty.")

        return TikTokAdaptation(
            script=script,
            on_screen_hook_lines=on_screen_hook_lines,
            hashtags=hashtags,
            description=description,
        )

    def _build_instagram(self, raw: dict, source_citation: str) -> InstagramAdaptation:
        slides = raw.get("carousel_slides", [])
        if not (MIN_CAROUSEL_SLIDES <= len(slides) <= MAX_CAROUSEL_SLIDES):
            raise StoryGenerationError(
                f"Instagram carousel must have {MIN_CAROUSEL_SLIDES}-{MAX_CAROUSEL_SLIDES} "
                f"slides, got {len(slides)}."
            )
        if source_citation not in slides[-1]:
            raise StoryGenerationError(
                "Instagram carousel's last slide must cite the source."
            )

        return InstagramAdaptation(carousel_slides=slides)

    def _build_x(self, raw: dict, source_citation: str) -> XAdaptation:
        tweets = raw.get("tweets", [])
        if not (MIN_TWEETS <= len(tweets) <= MAX_TWEETS):
            raise StoryGenerationError(
                f"X thread must have {MIN_TWEETS}-{MAX_TWEETS} tweets, got {len(tweets)}."
            )
        if len(tweets[0].split()) < MIN_FIRST_TWEET_WORDS:
            raise StoryGenerationError(
                "X thread's first tweet must stand alone as the complete hook "
                f"(at least {MIN_FIRST_TWEET_WORDS} words)."
            )
        if source_citation not in tweets[-1]:
            raise StoryGenerationError("X thread's last tweet must cite the source.")

        return XAdaptation(tweets=tweets)

    def _build_facebook(self, raw: dict) -> FacebookAdaptation:
        post = raw.get("post", "")
        if not post.strip().endswith("?"):
            raise StoryGenerationError(
                "Facebook post must close with a question to the audience."
            )
        if len(post.split()) < MIN_FACEBOOK_POST_WORDS:
            raise StoryGenerationError(
                f"Facebook post must be at least {MIN_FACEBOOK_POST_WORDS} words "
                "(longer/more conversational than the other platforms)."
            )

        return FacebookAdaptation(post=post)
