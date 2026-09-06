"""
Tests for canonical subtitle storage and SRT round-tripping.

The stored SRT is the source of truth once an editor has touched it, so
parsing it back must reproduce exactly what was written — otherwise an edit
would degrade a little on every read.
"""
import json

import pytest

from src.editorial.core.entities import SubtitleDraft, SubtitleLine
from src.editorial.infrastructure.persistence.subtitle_store import SubtitleStore


def _draft(language: str = "es") -> SubtitleDraft:
    return SubtitleDraft(
        language=language,
        subtitle_lines=[
            SubtitleLine(1, "00:00:00,000", "00:00:02,000", "Primera frase."),
            SubtitleLine(2, "00:00:02,000", "00:00:04,500", "Segunda frase."),
        ],
    )


@pytest.fixture
def store(tmp_path):
    return SubtitleStore(
        subtitle_root=tmp_path / "subtitles", audio_root=tmp_path / "audio"
    )


def test_srt_round_trips_without_loss():
    draft = _draft()
    parsed = SubtitleDraft.from_srt(draft.to_srt(), "es")

    assert parsed.subtitle_lines == draft.subtitle_lines


def test_parses_multi_row_caption_text():
    srt = "1\n00:00:00,000 --> 00:00:02,000\nPrimera linea\nsegunda linea"

    parsed = SubtitleDraft.from_srt(srt, "es")

    assert parsed.subtitle_lines[0].text == "Primera linea\nsegunda linea"


def test_parses_empty_srt_as_no_lines():
    assert SubtitleDraft.from_srt("", "es").subtitle_lines == []


@pytest.mark.parametrize(
    "malformed",
    [
        "1\n00:00:00,000 --> 00:00:02,000",  # missing text row
        "not-a-number\n00:00:00,000 --> 00:00:02,000\ntexto",  # bad index
        "1\n00:00:00,000 00:00:02,000\ntexto",  # missing arrow
    ],
)
def test_malformed_srt_raises(malformed):
    with pytest.raises(ValueError):
        SubtitleDraft.from_srt(malformed, "es")


def test_read_returns_none_before_anything_is_written(store):
    assert store.read("chapter-1", "es") is None


def test_write_then_read_preserves_content(store):
    store.write("chapter-1", _draft(), edited=False)

    stored = store.read("chapter-1", "es")

    assert stored is not None
    assert stored.language == "es"
    assert stored.edited is False
    assert stored.updated_at is not None
    assert stored.draft.subtitle_lines == _draft().subtitle_lines


def test_edited_flag_is_persisted(store):
    store.write("chapter-1", _draft(), edited=True)

    assert store.read("chapter-1", "es").edited is True


def test_languages_are_stored_independently(store):
    store.write("chapter-1", _draft("es"), edited=False)
    store.write("chapter-1", _draft("en"), edited=True)

    assert store.read("chapter-1", "es").edited is False
    assert store.read("chapter-1", "en").edited is True


def test_srt_is_written_at_the_canonical_path(store, tmp_path):
    store.write("chapter-1", _draft(), edited=False)

    path = tmp_path / "subtitles" / "chapter-1" / "es.srt"
    assert path.exists()
    assert "00:00:00,000 --> 00:00:02,000" in path.read_text(encoding="utf-8")


def test_srt_is_utf8_encoded(store):
    draft = SubtitleDraft(
        language="es",
        subtitle_lines=[SubtitleLine(1, "00:00:00,000", "00:00:01,000", "Año recién")],
    )
    store.write("chapter-1", draft, edited=False)

    assert store.read("chapter-1", "es").draft.subtitle_lines[0].text == "Año recién"


def test_srt_without_sidecar_reads_as_unedited(store, tmp_path):
    """A hand-dropped SRT is readable rather than rejected."""
    directory = tmp_path / "subtitles" / "chapter-1"
    directory.mkdir(parents=True)
    (directory / "es.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\ntexto", encoding="utf-8"
    )

    stored = store.read("chapter-1", "es")

    assert stored is not None
    assert stored.edited is False
    assert stored.updated_at is None


def test_corrupt_sidecar_does_not_break_reading(store, tmp_path):
    store.write("chapter-1", _draft(), edited=True)
    (tmp_path / "subtitles" / "chapter-1" / "es.meta.json").write_text(
        "{not json", encoding="utf-8"
    )

    stored = store.read("chapter-1", "es")

    assert stored is not None
    assert stored.edited is False  # falls back rather than raising


def test_empty_srt_file_counts_as_absent(store, tmp_path):
    directory = tmp_path / "subtitles" / "chapter-1"
    directory.mkdir(parents=True)
    (directory / "es.srt").touch()

    assert store.read("chapter-1", "es") is None


def test_meta_sidecar_records_edited_and_timestamp(store, tmp_path):
    store.write("chapter-1", _draft(), edited=True)

    meta = json.loads(
        (tmp_path / "subtitles" / "chapter-1" / "es.meta.json").read_text(encoding="utf-8")
    )

    assert meta["edited"] is True
    assert meta["updated_at"]


def test_audio_path_is_per_chapter_and_language(store, tmp_path):
    assert store.audio_path("chapter-1", "en") == tmp_path / "audio" / "chapter-1" / "en.mp3"
