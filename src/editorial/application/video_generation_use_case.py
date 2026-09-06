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

from sqlalchemy.orm import Session

from src.editorial.application.subtitle_generation_use_case import SubtitleGenerationUseCase
from src.editorial.core.ports import IImageClient, ITextToSpeechClient, IVideoCompositor
from src.editorial.infrastructure.persistence.models import (
    PlatformVersion,
    VideoGeneration,
    VideoGenerationStatus,
)

# Chapters are authored in Spanish; any other language is a translation.
SOURCE_LANGUAGE = "es"
SUPPORTED_LANGUAGES = ("es", "en")
DEFAULT_VIDEO_ROOT = Path("data/videos_generated")


class ScriptNotApprovedError(Exception):
    """Raised when video generation is attempted for a PlatformVersion whose
    script has not been approved (specs/script-approval-workflow)."""


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
    """The deterministic per-(chapter, language) file paths a run reads and
    writes. Shared by first attempts and retries so retries can reuse
    whatever the failed attempt already produced."""

    audio_path: Path
    visual_path: Path
    subtitle_path: Path
    video_path: Path

    def ensure_directory(self) -> None:
        self.video_path.parent.mkdir(parents=True, exist_ok=True)


class VideoGenerationUseCase:
    def __init__(
        self,
        tts_client: ITextToSpeechClient,
        image_client: IImageClient,
        compositor: IVideoCompositor,
        subtitle_use_case: SubtitleGenerationUseCase,
        video_root: Optional[Path] = None,
    ):
        self._tts_client = tts_client
        self._image_client = image_client
        self._compositor = compositor
        self._subtitle_use_case = subtitle_use_case
        self._video_root = video_root or DEFAULT_VIDEO_ROOT

    def generate_video(
        self, session: Session, platform_version_id: str, language: str
    ) -> VideoGenerationResult:
        """
        Generate a video for one platform version in one language.

        Raises ScriptNotApprovedError when the script is not approved, and
        ValueError for an unknown platform version or unsupported language.
        Every other failure is reported through the returned result.
        """
        self._require_supported_language(language)
        platform_version = self._load_approved_platform_version(session, platform_version_id)

        video_generation = VideoGeneration(
            platform_version=platform_version,
            language=language,
            status=VideoGenerationStatus.PENDING,
        )
        session.add(video_generation)
        session.commit()

        return self._run_pipeline(session, video_generation, platform_version)

    def retry_video_generation(
        self, session: Session, video_generation_id: str
    ) -> VideoGenerationResult:
        """
        Retry a failed generation, reusing any audio/visual/subtitle files the
        failed attempt left behind (spec: "Retry uses cached audio and
        visuals"). Recorded as a new row linked to the original via
        `retry_of_id` so the audit trail keeps both attempts.
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

        return self._run_pipeline(session, retry, platform_version)

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
            self._produce_subtitles(chapter.script, language, audio_duration_ms, workspace)
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
        self, script: str, language: str, audio_duration_ms: int, workspace: _Workspace
    ) -> None:
        try:
            draft = self._subtitle_use_case.translate_and_generate_subtitles(
                script=script,
                source_language=SOURCE_LANGUAGE,
                target_language=language,
                audio_duration_ms=audio_duration_ms,
            )
            workspace.subtitle_path.write_text(draft.to_srt(), encoding="utf-8")
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
            audio_path=directory / f"{chapter_id}.mp3",
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
