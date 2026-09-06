"""
Shared FastAPI dependency providers for the editorial service, factored
out so multiple routers (research, approval) don't each redefine
get_memory_store/get_llm_client.
"""
from pathlib import Path

from fastapi import Depends

from src.config.settings import DATA_DIR, settings
from src.editorial.application.publishing_use_case import PublishingUseCase
from src.editorial.application.subtitle_generation_use_case import (
    SubtitleGenerationUseCase,
)
from src.editorial.application.subtitle_review_use_case import SubtitleReviewUseCase
from src.editorial.application.video_generation_use_case import VideoGenerationUseCase
from src.editorial.infrastructure.external.elevenlabs_client import (
    ElevenLabsTextToSpeechClient,
)
from src.editorial.infrastructure.external.unsplash_client import UnsplashImageClient
from src.editorial.infrastructure.llm.anthropic_llm_client import AnthropicLLMClient
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore
from src.editorial.infrastructure.persistence.subtitle_store import SubtitleStore
from src.editorial.infrastructure.publishing.postiz_publisher import (
    PostizPublisherAdapter,
)
from src.editorial.infrastructure.video.ffmpeg_compositor import FFmpegCompositor

EDITORIAL_MEMORY_DIR = DATA_DIR / "knowledge_base" / "editorial_memory"
SUBTITLE_ROOT = DATA_DIR / "subtitles"
AUDIO_ROOT = DATA_DIR / "audio"
SUBTITLE_CACHE_DIR = DATA_DIR / "knowledge_base" / "subtitle_cache"
UNSPLASH_CACHE_DIR = DATA_DIR / "unsplash_cache"
VIDEO_ROOT = DATA_DIR / "videos_generated"


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


def get_video_root() -> Path:
    """Directory the video-serving endpoint is confined to."""
    return VIDEO_ROOT


def get_image_client() -> UnsplashImageClient:
    return UnsplashImageClient(
        access_key=settings.unsplash_access_key, cache_dir=UNSPLASH_CACHE_DIR
    )


def get_video_compositor() -> FFmpegCompositor:
    return FFmpegCompositor()


def get_video_generation_use_case(
    tts_client: ElevenLabsTextToSpeechClient = Depends(get_text_to_speech_client),
    image_client: UnsplashImageClient = Depends(get_image_client),
    compositor: FFmpegCompositor = Depends(get_video_compositor),
    subtitle_use_case: SubtitleGenerationUseCase = Depends(
        get_subtitle_generation_use_case
    ),
    subtitle_store: SubtitleStore = Depends(get_subtitle_store),
) -> VideoGenerationUseCase:
    return VideoGenerationUseCase(
        tts_client=tts_client,
        image_client=image_client,
        compositor=compositor,
        subtitle_use_case=subtitle_use_case,
        subtitle_store=subtitle_store,
        video_root=VIDEO_ROOT,
    )


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
