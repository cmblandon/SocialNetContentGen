"""
Contract tests for the Ollama adapter (local-curation-model, tasks 2.x/4.x).

Drives the adapter's real request path — httpx, URL construction, status
handling — through a mock transport, against payloads captured from the
locally-running Ollama server rather than written from documentation.

Unlike the ElevenLabs and Unsplash fixtures, these ARE observed: Ollama runs
locally and costs nothing to call, so the success envelope and the
missing-model error below were taken from real responses on 2026-09-06
(ollama serving cogito:latest).
"""
import json

import httpx
import pytest

from src.editorial.application.case_curation_use_case import CaseCurationUseCase
from src.editorial.core.exceptions import StoryGenerationError
from src.editorial.core.ports import ILLMClient, ScrapedDocument
from src.editorial.infrastructure.llm.ollama_llm_client import OllamaLLMClient

# --- Captured from a live local server ---------------------------------------

# POST /api/generate, stream=false — the completion is a JSON *string* under
# "response", not a nested object, even when format=json is requested.
OLLAMA_SUCCESS = {
    "model": "cogito:latest",
    "created_at": "2026-09-06T20:11:04.512345Z",
    "response": '{"score": 18, "advance": true, "reason": "Primary source"}',
    "done": True,
    "done_reason": "stop",
    "total_duration": 10529000000,
    "eval_count": 42,
}

# Ollama answers 404 with this body when the model is not pulled.
OLLAMA_MODEL_MISSING = {"error": "model 'does-not-exist:1b' not found"}


def transport_returning(response: httpx.Response) -> httpx.MockTransport:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return response

    transport = httpx.MockTransport(handler)
    transport.calls = calls  # type: ignore[attr-defined]
    return transport


def _client(transport: httpx.MockTransport, model: str = "cogito:latest") -> OllamaLLMClient:
    return OllamaLLMClient(
        base_url="http://localhost:11434", model=model, transport=transport
    )


# --- The adapter --------------------------------------------------------------


def test_conforms_to_the_editorial_llm_port():
    assert isinstance(_client(transport_returning(httpx.Response(200))), ILLMClient)


def test_returns_the_completion_string_from_the_envelope():
    """The text lives under "response"; the rest of the envelope is metadata."""
    client = _client(transport_returning(httpx.Response(200, json=OLLAMA_SUCCESS)))

    assert client.complete("score this") == OLLAMA_SUCCESS["response"]


def test_sends_the_documented_request():
    transport = transport_returning(httpx.Response(200, json=OLLAMA_SUCCESS))

    _client(transport).complete("score this document")

    request = transport.calls[0]  # type: ignore[attr-defined]
    body = json.loads(request.content)
    assert request.url.path == "/api/generate"
    assert body["model"] == "cogito:latest"
    assert body["prompt"] == "score this document"
    # Non-streaming: the adapter reads a single envelope, not a token stream.
    assert body["stream"] is False
    # Every editorial caller parses the response as JSON, so the model must be
    # constrained rather than left free to reply conversationally.
    assert body["format"] == "json"


def test_a_missing_model_names_the_fix():
    """404 here means "not pulled", which has an obvious remedy worth stating."""
    transport = transport_returning(httpx.Response(404, json=OLLAMA_MODEL_MISSING))

    with pytest.raises(StoryGenerationError, match="ollama pull missing-model"):
        _client(transport, model="missing-model").complete("score this")


def test_an_unreachable_server_names_the_url():
    """By far the most common failure: the server simply is not running."""

    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    client = _client(httpx.MockTransport(refuse))

    with pytest.raises(StoryGenerationError, match="localhost:11434.*Ollama running"):
        client.complete("score this")


def test_a_server_error_is_reported_with_its_body():
    transport = transport_returning(httpx.Response(500, text="internal failure"))

    with pytest.raises(StoryGenerationError, match="Ollama returned 500"):
        _client(transport).complete("score this")


def test_an_empty_completion_is_an_error_not_an_empty_string():
    """An empty string would fail JSON parsing far from its cause."""
    transport = transport_returning(
        httpx.Response(200, json={**OLLAMA_SUCCESS, "response": "   "})
    )

    with pytest.raises(StoryGenerationError, match="empty completion"):
        _client(transport).complete("score this")


def test_a_non_json_envelope_is_reported_clearly():
    transport = transport_returning(httpx.Response(200, text="<html>proxy error</html>"))

    with pytest.raises(StoryGenerationError, match="non-JSON envelope"):
        _client(transport).complete("score this")


# --- Curation on top of the adapter -------------------------------------------


class StubMemoryStore:
    def read_casos_cubiertos(self) -> str:
        return ""

    def append_caso_cubierto(self, entry: str) -> None:
        pass


def test_curation_parses_a_realistic_local_model_response():
    """
    The point of the whole change: curation must work end to end on output
    shaped the way the local model actually returns it.
    """
    payload = json.dumps(
        {
            # The real rubric keys, from case_curation_use_case._CRITERIA.
            "scores": {
                key: 5
                for key in (
                    "novedad",
                    "potencial_narrativo",
                    "respaldo_documental",
                    "elemento_visual",
                    "encaje_audiencia",
                )
            },
            "narrative_angle": "testigo militar con corroboración de radar",
        }
    )
    transport = transport_returning(
        httpx.Response(200, json={**OLLAMA_SUCCESS, "response": payload})
    )
    use_case = CaseCurationUseCase(
        llm_client=_client(transport), memory_store=StubMemoryStore()
    )

    result = use_case.curate(
        ScrapedDocument(
            title="AARO 2024 Annual Report",
            agency="AARO",
            doc_type="report",
            extracted_text="A pilot reported an unidentified radar contact.",
        )
    )

    assert result is not None
    assert result.advanced is True
    assert result.narrative_angle == "testigo militar con corroboración de radar"


def test_curation_surfaces_unparseable_local_output_as_a_curation_error():
    """
    A local model that ignores format=json must fail this document, leaving
    it retryable, rather than silently scoring it zero.
    """
    transport = transport_returning(
        httpx.Response(200, json={**OLLAMA_SUCCESS, "response": "Claro, aquí tienes:"})
    )
    use_case = CaseCurationUseCase(
        llm_client=_client(transport), memory_store=StubMemoryStore()
    )

    with pytest.raises(Exception) as caught:
        use_case.curate(
            ScrapedDocument(
                title="Some doc",
                agency="AARO",
                doc_type="report",
                extracted_text="text",
            )
        )
    assert "JSON" in str(caught.value)
