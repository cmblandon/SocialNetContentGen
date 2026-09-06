"""
VideoGenerationUseCase — turns an approved script into a video file.

Per specs/video-generation-from-script/spec.md the pipeline is: check script
approval -> TTS audio -> visuals -> subtitles -> FFmpeg composition ->
persisted metadata. Every step writes to a deterministic path under
`data/videos_generated/{platform}/{language}/`, which is what makes retry
cheap: a run that failed in composition finds the audio and image from the
previous attempt already on disk and skips straight to FFmpeg.

Failures are recorded, not raised: a step that fails leaves the
VideoGeneration row FAILED with the failing step named in `error_message`,
so the retry endpoint has something concrete to act on. The one exception is
the approval gate — generating video for an unapproved script is a caller
bug, not a recoverable outcome, so it raises.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.editorial.application.subtitle_generation_use_case import SubtitleGenerationUseCase
from src.editorial.core.ports import IImageClient, ITextToSpeechClient, IVideoCompositor
from src.editorial.infrastructure.persistence.models import (
    PlatformVersion,
    VideoGeneration,
    VideoGenerationStatus,
)
from src.editorial.infrastructure.persistence.subtitle_store import SubtitleStore

# Chapters are authored in Spanish; any other language is a translation.
SOURCE_LANGUAGE = "es"
SUPPORTED_LANGUAGES = ("es", "en")
DEFAULT_VIDEO_ROOT = Path("data/videos_generated")


class ScriptNotApprovedError(Exception):
    """Raised when video generation is attempted for a PlatformVersion whose
    script has not been approved (specs/script-approval-workflow)."""


class GenerationAlreadyExistsError(Exception):
    """Raised when a generation is requested for a (platform version,
    language) that already has one pending or generated.

    Every attempt for a given platform and language resolves to the same
    output paths, so two live attempts would have two workers writing the
    same MP4 concurrently — interleaved writes producing a corrupt file — and
    would pay for the same narration twice. Retrying a failed attempt is the
    supported way to produce a new one."""


@dataclass
class VideoGenerationResult:
    """Outcome of one video generation attempt."""

    video_generation_id: str
    status: VideoGenerationStatus
    video_file_path: Optional[str] = None
    subtitle_file_path: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.status == VideoGenerationStatus.GENERATED


@dataclass
class _Workspace:
    """
    The deterministic file paths a run reads and writes.

    Audio and the canonical subtitle track are keyed by (chapter, language)
    only — they derive from the chapter's script, not from the platform — so
    all four of a chapter's platform videos share one synthesis and one
    editable caption file. Only the visual and the MP4 are per-platform, plus
    the per-platform SRT copy the spec names, which composition writes from
    the canonical track.
    """

    audio_path: Path
    canonical_subtitle_path: Path
    visual_path: Path
    subtitle_path: Path
    video_path: Path

    def ensure_directory(self) -> None:
        self.video_path.parent.mkdir(parents=True, exist_ok=True)
        self.audio_path.parent.mkdir(parents=True, exist_ok=True)
        self.canonical_subtitle_path.parent.mkdir(parents=True, exist_ok=True)


class VideoGenerationUseCase:
    def __init__(
        self,
        tts_client: ITextToSpeechClient,
        image_client: IImageClient,
        compositor: IVideoCompositor,
        subtitle_use_case: SubtitleGenerationUseCase,
        subtitle_store: Optional[SubtitleStore] = None,
        video_root: Optional[Path] = None,
    ):
        self._tts_client = tts_client
        self._image_client = image_client
        self._compositor = compositor
        self._subtitle_use_case = subtitle_use_case
        self._subtitle_store = subtitle_store or SubtitleStore()
        self._video_root = video_root or DEFAULT_VIDEO_ROOT

    def create_pending(
        self, session: Session, platform_version_id: str, language: str
    ) -> VideoGeneration:
        """
        Record an intent to generate, without doing any of the work.

        Split from the pipeline so an HTTP caller can validate the request,
        persist a PENDING row, and return its id immediately while
        composition runs in the background (specs/video-generation-from-script:
        "creates a VideoGeneration record with status = pending and returns
        immediately").

        Raises ScriptNotApprovedError when the script is not approved, and
        ValueError for an unknown platform version or unsupported language —
        all before any row exists, so a rejected request leaves no trace.
        """
        self._require_supported_language(language)
        platform_version = self._load_approved_platform_version(session, platform_version_id)
        self._require_no_live_generation(session, platform_version_id, language)

        video_generation = VideoGeneration(
            platform_version=platform_version,
            language=language,
            status=VideoGenerationStatus.PENDING,
        )
        session.add(video_generation)
        session.commit()
        return video_generation

    @staticmethod
    def _require_no_live_generation(
        session: Session, platform_version_id: str, language: str
    ) -> None:
        existing = session.execute(
            select(VideoGeneration)
            .where(
                VideoGeneration.platform_version_id == platform_version_id,
                VideoGeneration.language == language,
                VideoGeneration.deleted_at.is_(None),
                VideoGeneration.status.in_(
                    (VideoGenerationStatus.PENDING, VideoGenerationStatus.GENERATED)
                ),
            )
            .limit(1)
        ).scalar_one_or_none()

        if existing is not None:
            raise GenerationAlreadyExistsError(
                f"PlatformVersion {platform_version_id} already has a "
                f"'{existing.status.value}' video in '{language}' "
                f"(VideoGeneration {existing.id})."
            )

    def run_pending(self, session: Session, video_generation_id: str) -> VideoGenerationResult:
        """
        Run the pipeline for an already-created PENDING row.

        Refuses a row that is not PENDING: re-running a GENERATED row would
        redo paid work for a video that already exists, and re-running one
        already in flight would have two workers writing the same files.
        """
        video_generation = session.get(VideoGeneration, video_generation_id)
        if video_generation is None:
            raise ValueError(f"VideoGeneration {video_generation_id} does not exist.")
        if video_generation.status != VideoGenerationStatus.PENDING:
            raise ValueError(
                f"VideoGeneration {video_generation_id} is "
                f"'{video_generation.status.value}', not 'pending'."
            )

        platform_version = self._load_approved_platform_version(
            session, video_generation.platform_version_id
        )
        return self._run_pipeline(session, video_generation, platform_version)

    def generate_video(
        self, session: Session, platform_version_id: str, language: str
    ) -> VideoGenerationResult:
        """Create the record and run the pipeline synchronously."""
        video_generation = self.create_pending(session, platform_version_id, language)
        return self.run_pending(session, video_generation.id)

    def create_retry(self, session: Session, video_generation_id: str) -> VideoGeneration:
        """
        Record a retry of a failed generation, without doing the work.

        A new row linked to the original via `retry_of_id`, so the audit trail
        keeps both attempts rather than overwriting the failure.
        """
        failed = session.get(VideoGeneration, video_generation_id)
        if failed is None:
            raise ValueError(f"VideoGeneration {video_generation_id} does not exist.")
        if failed.status != VideoGenerationStatus.FAILED:
            raise ValueError(
                f"VideoGeneration {video_generation_id} is '{failed.status.value}', "
                "not 'failed' — only failed generations can be retried."
            )

        platform_version = self._load_approved_platform_version(
            session, failed.platform_version_id
        )

        retry = VideoGeneration(
            platform_version=platform_version,
            language=failed.language,
            status=VideoGenerationStatus.PENDING,
            retry_of_id=failed.id,
        )
        session.add(retry)
        session.commit()
        return retry

    def retry_video_generation(
        self, session: Session, video_generation_id: str
    ) -> VideoGenerationResult:
        """
        Retry a failed generation synchronously, reusing any audio/visual/
        subtitle files the failed attempt left behind (spec: "Retry uses
        cached audio and visuals").
        """
        retry = self.create_retry(session, video_generation_id)
        return self.run_pending(session, retry.id)

    def _run_pipeline(
        self,
        session: Session,
        video_generation: VideoGeneration,
        platform_version: PlatformVersion,
    ) -> VideoGenerationResult:
        chapter = platform_version.chapter
        language = video_generation.language
        workspace = self._build_workspace(
            platform=platform_version.platform.value,
            language=language,
            chapter_id=chapter.id,
        )
        workspace.ensure_directory()

        try:
            narration = self._resolve_narration(chapter.script, language)
            audio_duration_ms = self._produce_audio(narration, language, workspace)
            self._produce_visual(chapter.visual_notes, chapter.source_citation, workspace)
            self._produce_subtitles(
                chapter.id, chapter.script, language, audio_duration_ms, workspace
            )
            self._compose(workspace, audio_duration_ms)
        except Exception as error:
            return self._record_failure(session, video_generation, error)

        return self._record_success(session, video_generation, workspace)

    def _resolve_narration(self, script: str, language: str) -> str:
        try:
            return self._subtitle_use_case.translate_script(script, SOURCE_LANGUAGE, language)
        except Exception as error:
            raise _StepError("translation", error) from error

    def _produce_audio(self, narration: str, language: str, workspace: _Workspace) -> int:
        if workspace.audio_path.exists() and workspace.audio_path.stat().st_size > 0:
            # Reused from a previous attempt: measure the file that is already
            # there rather than re-synthesizing it.
            try:
                return self._tts_client.get_audio_duration(str(workspace.audio_path))
            except Exception as error:
                raise _StepError("tts", error) from error
        try:
            return self._tts_client.generate_speech(
                text=narration, language=language, output_path=str(workspace.audio_path)
            )
        except Exception as error:
            raise _StepError("tts", error) from error

    def _produce_visual(
        self, visual_notes: Optional[str], source_citation: str, workspace: _Workspace
    ) -> None:
        if workspace.visual_path.exists() and workspace.visual_path.stat().st_size > 0:
            return

        directive = (visual_notes or "").strip()
        fallback_text = f"{directive or source_citation}\n\n{source_citation}"

        url = None
        if directive:
            try:
                url = self._image_client.search_image(directive)
            except Exception:
                # Search is best-effort: a provider failure falls back rather
                # than failing the whole generation.
                url = None

        if url:
            try:
                self._image_client.download_image(url, str(workspace.visual_path))
                return
            except Exception:
                pass  # fall through to the generated background

        try:
            self._image_client.create_fallback_image(
                fallback_text, str(workspace.visual_path)
            )
        except Exception as error:
            raise _StepError("visuals", error) from error

    def _produce_subtitles(
        self,
        chapter_id: str,
        script: str,
        language: str,
        audio_duration_ms: int,
        workspace: _Workspace,
    ) -> None:
        """
        Resolve the caption track, then copy it to the path the compositor
        burns in.

        An existing canonical track is reused rather than regenerated. That is
        what makes "edited subtitles are used in video composition"
        (specs/subtitle-generation-and-approval) true: regenerating here would
        silently discard an editor's corrections on every run.
        """
        try:
            stored = self._subtitle_store.read(chapter_id, language)
            if stored is None:
                draft = self._subtitle_use_case.translate_and_generate_subtitles(
                    script=script,
                    source_language=SOURCE_LANGUAGE,
                    target_language=language,
                    audio_duration_ms=audio_duration_ms,
                )
                stored = self._subtitle_store.write(chapter_id, draft, edited=False)

            workspace.subtitle_path.write_text(stored.draft.to_srt(), encoding="utf-8")
        except Exception as error:
            raise _StepError("subtitles", error) from error

    def _compose(self, workspace: _Workspace, audio_duration_ms: int) -> None:
        try:
            self._compositor.composite(
                audio_path=str(workspace.audio_path),
                visual_path=str(workspace.visual_path),
                subtitle_path=str(workspace.subtitle_path),
                output_path=str(workspace.video_path),
                duration_seconds=max(1, round(audio_duration_ms / 1000)),
            )
        except Exception as error:
            raise _StepError("composition", error) from error

    def _build_workspace(self, platform: str, language: str, chapter_id: str) -> _Workspace:
        directory = self._video_root / platform / language
        return _Workspace(
            audio_path=self._subtitle_store.audio_path(chapter_id, language),
            canonical_subtitle_path=self._subtitle_store.subtitle_path(chapter_id, language),
            visual_path=directory / f"{chapter_id}.jpg",
            subtitle_path=directory / f"{chapter_id}.srt",
            video_path=directory / f"{chapter_id}.mp4",
        )

    def _load_approved_platform_version(
        self, session: Session, platform_version_id: str
    ) -> PlatformVersion:
        platform_version = session.get(PlatformVersion, platform_version_id)
        if platform_version is None:
            raise ValueError(f"PlatformVersion {platform_version_id} does not exist.")
        if not platform_version.script_approved:
            raise ScriptNotApprovedError(
                f"PlatformVersion {platform_version_id} has no approved script — "
                "script must be approved before video generation."
            )
        return platform_version

    @staticmethod
    def _require_supported_language(language: str) -> None:
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language '{language}'; expected one of {SUPPORTED_LANGUAGES}."
            )

    @staticmethod
    def _record_failure(
        session: Session, video_generation: VideoGeneration, error: Exception
    ) -> VideoGenerationResult:
        video_generation.status = VideoGenerationStatus.FAILED
        video_generation.error_message = str(error)
        session.commit()
        return VideoGenerationResult(
            video_generation_id=video_generation.id,
            status=VideoGenerationStatus.FAILED,
            error_message=video_generation.error_message,
        )

    @staticmethod
    def _record_success(
        session: Session, video_generation: VideoGeneration, workspace: _Workspace
    ) -> VideoGenerationResult:
        video_generation.status = VideoGenerationStatus.GENERATED
        video_generation.video_file_path = str(workspace.video_path)
        video_generation.subtitle_file_path = str(workspace.subtitle_path)
        video_generation.generated_at = datetime.now(timezone.utc)
        video_generation.error_message = None
        session.commit()
        return VideoGenerationResult(
            video_generation_id=video_generation.id,
            status=VideoGenerationStatus.GENERATED,
            video_file_path=video_generation.video_file_path,
            subtitle_file_path=video_generation.subtitle_file_path,
        )


class _StepError(Exception):
    """Names the pipeline step that failed, so `error_message` tells the
    retry endpoint (and the editor) where the run broke."""

    def __init__(self, step: str, cause: Exception):
        super().__init__(f"{step} step failed: {cause}")
        self.step = step
        self.cause = cause
