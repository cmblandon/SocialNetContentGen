"""
Audio duration measurement via ffprobe.

Subtitle timing is derived from how long the narration actually runs, so this
measures the synthesized file rather than estimating from word count: a
words-per-minute guess drifts against real TTS output (which varies with the
voice, punctuation, and pauses), and that drift accumulates across a chapter
until captions no longer line up with speech.

ffprobe ships with FFmpeg, which video composition already requires, so this
adds no new dependency.
"""
import shutil
import subprocess
from typing import Optional

from src.editorial.core.exceptions import StoryGenerationError

_PROBE_TIMEOUT_SECONDS = 30


def find_ffprobe() -> Optional[str]:
    """Locate the ffprobe binary, or None when it is not installed."""
    return shutil.which("ffprobe")


def probe_duration_ms(audio_path: str, ffprobe_path: Optional[str] = None) -> int:
    """
    Measure an audio (or video) file's duration in milliseconds.

    Raises StoryGenerationError when ffprobe is missing, the file cannot be
    read, or the reported duration is unusable — an unmeasurable file must
    not silently fall back to an estimate, because the caller would then
    build subtitle timing on a number it believes was measured.
    """
    binary = ffprobe_path or find_ffprobe()
    if not binary:
        raise StoryGenerationError(
            "ffprobe not found. It ships with FFmpeg — install with: "
            "brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"
        )

    try:
        result = subprocess.run(
            [
                binary,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=_PROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise StoryGenerationError(f"ffprobe timed out reading {audio_path}") from error
    except subprocess.CalledProcessError as error:
        raise StoryGenerationError(
            f"ffprobe could not read {audio_path}: {error.stderr.strip()}"
        ) from error

    raw = result.stdout.strip()
    try:
        seconds = float(raw)
    except ValueError as error:
        raise StoryGenerationError(
            f"ffprobe returned an unparseable duration for {audio_path}: {raw!r}"
        ) from error

    if seconds <= 0:
        raise StoryGenerationError(
            f"ffprobe reported a non-positive duration for {audio_path}: {seconds}"
        )

    return round(seconds * 1000)
