"""
Manual-curation entrypoint (Phase 2): feeds an existing manually-ingested
FichaEstructurada through StoryWritingUseCase and PlatformAdaptationUseCase.

Stands in for research-agent/case-curation (Phase 4) — the "curation" here
is simply pointing this CLI at a doc_id already vetted by a human, via the
existing manual PDF-ingestion pipeline.
"""
import argparse
from dataclasses import dataclass

from src.core.entities import FichaEstructurada
from src.editorial.application.platform_adaptation_use_case import (
    PlatformAdaptationUseCase,
)
from src.editorial.application.story_writing_use_case import StoryWritingUseCase
from src.editorial.core.entities import PlatformAdaptations, StoryDraft
from src.editorial.infrastructure.persistence.ficha_reader import read_ficha_by_id


@dataclass
class ManualCurationResult:
    story: StoryDraft
    platform_adaptations_by_chapter: list[PlatformAdaptations]


def run_manual_curation(
    ficha: FichaEstructurada,
    doc_type: str,
    narrative_angle: str,
    story_writing_use_case: StoryWritingUseCase,
    platform_adaptation_use_case: PlatformAdaptationUseCase,
) -> ManualCurationResult:
    document_text = "\n".join([ficha.resumen_ejecutivo, *ficha.fragmentos_clave])

    story = story_writing_use_case.write_story(
        document_text=document_text,
        agency=ficha.organismo_emisor,
        doc_type=doc_type,
        published_date=ficha.fecha_documento,
        narrative_angle=narrative_angle,
    )

    platform_adaptations_by_chapter = [
        platform_adaptation_use_case.adapt_chapter(
            script=chapter.script, source_citation=chapter.source_citation
        )
        for chapter in story.chapters
    ]

    return ManualCurationResult(
        story=story, platform_adaptations_by_chapter=platform_adaptations_by_chapter
    )


def main() -> None:
    from src.config.settings import settings
    from src.editorial.infrastructure.llm.anthropic_llm_client import AnthropicLLMClient

    parser = argparse.ArgumentParser(
        description="Feed a manually-ingested FichaEstructurada through "
        "story-writing and platform-adaptation."
    )
    parser.add_argument("--doc-id", required=True, help="id of the ingested document")
    parser.add_argument("--doc-type", required=True, help='e.g. "report", "testimony"')
    parser.add_argument("--narrative-angle", required=True, help="the curator's note on why this case works")
    args = parser.parse_args()

    ficha = read_ficha_by_id(args.doc_id)
    if ficha is None:
        raise SystemExit(f"No ingested document found with id '{args.doc_id}'.")

    llm_client = AnthropicLLMClient(api_key=settings.anthropic_api_key)
    story_writing_use_case = StoryWritingUseCase(llm_client=llm_client)
    platform_adaptation_use_case = PlatformAdaptationUseCase(llm_client=llm_client)

    result = run_manual_curation(
        ficha=ficha,
        doc_type=args.doc_type,
        narrative_angle=args.narrative_angle,
        story_writing_use_case=story_writing_use_case,
        platform_adaptation_use_case=platform_adaptation_use_case,
    )

    print(f"Story summary: {result.story.summary}\n")
    for chapter, adaptations in zip(result.story.chapters, result.platform_adaptations_by_chapter):
        print(f"--- Chapter {chapter.chapter_index}: {chapter.title} ---")
        print(chapter.script)
        print(f"Source: {chapter.source_citation}\n")
        print(f"TikTok/Reels hashtags: {' '.join(adaptations.tiktok.hashtags)}")
        print(f"Instagram carousel slides: {len(adaptations.instagram.carousel_slides)}")
        print(f"X thread tweets: {len(adaptations.x.tweets)}")
        print(f"Facebook post: {adaptations.facebook.post[:120]}...\n")


if __name__ == "__main__":
    main()
