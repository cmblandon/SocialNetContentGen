"""
POST /research/run — the manual trigger for a research+curation pass.
Design.md defers autonomous daily/cron scheduling as a Non-Goal; this
endpoint is the operator-triggered stand-in for it (Phase 4).

Each dependency is its own FastAPI provider function so tests can override
individual pieces (research_agent, case_curation, the use cases) with
fakes, the same pattern already used for get_session.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.editorial.application.case_curation_use_case import CaseCurationUseCase
from src.editorial.application.orchestrator import run_research_cycle
from src.editorial.application.platform_adaptation_use_case import (
    PlatformAdaptationUseCase,
)
from src.editorial.application.research_agent_use_case import ResearchAgentUseCase
from src.editorial.application.story_writing_use_case import StoryWritingUseCase
from src.editorial.infrastructure.llm.anthropic_llm_client import AnthropicLLMClient
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore
from src.editorial.infrastructure.persistence.session import get_session
from src.editorial.infrastructure.scraping.firecrawl_scraper import (
    FirecrawlScraperAdapter,
)
from src.editorial.infrastructure.scraping.jina_scraper import JinaScraperAdapter
from src.editorial.presentation.dependencies import get_llm_client, get_memory_store

router = APIRouter(prefix="/research", tags=["research"])


class ResearchRunRequest(BaseModel):
    source_urls: list[str] = Field(min_length=1)


class ResearchRunResponse(BaseModel):
    documents_reviewed: int
    stories_created: int
    chapters_generated: int
    pending_approval_platform_version_ids: list[str]
    discarded_document_ids: list[str]


class SourceUrlsResponse(BaseModel):
    source_urls: list[str]


class SourceUrlRequest(BaseModel):
    url: str


def get_research_agent(
    memory_store: ProjectMemoryStore = Depends(get_memory_store),
) -> ResearchAgentUseCase:
    primary_scraper = JinaScraperAdapter(api_key=settings.jina_api_key)
    fallback_scraper = (
        FirecrawlScraperAdapter(api_key=settings.firecrawl_api_key)
        if settings.firecrawl_api_key
        else None
    )
    return ResearchAgentUseCase(primary_scraper, fallback_scraper, memory_store)


def get_case_curation(
    memory_store: ProjectMemoryStore = Depends(get_memory_store),
    llm_client: AnthropicLLMClient = Depends(get_llm_client),
) -> CaseCurationUseCase:
    return CaseCurationUseCase(llm_client=llm_client, memory_store=memory_store)


def get_story_writing_use_case(
    llm_client: AnthropicLLMClient = Depends(get_llm_client),
) -> StoryWritingUseCase:
    return StoryWritingUseCase(llm_client=llm_client)


def get_platform_adaptation_use_case(
    llm_client: AnthropicLLMClient = Depends(get_llm_client),
) -> PlatformAdaptationUseCase:
    return PlatformAdaptationUseCase(llm_client=llm_client)


@router.post("/run", response_model=ResearchRunResponse)
def run_research(
    request: ResearchRunRequest,
    session: Session = Depends(get_session),
    memory_store: ProjectMemoryStore = Depends(get_memory_store),
    research_agent: ResearchAgentUseCase = Depends(get_research_agent),
    case_curation: CaseCurationUseCase = Depends(get_case_curation),
    story_writing_use_case: StoryWritingUseCase = Depends(get_story_writing_use_case),
    platform_adaptation_use_case: PlatformAdaptationUseCase = Depends(
        get_platform_adaptation_use_case
    ),
) -> ResearchRunResponse:
    summary = run_research_cycle(
        session=session,
        source_urls=request.source_urls,
        research_agent=research_agent,
        case_curation=case_curation,
        story_writing_use_case=story_writing_use_case,
        platform_adaptation_use_case=platform_adaptation_use_case,
        memory_store=memory_store,
    )
    return ResearchRunResponse(
        documents_reviewed=summary.documents_reviewed,
        stories_created=summary.stories_created,
        chapters_generated=summary.chapters_generated,
        pending_approval_platform_version_ids=summary.pending_approval_platform_version_ids,
        discarded_document_ids=summary.discarded_document_ids,
    )


@router.get("/sources", response_model=SourceUrlsResponse)
def list_sources(
    memory_store: ProjectMemoryStore = Depends(get_memory_store),
) -> SourceUrlsResponse:
    return SourceUrlsResponse(source_urls=memory_store.read_source_urls())


@router.post("/sources", response_model=SourceUrlsResponse)
def add_source(
    request: SourceUrlRequest,
    memory_store: ProjectMemoryStore = Depends(get_memory_store),
) -> SourceUrlsResponse:
    memory_store.add_source_url(request.url)
    return SourceUrlsResponse(source_urls=memory_store.read_source_urls())


@router.post("/sources/delete", response_model=SourceUrlsResponse)
def remove_source(
    request: SourceUrlRequest,
    memory_store: ProjectMemoryStore = Depends(get_memory_store),
) -> SourceUrlsResponse:
    memory_store.remove_source_url(request.url)
    return SourceUrlsResponse(source_urls=memory_store.read_source_urls())
