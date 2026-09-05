"""
Tests for the manual-curation CLI orchestration (Phase 2 fixture path): feeds
an existing manually-ingested FichaEstructurada through StoryWritingUseCase
and PlatformAdaptationUseCase, standing in for research-agent/case-curation
until Phase 4 builds them for real.
"""
from src.core.entities import FichaEstructurada
from src.editorial.application.manual_curation_cli import run_manual_curation
from src.editorial.core.entities import (
    ChapterDraft,
    FacebookAdaptation,
    InstagramAdaptation,
    PlatformAdaptations,
    StoryDraft,
    TikTokAdaptation,
    XAdaptation,
)


def _ficha() -> FichaEstructurada:
    return FichaEstructurada(
        resumen_ejecutivo="A pilot reported an unidentified radar contact.",
        fragmentos_clave=["Radar contact lost at 0200 hours.", "No further incident followed."],
        fecha_documento="2024-03-01",
        organismo_emisor="AARO",
        confiabilidad_extraccion="alta",
    )


def _adaptations() -> PlatformAdaptations:
    return PlatformAdaptations(
        tiktok=TikTokAdaptation(script="s", on_screen_hook_lines=["a", "b"], hashtags=["#a", "#b", "#c"], description="d"),
        instagram=InstagramAdaptation(carousel_slides=["1", "2", "3", "4", "5", "6"]),
        x=XAdaptation(tweets=["t1", "t2", "t3", "t4"]),
        facebook=FacebookAdaptation(post="p?"),
    )


class FakeStoryWritingUseCase:
    def __init__(self, story: StoryDraft):
        self._story = story
        self.calls: list[dict] = []

    def write_story(self, **kwargs):
        self.calls.append(kwargs)
        return self._story


class FakePlatformAdaptationUseCase:
    def __init__(self, adaptations: PlatformAdaptations):
        self._adaptations = adaptations
        self.calls: list[dict] = []

    def adapt_chapter(self, **kwargs):
        self.calls.append(kwargs)
        return self._adaptations


def test_passes_ficha_fields_into_story_writing_use_case():
    ficha = _ficha()
    story = StoryDraft(summary="s", chapters=[])
    writer = FakeStoryWritingUseCase(story)
    adapter = FakePlatformAdaptationUseCase(_adaptations())

    run_manual_curation(
        ficha=ficha,
        doc_type="report",
        narrative_angle="military witness + radar corroboration",
        story_writing_use_case=writer,
        platform_adaptation_use_case=adapter,
    )

    assert len(writer.calls) == 1
    call = writer.calls[0]
    assert call["agency"] == "AARO"
    assert call["doc_type"] == "report"
    assert call["published_date"] == "2024-03-01"
    assert call["narrative_angle"] == "military witness + radar corroboration"
    assert "Radar contact lost at 0200 hours." in call["document_text"]
    assert "A pilot reported an unidentified radar contact." in call["document_text"]


def test_adapts_every_chapter_produced_by_the_story():
    ficha = _ficha()
    story = StoryDraft(
        summary="s",
        chapters=[
            ChapterDraft(title="P1", script="script one", visual_notes="v", source_citation="c", chapter_index=1),
            ChapterDraft(title="P2", script="script two", visual_notes="v", source_citation="c", chapter_index=2),
        ],
    )
    writer = FakeStoryWritingUseCase(story)
    adapter = FakePlatformAdaptationUseCase(_adaptations())

    run_manual_curation(
        ficha=ficha,
        doc_type="report",
        narrative_angle="angle",
        story_writing_use_case=writer,
        platform_adaptation_use_case=adapter,
    )

    assert len(adapter.calls) == 2
    assert adapter.calls[0] == {"script": "script one", "source_citation": "c"}
    assert adapter.calls[1] == {"script": "script two", "source_citation": "c"}


def test_returns_the_story_and_its_platform_adaptations():
    ficha = _ficha()
    story = StoryDraft(
        summary="s",
        chapters=[ChapterDraft(title="P1", script="script", visual_notes="v", source_citation="c", chapter_index=1)],
    )
    writer = FakeStoryWritingUseCase(story)
    adaptations = _adaptations()
    adapter = FakePlatformAdaptationUseCase(adaptations)

    result = run_manual_curation(
        ficha=ficha,
        doc_type="report",
        narrative_angle="angle",
        story_writing_use_case=writer,
        platform_adaptation_use_case=adapter,
    )

    assert result.story is story
    assert result.platform_adaptations_by_chapter == [adaptations]
