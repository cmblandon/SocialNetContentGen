"""
Tests for FFmpegCompositor — FFmpeg video composition wrapper.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.editorial.core.exceptions import StoryGenerationError
from src.editorial.infrastructure.video.ffmpeg_compositor import FFmpegCompositor


class TestFFmpegCompositor:
    """Tests for FFmpeg compositor."""

    def test_raises_when_ffmpeg_not_found(self):
        """Test that missing ffmpeg raises error."""
        with patch.object(FFmpegCompositor, "_find_ffmpeg", return_value=None):
            with pytest.raises(StoryGenerationError, match="FFmpeg not found"):
                FFmpegCompositor()

    def test_initializes_with_provided_path(self):
        """Test initialization with explicit ffmpeg path."""
        compositor = FFmpegCompositor(ffmpeg_path="/usr/bin/ffmpeg")
        assert compositor.ffmpeg_path == "/usr/bin/ffmpeg"

    def test_finds_ffmpeg_in_path(self):
        """Test that ffmpeg is found in system PATH."""
        compositor = FFmpegCompositor()
        assert compositor.ffmpeg_path is not None
        assert os.path.exists(compositor.ffmpeg_path)

    def test_raises_when_audio_file_missing(self):
        """Test that missing audio file raises error."""
        compositor = FFmpegCompositor()

        with tempfile.TemporaryDirectory() as tmpdir:
            visual_path = os.path.join(tmpdir, "image.jpg")
            Path(visual_path).touch()

            with pytest.raises(StoryGenerationError, match="Audio file not found"):
                compositor.composite(
                    audio_path="/nonexistent/audio.mp3",
                    visual_path=visual_path,
                    subtitle_path=None,
                    output_path=os.path.join(tmpdir, "output.mp4"),
                )

    def test_raises_when_visual_file_missing(self):
        """Test that missing visual file raises error."""
        compositor = FFmpegCompositor()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.mp3")
            Path(audio_path).touch()

            with pytest.raises(StoryGenerationError, match="Visual file not found"):
                compositor.composite(
                    audio_path=audio_path,
                    visual_path="/nonexistent/image.jpg",
                    subtitle_path=None,
                    output_path=os.path.join(tmpdir, "output.mp4"),
                )

    def test_raises_when_subtitle_file_missing(self):
        """Test that missing subtitle file raises error."""
        compositor = FFmpegCompositor()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.mp3")
            visual_path = os.path.join(tmpdir, "image.jpg")
            Path(audio_path).touch()
            Path(visual_path).touch()

            with pytest.raises(StoryGenerationError, match="Subtitle file not found"):
                compositor.composite(
                    audio_path=audio_path,
                    visual_path=visual_path,
                    subtitle_path="/nonexistent/subs.srt",
                    output_path=os.path.join(tmpdir, "output.mp4"),
                )

    def test_builds_ffmpeg_command_without_subtitles(self):
        """Test FFmpeg command construction without subtitles."""
        compositor = FFmpegCompositor()
        cmd = compositor._build_ffmpeg_command(
            audio_path="/path/to/audio.mp3",
            visual_path="/path/to/image.jpg",
            subtitle_path=None,
            output_path="/path/to/output.mp4",
            duration_seconds=10,
        )

        assert cmd[0] == compositor.ffmpeg_path
        assert "-loop" in cmd
        assert "1" in cmd
        assert "/path/to/audio.mp3" in cmd
        assert "/path/to/image.jpg" in cmd
        assert "libx264" in cmd  # H.264 codec
        assert "aac" in cmd  # AAC audio
        assert "10" in cmd  # Duration
        assert "/path/to/output.mp4" in cmd

    def test_builds_ffmpeg_command_with_subtitles(self):
        """Test FFmpeg command construction with subtitles."""
        compositor = FFmpegCompositor()
        cmd = compositor._build_ffmpeg_command(
            audio_path="/path/to/audio.mp3",
            visual_path="/path/to/image.jpg",
            subtitle_path="/path/to/subs.srt",
            output_path="/path/to/output.mp4",
            duration_seconds=10,
        )

        # Should include subtitle filter
        assert any("subtitles=" in str(arg) for arg in cmd)

    def test_creates_output_directory(self):
        """Test that output directory is created if it doesn't exist."""
        compositor = FFmpegCompositor()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.mp3")
            visual_path = os.path.join(tmpdir, "image.jpg")
            output_path = os.path.join(tmpdir, "subdir", "output.mp4")

            Path(audio_path).touch()
            Path(visual_path).touch()

            # Mock subprocess to avoid actual ffmpeg execution
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = StoryGenerationError("Mocked error")
                try:
                    compositor.composite(
                        audio_path=audio_path,
                        visual_path=visual_path,
                        subtitle_path=None,
                        output_path=output_path,
                    )
                except StoryGenerationError:
                    pass

                # Verify directory was created
                assert Path(os.path.dirname(output_path)).exists()

    def test_measures_audio_duration_when_not_supplied(self):
        """Omitting duration_seconds measures the audio with ffprobe."""
        compositor = FFmpegCompositor()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.mp3")
            visual_path = os.path.join(tmpdir, "image.jpg")
            output_path = os.path.join(tmpdir, "output.mp4")
            Path(audio_path).touch()
            Path(visual_path).touch()

            with patch(
                "src.editorial.infrastructure.video.ffmpeg_compositor.probe_duration_ms",
                return_value=6400,
            ) as probe:
                with patch("subprocess.run") as mock_run:
                    mock_run.side_effect = lambda *a, **k: Path(output_path).write_bytes(b"v")
                    compositor.composite(
                        audio_path=audio_path,
                        visual_path=visual_path,
                        subtitle_path=None,
                        output_path=output_path,
                    )

            probe.assert_called_once_with(audio_path)
            # 6400ms rounds to 6s, and that is what FFmpeg is told.
            assert "6" in mock_run.call_args[0][0]

    def test_escapes_path_for_ffmpeg(self):
        """Test path escaping for FFmpeg filter syntax."""
        # Test single quote escaping
        escaped = FFmpegCompositor._escape_path("/path/to/file's.srt")
        assert "\\'" in escaped

        # Test backslash escaping
        escaped = FFmpegCompositor._escape_path("C:\\path\\to\\file.srt")
        assert "\\\\" in escaped

    def test_raises_on_ffmpeg_timeout(self):
        """Test that FFmpeg timeout raises error."""
        compositor = FFmpegCompositor()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.mp3")
            visual_path = os.path.join(tmpdir, "image.jpg")
            Path(audio_path).touch()
            Path(visual_path).touch()

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 300)

                with pytest.raises(StoryGenerationError, match="FFmpeg timed out"):
                    compositor.composite(
                        audio_path=audio_path,
                        visual_path=visual_path,
                        subtitle_path=None,
                        output_path=os.path.join(tmpdir, "output.mp4"),
                        duration_seconds=10,
                    )

    def test_raises_on_ffmpeg_failure(self):
        """Test that FFmpeg errors are propagated."""
        compositor = FFmpegCompositor()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.mp3")
            visual_path = os.path.join(tmpdir, "image.jpg")
            Path(audio_path).touch()
            Path(visual_path).touch()

            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.CalledProcessError(
                    1, "ffmpeg", stderr="Encoding error"
                )

                # Duration is supplied so the failure under test is the
                # composition call itself, not duration measurement.
                with pytest.raises(StoryGenerationError, match="FFmpeg failed: Encoding error"):
                    compositor.composite(
                        audio_path=audio_path,
                        visual_path=visual_path,
                        subtitle_path=None,
                        output_path=os.path.join(tmpdir, "output.mp4"),
                        duration_seconds=10,
                    )

    def test_validates_output_file(self):
        """Test that empty output file raises error."""
        compositor = FFmpegCompositor()

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio.mp3")
            visual_path = os.path.join(tmpdir, "image.jpg")
            output_path = os.path.join(tmpdir, "output.mp4")

            Path(audio_path).touch()
            Path(visual_path).touch()

            with patch("subprocess.run"):
                # Create empty output file
                Path(output_path).touch()

                with pytest.raises(StoryGenerationError, match="empty output"):
                    compositor.composite(
                        audio_path=audio_path,
                        visual_path=visual_path,
                        subtitle_path=None,
                        output_path=output_path,
                        duration_seconds=10,
                    )


# Need to import subprocess for the tests
import subprocess
