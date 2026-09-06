## Why

`ResearchAgentUseCase.discover()` and both scraper adapters (`JinaScraperAdapter`, `FirecrawlScraperAdapter`) always fetch and extract the *entire* readable content of every source URL — there is no way for the operator to say what they're actually looking for. For a source page that covers many unrelated cases (a general reading-room index, a broad annual report), this means scraping and passing the whole page downstream into curation every time, wasting scraping cost/time and diluting curation with irrelevant material, when the operator often already knows the topic or case type they want this run to surface.

## What Changes

- Add an optional `query` (topic/focus, e.g. "Malmstrom missile incidents") to a pipeline run: `POST /research/run`'s request body, threaded through `run_research_cycle` → `ResearchAgentUseCase.discover(source_urls, query=None)` → `ISourceScraper.fetch(source_url, query=None)`.
- Extend the `ISourceScraper` port's `fetch` signature to accept an optional `query` parameter (backward compatible — defaults to `None`, meaning "fetch the whole page," today's behavior).
- `FirecrawlScraperAdapter` passes a given `query` as Firecrawl's `/v1/extract` `prompt` field, so Firecrawl performs guided/targeted extraction instead of a generic full-page summary.
- `JinaScraperAdapter`'s reader endpoint (`r.jina.ai`) has no natural-language query mode — it keeps fetching the full page regardless of `query`. To actually narrow extraction when a query is given, `ResearchAgentUseCase` prefers the query-capable scraper (Firecrawl) as primary and only falls back to Jina's full-page fetch on Firecrawl failure; with no query, today's Jina-primary/Firecrawl-fallback order is unchanged.
- Add a "topic/query" input next to "Ejecutar pipeline" in the Pipeline view, sent alongside the configured source URLs (optional — leaving it blank preserves today's whole-page behavior).

**Non-Goals**:
- No change to the official-source allowlist or the covered-cases dedup check — those still run before any fetch, independent of `query`.
- No persistence of past queries — each run's query is one-off input, not stored in `fuentes.md`/Configuración (per-URL or saved-query presets are a possible future change, not this one).
- No change to `ScrapedDocument`'s shape or to case-curation/story-writing — `query` only affects what a scraper extracts, not how downstream stages interpret it.

## Capabilities

### New Capabilities
_None — this extends two existing capabilities._

### Modified Capabilities
- `research-agent`: adds a requirement that extraction SHALL be scoped to an operator-provided query when one is given, using the query-capable scraper.
- `content-admin-panel`: the "Trigger a pipeline run from the panel" requirement gains an optional query field on the run-trigger action.

## Impact

- **Backend**: `src/editorial/core/ports.py` (`ISourceScraper.fetch` signature), `src/editorial/infrastructure/scraping/jina_scraper.py` and `firecrawl_scraper.py` (accept optional `query`), `src/editorial/application/research_agent_use_case.py` (`discover()` takes optional `query`, decides scraper order accordingly), `src/editorial/application/orchestrator.py` (`run_research_cycle` threads `query` through), `src/editorial/presentation/routers/research.py` (`ResearchRunRequest` gains optional `query`).
- **Frontend**: `frontend/src/lib/api.ts` (`runResearch` takes an optional query), `frontend/src/components/PipelineFeed.tsx` (query input next to "Ejecutar pipeline").
- **Existing tests touched**: `test_jina_scraper.py`, `test_firecrawl_scraper.py`, `test_research_agent_use_case.py`, `test_research_cycle.py`, `test_research_endpoint.py`, `PipelineFeed.test.tsx`.
- **No breaking changes**: `query` is optional everywhere with a `None`/absent default that reproduces today's exact behavior.
