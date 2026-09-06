"""
Canonical storage for chapter subtitles and narration audio.

Both derive from `chapter.script` and a language — never from the platform —
so they are stored once per (chapter, language) and reused across all of that
chapter's platform videos. Storing them per-platform instead would synthesize
the same narration four times and give an editor four separately-editable
copies of identical captions, which drift apart the moment one is corrected.
The per-platform SRT the spec names is written at composition time as a copy
of the canonical file (see VideoGenerationUseCase).

The SRT file is the source of truth for its text and timing. A sidecar
`.meta.json` records only what the file cannot: whether an editor has edited
it, and when it last changed.
"""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.editorial.core.entities import SubtitleDraft

DEFAULT_SUBTITLE_ROOT = Path("data/subtitles")
DEFAULT_AUDIO_ROOT = Path("data/audio")


@dataclass
class StoredSubtitle:
    """A stored subtitle track and the metadata around it."""

    language: str
    draft: SubtitleDraft
    edited: bool
    updated_at: Optional[datetime]


class SubtitleStore:
    """Reads and writes canonical subtitle tracks and narration audio paths."""

    def __init__(
        self,
        subtitle_root: Optional[Path] = None,
        audio_root: Optional[Path] = None,
    ):
        self._subtitle_root = subtitle_root or DEFAULT_SUBTITLE_ROOT
        self._audio_root = audio_root or DEFAULT_AUDIO_ROOT

    def subtitle_path(self, chapter_id: str, language: str) -> Path:
        return self._subtitle_root / chapter_id / f"{language}.srt"

    def audio_path(self, chapter_id: str, language: str) -> Path:
        return self._audio_root / chapter_id / f"{language}.mp3"

    def ensure_directories(self, chapter_id: str) -> None:
        (self._subtitle_root / chapter_id).mkdir(parents=True, exist_ok=True)
        (self._audio_root / chapter_id).mkdir(parents=True, exist_ok=True)

    def exists(self, chapter_id: str, language: str) -> bool:
        path = self.subtitle_path(chapter_id, language)
        return path.exists() and path.stat().st_size > 0

    def read(self, chapter_id: str, language: str) -> Optional[StoredSubtitle]:
        """Return the stored track, or None when nothing has been generated."""
        if not self.exists(chapter_id, language):
            return None

        srt_text = self.subtitle_path(chapter_id, language).read_text(encoding="utf-8")
        meta = self._read_meta(chapter_id, language)

        return StoredSubtitle(
            language=language,
            draft=SubtitleDraft.from_srt(srt_text, language),
            edited=bool(meta.get("edited", False)),
            updated_at=self._parse_timestamp(meta.get("updated_at")),
        )

    def write(
        self, chapter_id: str, draft: SubtitleDraft, *, edited: bool
    ) -> StoredSubtitle:
        """Persist a track, recording whether it came from an editor's hand."""
        self.ensure_directories(chapter_id)
        updated_at = datetime.now(timezone.utc)

        self.subtitle_path(chapter_id, draft.language).write_text(
            draft.to_srt(), encoding="utf-8"
        )
        self._meta_path(chapter_id, draft.language).write_text(
            json.dumps({"edited": edited, "updated_at": updated_at.isoformat()}),
            encoding="utf-8",
        )

        return StoredSubtitle(
            language=draft.language, draft=draft, edited=edited, updated_at=updated_at
        )

    def _meta_path(self, chapter_id: str, language: str) -> Path:
        return self._subtitle_root / chapter_id / f"{language}.meta.json"

    def _read_meta(self, chapter_id: str, language: str) -> dict:
        path = self._meta_path(chapter_id, language)
        if not path.exists():
            # An SRT without a sidecar predates the metadata or was dropped in
            # by hand; treat it as generated rather than refusing to read it.
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    @staticmethod
    def _parse_timestamp(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None
