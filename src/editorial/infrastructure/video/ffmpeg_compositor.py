"""
FFmpegCompositor — wraps FFmpeg for video composition.

Composites audio + visuals + subtitles into final MP4 video.
Handles 1080p H.264 codec with AAC audio and hardcoded subtitles.
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from src.editorial.core.exceptions import StoryGenerationError
from src.editorial.infrastructure.video.audio_duration import probe_duration_ms


class FFmpegCompositor:
    """Wrapper for FFmpeg video composition."""

    def __init__(self, ffmpeg_path: Optional[str] = None):
        """
        Initialize FFmpeg compositor.

        Args:
            ffmpeg_path: Path to ffmpeg binary (auto-detects if not provided)

        Raises:
            StoryGenerationError: If ffmpeg is not installed
        """
        self.ffmpeg_path = ffmpeg_path or self._find_ffmpeg()
        if not self.ffmpeg_path:
            raise StoryGenerationError(
                "FFmpeg not found. Install with: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"
            )

    def composite(
        self,
        audio_path: str,
        visual_path: str,
        subtitle_path: Optional[str],
        output_path: str,
        duration_seconds: Optional[int] = None,
    ) -> None:
        """
        Composite audio, visuals, and subtitles into MP4 video.

        Args:
            audio_path: Path to MP3/WAV audio file
            visual_path: Path to image file (JPEG/PNG)
            subtitle_path: Path to SRT subtitle file (optional)
            output_path: Path to save output MP4
            duration_seconds: Duration of video in seconds (auto-detect if None)

        Raises:
            StoryGenerationError: If composition fails
        """
        # Validate inputs
        if not os.path.exists(audio_path):
            raise StoryGenerationError(f"Audio file not found: {audio_path}")
        if not os.path.exists(visual_path):
            raise StoryGenerationError(f"Visual file not found: {visual_path}")
        if subtitle_path and not os.path.exists(subtitle_path):
            raise StoryGenerationError(f"Subtitle file not found: {subtitle_path}")

        # Create output directory
        output_dir = os.path.dirname(output_path)
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Auto-detect duration if not provided
        if duration_seconds is None:
            duration_seconds = self._get_audio_duration(audio_path)

        # Build FFmpeg command
        cmd = self._build_ffmpeg_command(
            audio_path=audio_path,
            visual_path=visual_path,
            subtitle_path=subtitle_path,
            output_path=output_path,
            duration_seconds=duration_seconds,
        )

        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
        except subprocess.TimeoutExpired as error:
            raise StoryGenerationError(f"FFmpeg timed out: {error}") from error
        except subprocess.CalledProcessError as error:
            raise StoryGenerationError(
                f"FFmpeg failed: {error.stderr}"
            ) from error

        # Validate output
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise StoryGenerationError(f"FFmpeg produced empty output: {output_path}")

    def _build_ffmpeg_command(
        self,
        audio_path: str,
        visual_path: str,
        subtitle_path: Optional[str],
        output_path: str,
        duration_seconds: int,
    ) -> list:
        """Build FFmpeg command for video composition."""
        cmd = [
            self.ffmpeg_path,
            "-y",  # Overwrite output
            "-loop",
            "1",  # Loop image
            "-i",
            visual_path,
            "-i",
            audio_path,
        ]

        if subtitle_path:
            cmd.extend(["-vf", f"subtitles={self._escape_path(subtitle_path)}"])

        cmd.extend(
            [
                "-c:v",
                "libx264",  # H.264 codec
                "-c:a",
                "aac",  # AAC audio
                "-pix_fmt",
                "yuv420p",  # Compatibility
                "-preset",
                "medium",  # Encoding speed/quality trade-off
                "-t",
                str(duration_seconds),  # Duration
                "-vf",
                "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",  # 1080p
                "-shortest",  # Stop at shortest input
                output_path,
            ]
        )

        return cmd

    def _get_audio_duration(self, audio_path: str) -> int:
        """Get audio duration in seconds, measured with ffprobe."""
        return max(1, round(probe_duration_ms(audio_path) / 1000))

    @staticmethod
    def _find_ffmpeg() -> Optional[str]:
        """Find ffmpeg in system PATH."""
        return shutil.which("ffmpeg")

    @staticmethod
    def _escape_path(path: str) -> str:
        """Escape path for FFmpeg command line."""
        # FFmpeg uses backslash escaping for special characters in filters
        return path.replace("\\", "\\\\").replace("'", "\\'")
