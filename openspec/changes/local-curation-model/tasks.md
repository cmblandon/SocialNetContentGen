## 1. Configuration

- [x] 1.1 Add `ollama_base_url`, `ollama_model`, and `curation_llm_provider` to `settings.py`, defaulting the provider to `anthropic` so behaviour is unchanged until flipped
- [x] 1.2 Document the new keys in the README and `.env`

## 2. Adapter

- [x] 2.1 Create `OllamaLLMClient` implementing the editorial `ILLMClient` port against Ollama's `/api/generate`
- [x] 2.2 Request JSON-constrained output (`format: "json"`), since curation parses the response as JSON
- [x] 2.3 Report an unreachable server and a missing model as distinct, actionable errors
- [x] 2.4 Add port conformance tests, including a partial implementation that must NOT satisfy `ILLMClient`

## 3. Wiring

- [x] 3.1 Add a curation-specific LLM provider in `dependencies.py` that resolves Anthropic or Ollama from configuration
- [x] 3.2 Point `research.py`'s curation construction at it, leaving story-writing, platform-adaptation and subtitle translation on Anthropic
- [x] 3.3 Add a test that selecting the local provider changes only curation's client

## 4. Contract tests

- [x] 4.1 Contract-test the adapter against recorded Ollama response payloads via a mock transport, covering a normal completion, a missing model, and an unreachable server
- [x] 4.2 Verify curation parses a realistic local-model response through the real adapter

## 5. Verification

- [x] 5.1 Run the two currently-FAILED documents through curation with the local provider and report scores, latency, and whether the output parsed
