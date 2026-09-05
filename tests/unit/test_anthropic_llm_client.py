"""
Tests for AnthropicLLMClient — the editorial ILLMClient implementation.
The underlying `anthropic.Anthropic` client is injected so no real API call
is ever made in tests.
"""
from unittest.mock import MagicMock

from src.editorial.core.ports import ILLMClient
from src.editorial.infrastructure.llm.anthropic_llm_client import AnthropicLLMClient


def _fake_anthropic_client(response_text: str) -> MagicMock:
    client = MagicMock()
    content_block = MagicMock()
    content_block.text = response_text
    client.messages.create.return_value = MagicMock(content=[content_block])
    return client


def test_conforms_to_illm_client_protocol():
    client = AnthropicLLMClient(api_key="test-key", client=_fake_anthropic_client("ok"))
    assert isinstance(client, ILLMClient)


def test_complete_returns_the_response_text():
    fake_client = _fake_anthropic_client("Hello from Claude")
    client = AnthropicLLMClient(api_key="test-key", client=fake_client)

    result = client.complete("say hello")

    assert result == "Hello from Claude"


def test_complete_sends_the_prompt_as_a_user_message():
    fake_client = _fake_anthropic_client("ok")
    client = AnthropicLLMClient(api_key="test-key", client=fake_client)

    client.complete("write a story about radar contacts")

    _, kwargs = fake_client.messages.create.call_args
    assert kwargs["messages"] == [
        {"role": "user", "content": "write a story about radar contacts"}
    ]
