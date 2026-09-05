"""
Domain entities for the editorial bounded context — plain dataclasses,
no dependency on SQLAlchemy or any external library (mirrors the style of
src/core/entities.py).
"""
from dataclasses import dataclass, field


@dataclass
class ChapterDraft:
    """One chapter as drafted by StoryWritingUseCase, before persistence."""

    title: str
    script: str
    visual_notes: str
    source_citation: str
    chapter_index: int


@dataclass
class StoryDraft:
    """A story as drafted by StoryWritingUseCase, before persistence."""

    summary: str
    chapters: list[ChapterDraft] = field(default_factory=list)


@dataclass
class TikTokAdaptation:
    """TikTok/Reels adaptation of a chapter (specs/platform-adaptation)."""

    script: str
    on_screen_hook_lines: list[str]
    hashtags: list[str]
    description: str


@dataclass
class InstagramAdaptation:
    """Instagram carousel adaptation of a chapter."""

    carousel_slides: list[str]


@dataclass
class XAdaptation:
    """X (Twitter) thread adaptation of a chapter."""

    tweets: list[str]


@dataclass
class FacebookAdaptation:
    """Facebook post adaptation of a chapter."""

    post: str


@dataclass
class PlatformAdaptations:
    """All four platform versions produced for one chapter."""

    tiktok: TikTokAdaptation
    instagram: InstagramAdaptation
    x: XAdaptation
    facebook: FacebookAdaptation
