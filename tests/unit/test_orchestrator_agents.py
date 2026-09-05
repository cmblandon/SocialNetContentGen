"""
Tests for the editorial orchestrator's subagent wiring — per
specs/editorial-orchestration/spec.md ("Orchestrator delegates each stage
instead of doing the work itself"). Each subagent's tool must genuinely
delegate to the injected Phase 2 use case rather than reimplementing its
logic, and the deep agent must actually accept this wiring from the real
`deepagents` library. A FakeListChatModel is used so this is verified
without any live LLM call — we are testing our wiring, not the model's
reasoning (that would require a very different kind of test).
"""
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from src.editorial.application.orchestrator_agents import (
    build_editorial_deep_agent,
    build_platform_adapter_agent_tool,
    build_subagents,
    build_writer_agent_tool,
)
from src.editorial.core.entities import (
    FacebookAdaptation,
    InstagramAdaptation,
    PlatformAdaptations,
    StoryDraft,
    XAdaptation,
    TikTokAdaptation,
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


def _adaptations() -> PlatformAdaptations:
    return PlatformAdaptations(
        tiktok=TikTokAdaptation(script="s", on_screen_hook_lines=["a", "b"], hashtags=["#a", "#b", "#c"], description="d"),
        instagram=InstagramAdaptation(carousel_slides=["1", "2", "3", "4", "5", "6"]),
        x=XAdaptation(tweets=["t1", "t2", "t3", "t4"]),
        facebook=FacebookAdaptation(post="p?"),
    )


def test_build_subagents_returns_writer_and_platform_adapter_agents():
    writer = FakeStoryWritingUseCase(StoryDraft(summary="s", chapters=[]))
    adapter = FakePlatformAdaptationUseCase(_adaptations())

    subagents = build_subagents(writer, adapter)

    names = {subagent["name"] for subagent in subagents}
    assert names == {"writer_agent", "platform_adapter_agent"}
    for subagent in subagents:
        assert subagent["description"]
        assert len(subagent["tools"]) == 1


def test_writer_agent_tool_delegates_to_story_writing_use_case_without_reimplementing_it():
    story = StoryDraft(summary="A radar contact goes unexplained.", chapters=[])
    writer = FakeStoryWritingUseCase(story)
    tool = build_writer_agent_tool(writer)

    result = tool.invoke(
        {
            "document_text": "doc text",
            "agency": "AARO",
            "doc_type": "report",
            "published_date": "2024-03-01",
            "narrative_angle": "angle",
        }
    )

    assert len(writer.calls) == 1
    assert writer.calls[0]["document_text"] == "doc text"
    assert writer.calls[0]["agency"] == "AARO"
    assert result["summary"] == "A radar contact goes unexplained."


def test_platform_adapter_agent_tool_delegates_to_platform_adaptation_use_case_without_reimplementing_it():
    adaptations = _adaptations()
    adapter = FakePlatformAdaptationUseCase(adaptations)
    tool = build_platform_adapter_agent_tool(adapter)

    result = tool.invoke({"script": "chapter script", "source_citation": "AARO, report, 2024-03-01"})

    assert len(adapter.calls) == 1
    assert adapter.calls[0]["script"] == "chapter script"
    assert result["tiktok"]["hashtags"] == ["#a", "#b", "#c"]


def test_build_editorial_deep_agent_accepts_the_subagent_wiring():
    writer = FakeStoryWritingUseCase(StoryDraft(summary="s", chapters=[]))
    adapter = FakePlatformAdaptationUseCase(_adaptations())
    fake_model = FakeListChatModel(responses=["ok"])

    graph = build_editorial_deep_agent(
        model=fake_model,
        story_writing_use_case=writer,
        platform_adaptation_use_case=adapter,
    )

    assert hasattr(graph, "invoke")
