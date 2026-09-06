"""
Shared FastAPI dependency providers for the editorial service, factored
out so multiple routers (research, approval) don't each redefine
get_memory_store/get_llm_client.
"""
from fastapi import Depends

from src.config.settings import DATA_DIR, settings
from src.editorial.application.publishing_use_case import PublishingUseCase
from src.editorial.application.subtitle_generation_use_case import (
    SubtitleGenerationUseCase,
)
from src.editorial.application.subtitle_review_use_case import SubtitleReviewUseCase
from src.editorial.infrastructure.external.elevenlabs_client import (
    ElevenLabsTextToSpeechClient,
)
from src.editorial.infrastructure.llm.anthropic_llm_client import AnthropicLLMClient
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore
from src.editorial.infrastructure.persistence.subtitle_store import SubtitleStore
from src.editorial.infrastructure.publishing.postiz_publisher import (
    PostizPublisherAdapter,
)

EDITORIAL_MEMORY_DIR = DATA_DIR / "knowledge_base" / "editorial_memory"
SUBTITLE_ROOT = DATA_DIR / "subtitles"
AUDIO_ROOT = DATA_DIR / "audio"
SUBTITLE_CACHE_DIR = DATA_DIR / "knowledge_base" / "subtitle_cache"


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


def get_subtitle_store() -> SubtitleStore:
    return SubtitleStore(subtitle_root=SUBTITLE_ROOT, audio_root=AUDIO_ROOT)


def get_text_to_speech_client() -> ElevenLabsTextToSpeechClient:
    return ElevenLabsTextToSpeechClient(
        api_key=settings.elevenlabs_api_key,
        spanish_voice_id=settings.elevenlabs_spanish_voice_id,
        english_voice_id=settings.elevenlabs_english_voice_id,
    )


def get_subtitle_generation_use_case(
    llm_client: AnthropicLLMClient = Depends(get_llm_client),
) -> SubtitleGenerationUseCase:
    return SubtitleGenerationUseCase(llm_client=llm_client, cache_dir=SUBTITLE_CACHE_DIR)


def get_subtitle_review_use_case(
    tts_client: ElevenLabsTextToSpeechClient = Depends(get_text_to_speech_client),
    subtitle_use_case: SubtitleGenerationUseCase = Depends(
        get_subtitle_generation_use_case
    ),
    subtitle_store: SubtitleStore = Depends(get_subtitle_store),
) -> SubtitleReviewUseCase:
    return SubtitleReviewUseCase(
        tts_client=tts_client,
        subtitle_use_case=subtitle_use_case,
        subtitle_store=subtitle_store,
    )
