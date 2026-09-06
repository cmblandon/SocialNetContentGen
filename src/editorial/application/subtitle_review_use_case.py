"""
SubtitleReviewUseCase — generate, read, and edit a chapter's caption tracks
(specs/subtitle-generation-and-approval/spec.md).

Generation is gated on script approval for the same reason video generation
is: captions transcribe the narration, so producing them from unapproved text
would put words on screen no editor has signed off on.

Editing preserves timing by construction — an edit replaces the text of
existing segments and cannot add, remove, or re-time them. Timing came from
measured audio; letting a text edit disturb it would desynchronize captions
from speech, and re-deriving it would need another TTS call.
"""
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from src.editorial.application.script_approval import (
    ChapterNotFoundError,
    is_script_approved,
)
from src.editorial.application.subtitle_generation_use_case import (
    SubtitleGenerationUseCase,
)
from src.editorial.core.entities import SubtitleDraft, SubtitleLine
from src.editorial.core.ports import ITextToSpeechClient
from src.editorial.infrastructure.persistence.models import Chapter
from src.editorial.infrastructure.persistence.subtitle_store import (
    StoredSubtitle,
    SubtitleStore,
)

SOURCE_LANGUAGE = "es"
SUBTITLE_LANGUAGES = ("es", "en")


class ScriptNotApprovedError(Exception):
    """Raised when subtitles are requested for an unapproved script."""


class SubtitlesNotGeneratedError(Exception):
    """Raised when an edit targets a track that does not exist yet."""


class SegmentCountMismatchError(Exception):
    """Raised when an edit supplies a different number of segments than the
    track has — timing is preserved per segment, so the counts must line up."""


@dataclass
class SubtitleSegmentEdit:
    """One replacement caption text, positionally matched to a segment."""

    index: int
    text: str


class SubtitleReviewUseCase:
    def __init__(
        self,
        tts_client: ITextToSpeechClient,
        subtitle_use_case: SubtitleGenerationUseCase,
        subtitle_store: Optional[SubtitleStore] = None,
    ):
        self._tts_client = tts_client
        self._subtitle_use_case = subtitle_use_case
        self._store = subtitle_store or SubtitleStore()

    def generate(self, session: Session, chapter_id: str) -> list[StoredSubtitle]:
        """
        Generate Spanish and English tracks for a chapter.

        Already-generated tracks are returned untouched rather than
        regenerated, so calling this twice cannot discard an editor's work.
        """
        chapter = self._require_approved_chapter(session, chapter_id)
        self._store.ensure_directories(chapter_id)

        tracks = []
        for language in SUBTITLE_LANGUAGES:
            existing = self._store.read(chapter_id, language)
            if existing is not None:
                tracks.append(existing)
                continue

            duration_ms = self._resolve_audio_duration(chapter, language)
            draft = self._subtitle_use_case.translate_and_generate_subtitles(
                script=chapter.script,
                source_language=SOURCE_LANGUAGE,
                target_language=language,
                audio_duration_ms=duration_ms,
            )
            tracks.append(self._store.write(chapter_id, draft, edited=False))

        return tracks

    def get(self, session: Session, chapter_id: str) -> list[StoredSubtitle]:
        """Return whichever tracks exist; an ungenerated chapter yields []."""
        self._require_chapter(session, chapter_id)
        return [
            track
            for track in (
                self._store.read(chapter_id, language) for language in SUBTITLE_LANGUAGES
            )
            if track is not None
        ]

    def update(
        self,
        session: Session,
        chapter_id: str,
        language: str,
        segments: list[SubtitleSegmentEdit],
    ) -> StoredSubtitle:
        """Replace segment text, keeping every start/end time as generated."""
        self._require_chapter(session, chapter_id)
        if language not in SUBTITLE_LANGUAGES:
            raise ValueError(
                f"Unsupported language '{language}'; expected one of {SUBTITLE_LANGUAGES}."
            )

        existing = self._store.read(chapter_id, language)
        if existing is None:
            raise SubtitlesNotGeneratedError(
                f"Chapter {chapter_id} has no '{language}' subtitles to edit."
            )

        current_lines = existing.draft.subtitle_lines
        if len(segments) != len(current_lines):
            raise SegmentCountMismatchError(
                f"Chapter {chapter_id} '{language}' track has {len(current_lines)} "
                f"segments, but {len(segments)} were supplied — timing is preserved "
                "per segment, so segments cannot be added or removed."
            )

        by_index = {segment.index: segment.text for segment in segments}
        if by_index.keys() != {line.index for line in current_lines}:
            raise SegmentCountMismatchError(
                f"Chapter {chapter_id} '{language}' edit does not match the "
                "track's segment indices."
            )

        edited_draft = SubtitleDraft(
            language=language,
            subtitle_lines=[
                SubtitleLine(
                    index=line.index,
                    start_time=line.start_time,
                    end_time=line.end_time,
                    text=by_index[line.index].strip(),
                )
                for line in current_lines
            ],
        )

        return self._store.write(chapter_id, edited_draft, edited=True)

    def _resolve_audio_duration(self, chapter: Chapter, language: str) -> int:
        """
        Measure the narration audio, synthesizing it only if it is not already
        on disk. The file lives at the same path video generation reads, so a
        later video run reuses this synthesis instead of paying for it twice.
        """
        audio_path = self._store.audio_path(chapter.id, language)
        if audio_path.exists() and audio_path.stat().st_size > 0:
            return self._tts_client.get_audio_duration(str(audio_path))

        narration = self._subtitle_use_case.translate_script(
            chapter.script, SOURCE_LANGUAGE, language
        )
        return self._tts_client.generate_speech(
            text=narration, language=language, output_path=str(audio_path)
        )

    def _require_approved_chapter(self, session: Session, chapter_id: str) -> Chapter:
        chapter = self._require_chapter(session, chapter_id)
        if not is_script_approved(chapter):
            raise ScriptNotApprovedError(
                "Script must be approved before subtitle generation."
            )
        return chapter

    @staticmethod
    def _require_chapter(session: Session, chapter_id: str) -> Chapter:
        chapter = session.get(Chapter, chapter_id)
        if chapter is None:
            raise ChapterNotFoundError(f"Chapter {chapter_id} does not exist.")
        return chapter
