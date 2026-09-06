"""
Tests for VideoGenerationUseCase — per specs/video-generation-from-script/spec.md.

All external services (TTS, images, FFmpeg) are faked: what is under test is
the orchestration — that the approval gate holds, that each step's failure is
recorded rather than raised, that the Unsplash-to-fallback path is taken when
search yields nothing, and that a retry reuses what the failed attempt left
on disk instead of paying for TTS twice.
"""
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.editorial.application.subtitle_generation_use_case import SubtitleGenerationUseCase
from src.editorial.application.video_generation_use_case import (
    ScriptNotApprovedError,
    VideoGenerationUseCase,
)
from src.editorial.infrastructure.persistence.models import (
    ApprovalStatus,
    Base,
    Chapter,
    Document,
    PlatformName,
    PlatformVersion,
    Story,
    VideoGeneration,
    VideoGenerationStatus,
)
from src.editorial.core.entities import SubtitleDraft, SubtitleLine
from src.editorial.infrastructure.persistence.subtitle_store import SubtitleStore

CHAPTER_SCRIPT = "Primera frase del guion. Segunda frase del guion."
VISUAL_NOTES = "archival footage of military radar"
SOURCE_CITATION = "AARO, report, 2024-03-01"


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _make_platform_version(session, *, script_approved: bool) -> PlatformVersion:
    document = Document(
        title="AARO 2024 Annual Report",
        agency="AARO",
        doc_type="report",
        extracted_text="Full text.",
    )
    story = Story(document=document, summary="A radar contact goes unexplained.")
    chapter = Chapter(
        story=story,
        chapter_index=1,
        title="Part 1",
        script=CHAPTER_SCRIPT,
        visual_notes=VISUAL_NOTES,
        source_citation=SOURCE_CITATION,
    )
    platform_version = PlatformVersion(
        chapter=chapter,
        platform=PlatformName.TIKTOK,
        content="{}",
        status=ApprovalStatus.PENDING_REVIEW,
        script_approved=script_approved,
    )
    session.add_all([document, story, chapter, platform_version])
    session.commit()
    return platform_version


def _make_chapter_with_all_platforms(session) -> list[str]:
    """A chapter with all four platform versions, script approved."""
    document = Document(
        title="AARO 2024 Annual Report",
        agency="AARO",
        doc_type="report",
        extracted_text="Full text.",
    )
    story = Story(document=document, summary="A radar contact goes unexplained.")
    chapter = Chapter(
        story=story,
        chapter_index=1,
        title="Part 1",
        script=CHAPTER_SCRIPT,
        visual_notes=VISUAL_NOTES,
        source_citation=SOURCE_CITATION,
    )
    session.add_all([document, story, chapter])
    for platform in PlatformName:
        session.add(
            PlatformVersion(
                chapter=chapter,
                platform=platform,
                content="{}",
                status=ApprovalStatus.PENDING_REVIEW,
                script_approved=True,
            )
        )
    session.commit()
    return [pv.id for pv in chapter.platform_versions]


class FakeTTSClient:
    def __init__(self, duration_ms: int = 4000, error: Exception | None = None):
        self.duration_ms = duration_ms
        self.error = error
        self.calls: list[tuple[str, str]] = []
        self.measured: list[str] = []

    def generate_speech(self, text: str, language: str, output_path: str) -> int:
        self.calls.append((text, language))
        if self.error:
            raise self.error
        Path(output_path).write_bytes(b"fake-audio")
        return self.duration_ms

    def get_audio_duration(self, audio_path: str) -> int:
        self.measured.append(audio_path)
        return self.duration_ms


class FakeImageClient:
    def __init__(self, search_result: str | None = "https://example.test/a.jpg"):
        self.search_result = search_result
        self.search_queries: list[str] = []
        self.downloaded: list[str] = []
        self.fallback_texts: list[str] = []

    def search_image(self, query: str) -> str | None:
        self.search_queries.append(query)
        return self.search_result

    def download_image(self, url: str, output_path: str) -> None:
        self.downloaded.append(url)
        Path(output_path).write_bytes(b"fake-image")

    def create_fallback_image(self, text: str, output_path: str) -> None:
        self.fallback_texts.append(text)
        Path(output_path).write_bytes(b"fake-fallback")


class FakeCompositor:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[dict] = []

    def composite(
        self, audio_path, visual_path, subtitle_path, output_path, duration_seconds=None
    ) -> None:
        self.calls.append(
            {
                "audio_path": audio_path,
                "visual_path": visual_path,
                "subtitle_path": subtitle_path,
                "duration_seconds": duration_seconds,
            }
        )
        if self.error:
            raise self.error
        Path(output_path).write_bytes(b"fake-video")


class FakeLLMClient:
    """Translation stub — returns a marked English rendering."""

    def __init__(self):
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        return "First script sentence. Second script sentence."


def _subtitle_store(tmp_path) -> SubtitleStore:
    """Always tmp-scoped: a default-constructed store writes into the real
    data/ directory."""
    return SubtitleStore(
        subtitle_root=tmp_path / "subtitles", audio_root=tmp_path / "audio"
    )


def _build_use_case(tmp_path, *, tts=None, images=None, compositor=None, store=None):
    subtitle_use_case = SubtitleGenerationUseCase(
        FakeLLMClient(), cache_dir=tmp_path / "subtitle_cache"
    )
    return VideoGenerationUseCase(
        tts_client=tts or FakeTTSClient(),
        image_client=images or FakeImageClient(),
        compositor=compositor or FakeCompositor(),
        subtitle_use_case=subtitle_use_case,
        subtitle_store=store or _subtitle_store(tmp_path),
        video_root=tmp_path / "videos_generated",
    )


def test_generates_video_for_approved_script(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)
    use_case = _build_use_case(tmp_path)

    result = use_case.generate_video(session, platform_version.id, "es")

    assert result.succeeded
    assert result.status == VideoGenerationStatus.GENERATED
    assert Path(result.video_file_path).exists()
    assert Path(result.subtitle_file_path).exists()
    assert result.error_message is None


def test_refuses_to_generate_when_script_not_approved(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=False)
    use_case = _build_use_case(tmp_path)

    with pytest.raises(ScriptNotApprovedError):
        use_case.generate_video(session, platform_version.id, "es")

    assert session.query(VideoGeneration).count() == 0


def test_stores_video_under_platform_and_language_directory(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)
    use_case = _build_use_case(tmp_path)

    result = use_case.generate_video(session, platform_version.id, "es")

    expected = tmp_path / "videos_generated" / "tiktok" / "es"
    assert Path(result.video_file_path).parent == expected
    assert Path(result.video_file_path).name.endswith(".mp4")


def test_persists_metadata_on_success(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)
    use_case = _build_use_case(tmp_path)

    result = use_case.generate_video(session, platform_version.id, "es")

    record = session.get(VideoGeneration, result.video_generation_id)
    assert record.status == VideoGenerationStatus.GENERATED
    assert record.language == "es"
    assert record.generated_at is not None
    assert record.platform_version_id == platform_version.id


def test_rejects_unsupported_language(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)
    use_case = _build_use_case(tmp_path)

    with pytest.raises(ValueError, match="Unsupported language"):
        use_case.generate_video(session, platform_version.id, "fr")


def test_records_tts_failure_without_raising(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)
    use_case = _build_use_case(
        tmp_path, tts=FakeTTSClient(error=RuntimeError("quota exceeded"))
    )

    result = use_case.generate_video(session, platform_version.id, "es")

    assert result.status == VideoGenerationStatus.FAILED
    assert "tts step failed" in result.error_message
    assert "quota exceeded" in result.error_message
    assert result.video_file_path is None


def test_records_composition_failure_without_raising(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)
    use_case = _build_use_case(
        tmp_path, compositor=FakeCompositor(error=RuntimeError("encoder crashed"))
    )

    result = use_case.generate_video(session, platform_version.id, "es")

    assert result.status == VideoGenerationStatus.FAILED
    assert "composition step failed" in result.error_message


def test_falls_back_to_generated_image_when_search_finds_nothing(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)
    images = FakeImageClient(search_result=None)
    use_case = _build_use_case(tmp_path, images=images)

    result = use_case.generate_video(session, platform_version.id, "es")

    assert result.succeeded
    assert images.downloaded == []
    assert len(images.fallback_texts) == 1
    assert SOURCE_CITATION in images.fallback_texts[0]


def test_falls_back_when_image_download_fails(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)

    class FailingDownloadClient(FakeImageClient):
        def download_image(self, url, output_path):
            raise RuntimeError("404 from CDN")

    images = FailingDownloadClient()
    use_case = _build_use_case(tmp_path, images=images)

    result = use_case.generate_video(session, platform_version.id, "es")

    assert result.succeeded
    assert len(images.fallback_texts) == 1


def test_searches_unsplash_with_the_chapter_visual_directive(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)
    images = FakeImageClient()
    use_case = _build_use_case(tmp_path, images=images)

    use_case.generate_video(session, platform_version.id, "es")

    assert images.search_queries == [VISUAL_NOTES]


def test_composition_duration_matches_audio_duration(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)
    compositor = FakeCompositor()
    use_case = _build_use_case(
        tmp_path, tts=FakeTTSClient(duration_ms=7000), compositor=compositor
    )

    use_case.generate_video(session, platform_version.id, "es")

    assert compositor.calls[0]["duration_seconds"] == 7


def test_english_video_narrates_translated_script(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)
    tts = FakeTTSClient()
    use_case = _build_use_case(tmp_path, tts=tts)

    use_case.generate_video(session, platform_version.id, "en")

    narrated_text, language = tts.calls[0]
    assert language == "en"
    assert narrated_text != CHAPTER_SCRIPT  # translated, not the Spanish original


def test_retry_reuses_cached_audio_and_visuals(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)
    tts = FakeTTSClient()
    images = FakeImageClient()
    compositor = FakeCompositor(error=RuntimeError("encoder crashed"))
    use_case = _build_use_case(tmp_path, tts=tts, images=images, compositor=compositor)

    failed = use_case.generate_video(session, platform_version.id, "es")
    assert failed.status == VideoGenerationStatus.FAILED
    assert len(tts.calls) == 1

    # Composition now works; retry must not pay for TTS or image fetch again.
    compositor.error = None
    retried = use_case.retry_video_generation(session, failed.video_generation_id)

    assert retried.succeeded
    assert len(tts.calls) == 1, "TTS should have been reused, not re-requested"
    assert len(images.search_queries) == 1, "image should have been reused"
    # The reused audio's duration is measured off the file, not re-estimated.
    assert tts.measured == [
        str(tmp_path / "audio" / platform_version.chapter_id / "es.mp3")
    ]


def test_retry_reports_failure_when_cached_audio_cannot_be_measured(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)

    class UnmeasurableTTSClient(FakeTTSClient):
        def get_audio_duration(self, audio_path: str) -> int:
            raise RuntimeError("ffprobe could not read the file")

    tts = UnmeasurableTTSClient()
    compositor = FakeCompositor(error=RuntimeError("encoder crashed"))
    use_case = _build_use_case(tmp_path, tts=tts, compositor=compositor)

    failed = use_case.generate_video(session, platform_version.id, "es")
    compositor.error = None
    retried = use_case.retry_video_generation(session, failed.video_generation_id)

    # Better to fail loudly than to build subtitle timing on a guess.
    assert retried.status == VideoGenerationStatus.FAILED
    assert "tts step failed" in retried.error_message


def test_retry_links_to_the_original_attempt(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)
    compositor = FakeCompositor(error=RuntimeError("encoder crashed"))
    use_case = _build_use_case(tmp_path, compositor=compositor)

    failed = use_case.generate_video(session, platform_version.id, "es")
    compositor.error = None
    retried = use_case.retry_video_generation(session, failed.video_generation_id)

    record = session.get(VideoGeneration, retried.video_generation_id)
    assert record.retry_of_id == failed.video_generation_id
    assert session.query(VideoGeneration).count() == 2


def test_retry_refuses_a_generation_that_did_not_fail(session, tmp_path):
    platform_version = _make_platform_version(session, script_approved=True)
    use_case = _build_use_case(tmp_path)

    succeeded = use_case.generate_video(session, platform_version.id, "es")

    with pytest.raises(ValueError, match="only failed generations"):
        use_case.retry_video_generation(session, succeeded.video_generation_id)


def test_composition_uses_edited_subtitles_instead_of_regenerating(session, tmp_path):
    """specs/subtitle-generation-and-approval: an editor's corrections must
    reach the video, so an existing track is reused, never regenerated."""
    platform_version = _make_platform_version(session, script_approved=True)
    store = _subtitle_store(tmp_path)
    edited = SubtitleDraft(
        language="es",
        subtitle_lines=[
            SubtitleLine(1, "00:00:00,000", "00:00:04,000", "TEXTO CORREGIDO A MANO")
        ],
    )
    store.write(platform_version.chapter_id, edited, edited=True)

    use_case = _build_use_case(tmp_path, store=store)
    result = use_case.generate_video(session, platform_version.id, "es")

    assert result.succeeded
    burned_in = Path(result.subtitle_file_path).read_text(encoding="utf-8")
    assert "TEXTO CORREGIDO A MANO" in burned_in
    # The canonical track is untouched by the run.
    assert store.read(platform_version.chapter_id, "es").edited is True


def test_composition_writes_subtitles_to_the_per_platform_path(session, tmp_path):
    """The spec's per-platform SRT location is still populated, as a copy."""
    platform_version = _make_platform_version(session, script_approved=True)
    use_case = _build_use_case(tmp_path)

    result = use_case.generate_video(session, platform_version.id, "es")

    expected = (
        tmp_path
        / "videos_generated"
        / "tiktok"
        / "es"
        / f"{platform_version.chapter_id}.srt"
    )
    assert Path(result.subtitle_file_path) == expected
    assert expected.exists()


def test_audio_is_shared_across_platforms_of_the_same_chapter(session, tmp_path):
    """One narration synthesis serves every platform video for a chapter."""
    tts = FakeTTSClient()
    use_case = _build_use_case(tmp_path, tts=tts)

    platform_version_ids = _make_chapter_with_all_platforms(session)
    assert len(platform_version_ids) == 4

    for platform_version_id in platform_version_ids:
        result = use_case.generate_video(session, platform_version_id, "es")
        assert result.succeeded

    assert len(tts.calls) == 1, "narration should be synthesized once, not per platform"


def test_raises_for_unknown_platform_version(session, tmp_path):
    use_case = _build_use_case(tmp_path)

    with pytest.raises(ValueError, match="does not exist"):
        use_case.generate_video(session, "no-such-id", "es")
