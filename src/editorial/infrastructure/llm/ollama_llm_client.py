"""
Local LLM client for the editorial service, implementing the editorial
ILLMClient port against a locally-running Ollama server.

Used for case curation only (openspec/changes/local-curation-model):
curation scores a document against a rubric and emits a small JSON verdict,
which a local 8B model handles. Story-writing and platform-adaptation stay on
the cloud model — they generate prose under validation (chapter length, no
fabricated quotes, mandatory visual directives) that a small local model
fails often enough to cost more in regeneration than it saves.

Distinct from src/infrastructure/llm/local_llm_client.py, which is the
ingestion pipeline's MLX depuration client and speaks a different protocol.
"""
import logging
from typing import Optional

import httpx

from src.editorial.core.exceptions import StoryGenerationError

logger = logging.getLogger("editorial.ollama")

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "cogito:latest"
DEFAULT_TIMEOUT_SECONDS = 180.0


class OllamaLLMClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        # Generous: a local 8B model takes tens of seconds on a full document,
        # far longer than a cloud call. Still bounded, so a wedged server
        # cannot hang a research pass indefinitely.
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def complete(self, prompt: str) -> str:
        """
        Send prompt to the local model and return its raw text response.

        Requests JSON-constrained output: every editorial caller parses the
        response as JSON, and an unconstrained local model tends to wrap it
        in conversational prose that fails the parse.
        """
        logger.info(
            "Requesting completion from local model %s (%d chars of prompt)",
            self._model,
            len(prompt),
        )
        try:
            response = self._client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
            )
        except httpx.HTTPError as error:
            # Names the URL, because the overwhelmingly common cause is that
            # the server simply is not running.
            raise StoryGenerationError(
                f"Could not reach the local model at {self._base_url} — is "
                f"Ollama running? ({error})"
            ) from error

        if response.status_code == 404:
            # Ollama answers 404 with {"error": "model 'x' not found"}. That
            # is a setup problem with an obvious fix, worth naming outright.
            raise StoryGenerationError(
                f"Ollama does not have the model '{self._model}'. "
                f"Install it with: ollama pull {self._model}"
            )

        if response.status_code >= 400:
            raise StoryGenerationError(
                f"Ollama returned {response.status_code}: {response.text[:300]}"
            )

        try:
            payload = response.json()
        except ValueError as error:
            raise StoryGenerationError(
                f"Ollama returned a non-JSON envelope: {response.text[:300]}"
            ) from error

        text = payload.get("response")
        if not isinstance(text, str) or not text.strip():
            raise StoryGenerationError(
                f"Ollama returned an empty completion for model '{self._model}'."
            )
        return text

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OllamaLLMClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
