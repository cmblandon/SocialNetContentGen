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


@dataclass
class SubtitleLine:
    """One subtitle line in SRT format."""

    index: int
    start_time: str
    end_time: str
    text: str

    def to_srt_block(self) -> str:
        """Render as SRT block: index, timecode, text."""
        return f"{self.index}\n{self.start_time} --> {self.end_time}\n{self.text}"


@dataclass
class SubtitleDraft:
    """Subtitles for one chapter, one language."""

    language: str
    subtitle_lines: list[SubtitleLine] = field(default_factory=list)

    def to_srt(self) -> str:
        """Render all subtitle lines as complete SRT file."""
        if not self.subtitle_lines:
            return ""
        blocks = [line.to_srt_block() for line in self.subtitle_lines]
        return "\n\n".join(blocks)

    @classmethod
    def from_srt(cls, srt_text: str, language: str) -> "SubtitleDraft":
        """
        Parse an SRT file back into subtitle lines.

        Needed because a stored SRT is the source of truth once an editor has
        touched it: re-reading it (rather than regenerating) is what lets an
        edit survive into the composited video.

        Raises ValueError on a block that is not well-formed, so a corrupt
        file surfaces instead of silently yielding partial subtitles.
        """
        lines: list[SubtitleLine] = []
        for block in [b for b in srt_text.strip().split("\n\n") if b.strip()]:
            rows = block.strip().split("\n")
            if len(rows) < 3:
                raise ValueError(f"Malformed SRT block (expected 3+ rows): {block!r}")

            try:
                index = int(rows[0].strip())
            except ValueError as error:
                raise ValueError(f"Malformed SRT index in block: {block!r}") from error

            timecode = rows[1]
            if "-->" not in timecode:
                raise ValueError(f"Malformed SRT timecode in block: {block!r}")
            start_time, _, end_time = timecode.partition("-->")

            lines.append(
                SubtitleLine(
                    index=index,
                    start_time=start_time.strip(),
                    end_time=end_time.strip(),
                    # Multi-row captions keep their internal line breaks.
                    text="\n".join(rows[2:]).strip(),
                )
            )

        return cls(language=language, subtitle_lines=lines)
