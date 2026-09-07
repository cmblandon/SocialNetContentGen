## Why

Curation is currently failing outright. Two documents in the pipeline are
`FAILED` with:

```
400 invalid_request_error — "Your credit balance is too low to access the
Anthropic API."
```

Both were scraped and checkpointed successfully; only the LLM call failed. The
pipeline stalls at its cheapest, highest-volume stage — curation runs on every
discovered document, most of which are discarded, so it spends the most tokens
on content that never ships.

Ollama is already installed and running locally with `cogito:latest` (8B,
131k context), which returns well-formed JSON for a curation-shaped prompt in
about ten seconds.

## What Changes

- **New**: `OllamaLLMClient`, a second implementation of the editorial
  `ILLMClient` port, talking to a locally-running Ollama server.
- **Modified**: curation resolves its LLM through a dedicated provider that can
  be pointed at Ollama or Anthropic by configuration.

## Capabilities

### New Capabilities

- `local-curation-model`: run case curation against a local model so
  discovery and scoring keep working without cloud credits, without changing
  the curation rubric or its output contract.

## Impact

**Scope widened after measurement.** This began as curation-only, on the
expectation that a small model could not satisfy story-writing's validation.
That proved half true: `cogito` produced a 42-word chapter and `gemma4` a
121-word one against a required 150–220. But feeding the failure back fixed
it — the same model then produced 149, then 150 words, and passed.

So all document processing (curation, story-writing, platform-adaptation) can
run locally, provided generation retries with the validation error included in
the retry prompt. The constraint is not relaxed to accommodate the model; the
model is asked again, told what was wrong.

Expect lower prose quality and roughly 2x latency versus the cloud model, in
exchange for zero API cost and no dependency on credit balance.

**New files:**
- `src/editorial/infrastructure/llm/ollama_llm_client.py`
- `tests/contract/test_ollama_contract.py`

**Modified files:**
- `src/config/settings.py` — Ollama base URL, model, and the curation provider switch.
- `src/editorial/presentation/dependencies.py` — a curation-specific LLM provider.
- `src/editorial/presentation/routers/research.py` — curation uses that provider.
- `tests/unit/test_editorial_ports.py` — conformance for the new adapter.

**Breaking Changes:** None. The default provider stays Anthropic, so
behaviour is unchanged until the setting is flipped.
