"""
Subagent wiring for the editorial orchestrator (deepagents/LangGraph), per
specs/editorial-orchestration/spec.md: the orchestrator delegates each
stage to its subagent rather than doing the work itself. writer_agent and
platform_adapter_agent here are thin tool wrappers around the Phase 2 use
cases (StoryWritingUseCase, PlatformAdaptationUseCase) — the tool's job is
delegation, all actual logic/validation stays in the use case.
"""
from dataclasses import asdict
from typing import Optional

from deepagents import SubAgent, create_deep_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool

from src.editorial.application.platform_adaptation_use_case import (
    PlatformAdaptationUseCase,
)
from src.editorial.application.story_writing_use_case import StoryWritingUseCase


def build_writer_agent_tool(story_writing_use_case: StoryWritingUseCase):
    @tool
    def writer_agent(
        document_text: str,
        agency: str,
        doc_type: str,
        published_date: str,
        narrative_angle: str,
    ) -> dict:
        """Delegate to the writer agent: converts a curated official
        document into a hook-driven, fact-bound story, split into chapters
        when the document is extensive. Never fabricates facts or quotes."""
        story = story_writing_use_case.write_story(
            document_text=document_text,
            agency=agency,
            doc_type=doc_type,
            published_date=published_date,
            narrative_angle=narrative_angle,
        )
        return {
            "summary": story.summary,
            "chapters": [asdict(chapter) for chapter in story.chapters],
        }

    return writer_agent


def build_platform_adapter_agent_tool(
    platform_adaptation_use_case: PlatformAdaptationUseCase,
):
    @tool
    def platform_adapter_agent(script: str, source_citation: str) -> dict:
        """Delegate to the platform adapter agent: reformats a chapter's
        script into TikTok/Reels, Instagram, X, and Facebook versions
        without changing any fact or the core spoken script."""
        adaptations = platform_adaptation_use_case.adapt_chapter(
            script=script, source_citation=source_citation
        )
        return {
            "tiktok": asdict(adaptations.tiktok),
            "instagram": asdict(adaptations.instagram),
            "x": asdict(adaptations.x),
            "facebook": asdict(adaptations.facebook),
        }

    return platform_adapter_agent


def build_subagents(
    story_writing_use_case: StoryWritingUseCase,
    platform_adaptation_use_case: PlatformAdaptationUseCase,
) -> list[SubAgent]:
    return [
        SubAgent(
            name="writer_agent",
            description=(
                "Converts a curated official document into a hook-driven, "
                "fact-bound, chapterized story. Use this to write the "
                "narrative for a document the curator has advanced."
            ),
            tools=[build_writer_agent_tool(story_writing_use_case)],
        ),
        SubAgent(
            name="platform_adapter_agent",
            description=(
                "Reformats a chapter's script for TikTok/Reels, Instagram, "
                "X, and Facebook without changing facts. Use this once a "
                "chapter's script exists."
            ),
            tools=[build_platform_adapter_agent_tool(platform_adaptation_use_case)],
        ),
    ]


def build_editorial_deep_agent(
    model: str | BaseChatModel,
    story_writing_use_case: StoryWritingUseCase,
    platform_adaptation_use_case: PlatformAdaptationUseCase,
    checkpointer: Optional[object] = None,
):
    """
    Constructs the editorial root orchestrator. Only research-agent/
    case-curation/publishing are absent (Phases 4-5 add their own
    subagents/tools here); the approval gate itself is enforced at the
    application layer (see orchestrator.py), not via this graph's own
    interrupt mechanics, since there is no publisher node yet to pause
    before (design.md Decision 5; Phase 3 migration note).
    """
    return create_deep_agent(
        model=model,
        subagents=build_subagents(story_writing_use_case, platform_adaptation_use_case),
        checkpointer=checkpointer,
    )
