"""
Cloud LLM client for the editorial service, implementing the editorial
ILLMClient port (src/editorial/core/ports.py) via the Anthropic API.
Distinct from src/infrastructure/llm/local_llm_client.py, which depurates
raw ingestion text with a local MLX model — quality/fact-fidelity matters
more here than cost (design.md Decision 7).
"""
from typing import Optional

import anthropic

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 4096


class AnthropicLLMClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        client: Optional[anthropic.Anthropic] = None,
    ):
        self._model = model
        self._max_tokens = max_tokens
        self._client = client or anthropic.Anthropic(api_key=api_key)

    def complete(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
