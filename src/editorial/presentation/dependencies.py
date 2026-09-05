"""
Shared FastAPI dependency providers for the editorial service, factored
out so multiple routers (research, approval) don't each redefine
get_memory_store/get_llm_client.
"""
from fastapi import Depends

from src.config.settings import DATA_DIR, settings
from src.editorial.application.publishing_use_case import PublishingUseCase
from src.editorial.infrastructure.llm.anthropic_llm_client import AnthropicLLMClient
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore
from src.editorial.infrastructure.publishing.postiz_publisher import (
    PostizPublisherAdapter,
)

EDITORIAL_MEMORY_DIR = DATA_DIR / "knowledge_base" / "editorial_memory"


def get_memory_store() -> ProjectMemoryStore:
    return ProjectMemoryStore(memory_dir=EDITORIAL_MEMORY_DIR)


def get_llm_client() -> AnthropicLLMClient:
    return AnthropicLLMClient(api_key=settings.anthropic_api_key)


def get_publisher() -> PostizPublisherAdapter:
    return PostizPublisherAdapter(
        api_key=settings.postiz_api_key, base_url=settings.postiz_base_url
    )


def get_publishing_use_case(
    publisher: PostizPublisherAdapter = Depends(get_publisher),
    memory_store: ProjectMemoryStore = Depends(get_memory_store),
) -> PublishingUseCase:
    return PublishingUseCase(publisher=publisher, memory_store=memory_store)
