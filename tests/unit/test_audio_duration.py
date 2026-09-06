"""
Tests for audio duration measurement via ffprobe.

Subtitle timing is built on this number, so the contract under test is that
an unmeasurable file raises rather than degrading to an estimate.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.editorial.core.exceptions import StoryGenerationError
from src.editorial.infrastructure.video.audio_duration import find_ffprobe, probe_duration_ms

_HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def test_raises_when_ffprobe_is_missing():
    with patch(
        "src.editorial.infrastructure.video.audio_duration.find_ffprobe", return_value=None
    ):
        with pytest.raises(StoryGenerationError, match="ffprobe not found"):
            probe_duration_ms("/tmp/whatever.mp3")


def test_raises_when_ffprobe_cannot_read_the_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        not_audio = os.path.join(tmpdir, "notaudio.mp3")
        Path(not_audio).write_bytes(b"this is not audio")

        with pytest.raises(StoryGenerationError, match="could not read"):
            probe_duration_ms(not_audio, ffprobe_path=find_ffprobe() or "ffprobe")


def test_raises_when_duration_is_unparseable():
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="N/A\n", stderr="")
    with patch("subprocess.run", return_value=completed):
        with pytest.raises(StoryGenerationError, match="unparseable duration"):
            probe_duration_ms("/tmp/audio.mp3", ffprobe_path="/usr/bin/ffprobe")


def test_raises_when_duration_is_non_positive():
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="0.0\n", stderr="")
    with patch("subprocess.run", return_value=completed):
        with pytest.raises(StoryGenerationError, match="non-positive duration"):
            probe_duration_ms("/tmp/audio.mp3", ffprobe_path="/usr/bin/ffprobe")


def test_converts_seconds_to_milliseconds():
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="4.128000\n", stderr=""
    )
    with patch("subprocess.run", return_value=completed):
        assert probe_duration_ms("/tmp/audio.mp3", ffprobe_path="/usr/bin/ffprobe") == 4128


def test_raises_on_ffprobe_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffprobe", 30)):
        with pytest.raises(StoryGenerationError, match="timed out"):
            probe_duration_ms("/tmp/audio.mp3", ffprobe_path="/usr/bin/ffprobe")


@pytest.mark.skipif(not _HAS_FFMPEG, reason="FFmpeg/ffprobe not installed")
def test_measures_a_real_audio_file():
    """Round-trip against real ffmpeg output: a 3s tone must measure ~3000ms."""
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "tone.mp3")
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=3",
                audio_path,
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )

        duration_ms = probe_duration_ms(audio_path)

        # MP3 frame padding makes this slightly inexact; 100ms is ample.
        assert abs(duration_ms - 3000) < 100
