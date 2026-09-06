"""
Contract test for story generation against the Anthropic Messages API (task 2.4).

Replaces the originally-planned "test story generation end-to-end". Calling a
live LLM from the automated suite has the same problems that reshaped tasks
6.6, 9.6 and 15.6: it is non-deterministic, costs money on every run, needs a
production key in CI, and fails when the provider does.

What is actually worth verifying is twofold, and neither needs a live call:

1. AnthropicLLMClient correctly unwraps a real Messages API response envelope.
   The previous tests handed it a bare string, so `response.content[0].text`
   — the one line that touches the API's shape — was never exercised. These
   drive the real SDK deserialization through a mock transport.

2. StoryWritingUseCase enforces the 150-220 word constraint on output shaped
   the way an LLM actually returns it (JSON inside a text block), not on a
   dict a test author hand-built.

FIXTURE PROVENANCE — and its limit. The envelopes below follow the documented
Messages API response shape; they are not captured from a live call. Nothing
in this repo calls the real API, by choice. If Anthropic changes the envelope,
these tests still pass and production still breaks — that gap closes the first
time the pipeline runs with a real key, and these fixtures are where to record
what came back.

Note the SDK is anthropic 1.x, which uses `httpx2` rather than `httpx`;
`httpx.MockTransport` is explicitly rejected by the client constructor.
"""
import json

import anthropic
import httpx2
import pytest

from src.editorial.application.story_writing_use_case import (
    MAX_CHAPTER_WORDS,
    MIN_CHAPTER_WORDS,
    StoryWritingUseCase,
)
from src.editorial.core.exceptions import StoryGenerationError
from src.editorial.infrastructure.llm.anthropic_llm_client import AnthropicLLMClient

DOCUMENT_TEXT = (
    "A pilot reported an unidentified radar contact over the Pacific. "
    'The incident log states: "radar contact was lost at 0200 hours" '
    "before the aircraft returned to base without further incident."
)


def _words(count: int) -> str:
    return " ".join(["palabra"] * count)


def _story_payload(word_count: int) -> dict:
    return {
        "summary": "Un contacto de radar queda sin explicación.",
        "chapters": [
            {
                "title": "Parte 1",
                "script": _words(word_count),
                "visual_notes": "material de archivo de radar militar; pausa tras la cita",
                "source_citation": "AARO, report, 2024-03-01",
            }
        ],
    }


def _messages_envelope(text: str, stop_reason: str = "end_turn") -> dict:
    """The documented Messages API response shape."""
    return {
        "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 2095, "output_tokens": 503},
    }


def _client_returning(payload: dict, capture: list | None = None) -> AnthropicLLMClient:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if capture is not None:
            capture.append(json.loads(request.content))
        return httpx2.Response(200, json=payload)

    sdk_client = anthropic.Anthropic(
        api_key="test-key",
        http_client=anthropic.DefaultHttpxClient(
            transport=httpx2.MockTransport(handler)
        ),
    )
    return AnthropicLLMClient(api_key="test-key", client=sdk_client)


# --- The adapter against the API envelope -----------------------------------


def test_client_unwraps_the_text_block_from_a_real_envelope():
    """`content` is a list of typed blocks — the text is not the top level."""
    client = _client_returning(_messages_envelope("story text here"))

    assert client.complete("write a story") == "story text here"


def test_client_sends_the_prompt_as_a_user_message():
    sent: list = []
    client = _client_returning(_messages_envelope("ok"), capture=sent)

    client.complete("Convert this document into a story.")

    body = sent[0]
    assert body["messages"] == [
        {"role": "user", "content": "Convert this document into a story."}
    ]
    assert body["model"]
    assert body["max_tokens"] > 0


# --- Story generation on realistically-shaped output ------------------------


def test_generates_a_story_from_a_recorded_response():
    """The JSON arrives as text inside a content block, not as a dict."""
    payload = _messages_envelope(json.dumps(_story_payload(180)))
    use_case = StoryWritingUseCase(llm_client=_client_returning(payload))

    draft = use_case.write_story(
        document_text=DOCUMENT_TEXT,
        agency="AARO",
        doc_type="report",
        published_date="2024-03-01",
        narrative_angle="testigo militar + corroboración de radar",
    )

    assert draft.summary == "Un contacto de radar queda sin explicación."
    assert len(draft.chapters) == 1
    assert draft.chapters[0].visual_notes


@pytest.mark.parametrize("word_count", [MIN_CHAPTER_WORDS, 185, MAX_CHAPTER_WORDS])
def test_accepts_chapters_inside_the_reel_length_range(word_count):
    payload = _messages_envelope(json.dumps(_story_payload(word_count)))
    use_case = StoryWritingUseCase(llm_client=_client_returning(payload))

    draft = use_case.write_story(
        document_text=DOCUMENT_TEXT,
        agency="AARO",
        doc_type="report",
        published_date="2024-03-01",
        narrative_angle="angle",
    )

    assert len(draft.chapters[0].script.split()) == word_count


@pytest.mark.parametrize(
    "word_count", [MIN_CHAPTER_WORDS - 1, 40, MAX_CHAPTER_WORDS + 1, 400]
)
def test_rejects_chapters_outside_the_reel_length_range(word_count):
    """
    The constraint is what keeps a chapter inside a 15-60s reel. An LLM will
    drift outside it, so this must fail rather than pass a too-long script
    downstream to paid narration.
    """
    payload = _messages_envelope(json.dumps(_story_payload(word_count)))
    use_case = StoryWritingUseCase(llm_client=_client_returning(payload))

    with pytest.raises(StoryGenerationError, match="must be between"):
        use_case.write_story(
            document_text=DOCUMENT_TEXT,
            agency="AARO",
            doc_type="report",
            published_date="2024-03-01",
            narrative_angle="angle",
        )


def test_rejects_a_chapter_missing_visual_directives():
    payload = _story_payload(180)
    payload["chapters"][0]["visual_notes"] = ""
    use_case = StoryWritingUseCase(
        llm_client=_client_returning(_messages_envelope(json.dumps(payload)))
    )

    with pytest.raises(StoryGenerationError, match="visual directives"):
        use_case.write_story(
            document_text=DOCUMENT_TEXT,
            agency="AARO",
            doc_type="report",
            published_date="2024-03-01",
            narrative_angle="angle",
        )


def test_rejects_a_fabricated_quote_in_realistic_output():
    payload = _story_payload(178)
    payload["chapters"][0]["script"] += ' El piloto dijo: "hicimos contacto directo"'
    use_case = StoryWritingUseCase(
        llm_client=_client_returning(_messages_envelope(json.dumps(payload)))
    )

    with pytest.raises(StoryGenerationError, match="quote not found"):
        use_case.write_story(
            document_text=DOCUMENT_TEXT,
            agency="AARO",
            doc_type="report",
            published_date="2024-03-01",
            narrative_angle="angle",
        )


def test_prose_around_the_json_is_rejected_rather_than_half_parsed():
    """
    A model that ignores "respond with JSON" and wraps it in prose must fail
    loudly. Silently salvaging it would make the failure mode invisible until
    a malformed chapter reached narration.
    """
    wrapped = "Claro, aquí está el resultado:\n\n" + json.dumps(_story_payload(180))
    use_case = StoryWritingUseCase(
        llm_client=_client_returning(_messages_envelope(wrapped))
    )

    with pytest.raises(StoryGenerationError, match="not valid JSON"):
        use_case.write_story(
            document_text=DOCUMENT_TEXT,
            agency="AARO",
            doc_type="report",
            published_date="2024-03-01",
            narrative_angle="angle",
        )


def test_a_truncated_response_surfaces_as_a_generation_error():
    """max_tokens cuts the JSON mid-object; the parse must fail, not guess."""
    truncated = json.dumps(_story_payload(180))[:-40]
    use_case = StoryWritingUseCase(
        llm_client=_client_returning(_messages_envelope(truncated, stop_reason="max_tokens"))
    )

    with pytest.raises(StoryGenerationError, match="not valid JSON"):
        use_case.write_story(
            document_text=DOCUMENT_TEXT,
            agency="AARO",
            doc_type="report",
            published_date="2024-03-01",
            narrative_angle="angle",
        )


def test_the_prompt_carries_the_reel_constraints_to_the_model():
    """The constraint is enforced after the fact; it must also be asked for."""
    sent: list = []
    use_case = StoryWritingUseCase(
        llm_client=_client_returning(
            _messages_envelope(json.dumps(_story_payload(180))), capture=sent
        )
    )

    use_case.write_story(
        document_text=DOCUMENT_TEXT,
        agency="AARO",
        doc_type="report",
        published_date="2024-03-01",
        narrative_angle="angle",
    )

    prompt = sent[0]["messages"][0]["content"]
    assert "150–220 words" in prompt
    assert "visual directives" in prompt
    assert DOCUMENT_TEXT in prompt
