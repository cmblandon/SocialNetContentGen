## Context

`ResearchAgentUseCase.discover(source_urls)` (`src/editorial/application/research_agent_use_case.py`) calls `self._primary_scraper.fetch(source_url)`, falling back to `self._fallback_scraper.fetch(source_url)` only if the primary returns `None`. The only wiring today (`get_research_agent` in `src/editorial/presentation/routers/research.py`) constructs `primary_scraper=JinaScraperAdapter(...)`, `fallback_scraper=FirecrawlScraperAdapter(...)` (or `None` if `FIRECRAWL_API_KEY` is unset).

`JinaScraperAdapter.fetch` (`r.jina.ai/<url>`) is a plain reader — it returns whatever text the page has, with no query/topic input, and almost always succeeds (any 200 response with non-empty body counts). `FirecrawlScraperAdapter.fetch` posts to Firecrawl's `/v1/extract` with just `{"urls": [source_url]}` — Firecrawl's real `/v1/extract` API additionally accepts a `prompt` (and/or a JSON `schema`) to guide what it extracts from the page, which this adapter doesn't use at all today.

Net effect: because Jina is primary and rarely fails, Firecrawl's fallback path — the only one of the two actually capable of guided extraction — almost never runs. A `query` parameter has no real effect unless it can also influence *which* scraper runs first.

## Goals / Non-Goals

**Goals:**
- Let an operator supply an optional per-run `query` (a topic/focus string) that measurably narrows what gets extracted from a source page, not just a parameter that's accepted and ignored.
- Keep `ISourceScraper` a simple, generic two-method-shaped port — no new protocol members, no scraper-reports-its-own-capabilities machinery, for two adapters.
- Fully backward compatible: omitting `query` (or passing `None`) reproduces exactly today's behavior end to end (same scraper order, same requests, same results).

**Non-Goals:**
- Making Jina's reader itself query-aware — its plain-reader API has no such mode; this is a fixed constraint of the current adapter, not something this change works around.
- Any autonomous "figure out relevance" step inside `ResearchAgentUseCase` — per its existing "does not interpret or write content" requirement, it still never inspects or filters `extracted_text` itself. All the query does is get handed to a scraper's `fetch()`; extraction narrowing (or not) is entirely the scraper's business.
- Saved/reusable queries, or per-source-URL queries (see proposal.md's Non-Goals) — one query per run, full stop.

## Decisions

### 1. Extend `ISourceScraper.fetch` with an optional `query` parameter, not a new method
`fetch(self, source_url: str, query: Optional[str] = None) -> Optional[ScrapedDocument]`. Both adapters implement the new parameter; `JinaScraperAdapter` accepts and ignores it (documented in its docstring as a known limitation, not silently dropped), `FirecrawlScraperAdapter` forwards it as `prompt` in the `/v1/extract` payload when non-`None`.
**Alternative considered**: a separate `fetch_scoped(source_url, query)` method — rejected; it would fork every caller (`ResearchAgentUseCase`, any future adapter) into two near-identical code paths for what is fundamentally one operation with an extra optional input.

### 2. When `query` is given, `ResearchAgentUseCase.discover()` tries the fallback scraper first, then primary
Today's fixed primary→fallback order stays the *default* (no query). When a query is provided, `discover()` inverts the order for that call — try `fallback_scraper` first (if one is configured), then `primary_scraper` — since in this codebase's only wiring, the fallback slot is the query-capable adapter (Firecrawl) and the primary slot is the non-query-capable one (Jina). This keeps `ISourceScraper` free of any "I support queries" flag: the *caller* (the DI wiring in `research.py`, which already knows the concrete adapter types) is what decides which slot is query-capable, simply by choosing what it constructs `ResearchAgentUseCase` with. `discover()` itself just inverts try-order on a boolean ("was a query given"), never inspects adapter types.
If no `fallback_scraper` is configured (`FIRECRAWL_API_KEY` unset) and a query is given, `discover()` falls back to the only scraper it has (today's Jina), which will ignore the query — same graceful degradation as today's "no Firecrawl configured" case, just without the narrowing benefit.
**Alternative considered**: add a `supports_query: bool` (or similar) attribute/protocol member scrapers self-report, and have `discover()` pick based on that — rejected as over-engineering for exactly two adapters where one caller already knows which is which; revisit if a third scraper with different query support is ever added.
**Alternative considered**: always call both scrapers when a query is given and merge/prefer the structured one — rejected; doubles request volume and cost for every query-scoped run, contradicting this change's entire cost-saving motivation.

### 3. `FirecrawlScraperAdapter` maps `query` to Firecrawl's `prompt` field
`{"urls": [source_url], "prompt": query}` when `query` is not `None`; omit the key entirely when it is (matching today's exact payload for the no-query case, so existing tests asserting `client.last_json["urls"] == [...]` alone stay valid for calls made without a query).

### 4. Request/response shape: `POST /research/run` gains an optional `query` field, not a new endpoint
`ResearchRunRequest.query: Optional[str] = None`. `run_research_cycle` (`orchestrator.py`) and `ResearchAgentUseCase.discover` both gain a matching optional `query` parameter threaded straight through — no new orchestration concept, just one more piece of data flowing down the same call chain `source_urls` already takes.

### 5. Frontend: a single-line text input next to "Ejecutar pipeline", not a separate view
Per design precedent from `enhance-admin-panel-ui` (small, single-operator tool, no unnecessary complexity): a plain `<input>` in `PipelineFeed.tsx`'s topbar, value held in local component state, sent as `query` in the `runResearch()` call only when non-empty (empty string is normalized to `undefined`/omitted, not sent as `""`, so the backend's `None`-default path is what actually runs — consistent with Decision 4).

## Risks / Trade-offs

- **[Risk]** The "invert scraper order when a query is given" heuristic is implicit — it works because *today's* wiring happens to put the query-capable adapter in the fallback slot. If someone later reconfigures `get_research_agent()` with a different pair of scrapers, this heuristic silently stops making sense. **[Mitigation]** Document the assumption plainly in `ResearchAgentUseCase`'s docstring and in `get_research_agent()`'s comment, so the coupling is visible at both ends, not just inferred from behavior.
- **[Risk]** Firecrawl's `/v1/extract` `prompt` field's exact effect on output shape is unverified against live Firecrawl docs (same caveat this adapter's file already carries for its base request shape). **[Mitigation]** No behavior in this change depends on a specific *shape* of Firecrawl's guided response beyond what the adapter already parses (`title`/`agency`/`doc_type`/`summary`/`published_date`) — a `prompt` that Firecrawl ignores or handles differently than assumed degrades gracefully to "same shape, possibly less-targeted content," not a parsing failure.
- **[Risk]** A query that's too narrow could cause Firecrawl to return an empty/near-empty `summary`, which `FirecrawlScraperAdapter.fetch` already treats as `None` (existing "returns none when summary is missing or empty" behavior) — falling through to Jina's full-page fetch. **[Accepted]**: this is the same honest "discard and try the next scraper" pattern the codebase already uses elsewhere; a bad query degrading to full-page-fetch is a reasonable, self-correcting outcome, not a new failure mode to guard against specially.

## Migration Plan

1. Extend `ISourceScraper.fetch` and both adapters with the optional `query` parameter (backward compatible on its own — no other code needs to change yet for existing calls to keep working, since `query` defaults to `None`).
2. Update `ResearchAgentUseCase.discover()` to accept `query` and apply the order-inversion decision.
3. Thread `query` through `orchestrator.run_research_cycle` and `POST /research/run`.
4. Frontend: add the query input and wire it through `runResearch()`.
5. Mandatory verification: full backend + frontend unit suites, curl testing of the new request field, E2E re-run if the Pipeline feed's DOM changes enough to affect existing selectors (it shouldn't — this only adds one input, doesn't touch approve/publish/select controls).

Rollback: every change here is additive (new optional parameter, new optional request field, new optional UI input) — reverting the commit(s) fully restores today's behavior with no data migration involved.

## Open Questions

- Should a run's `query` be recorded anywhere (e.g. appended to `calendario.md` or a run-history log) for later audit of "what was this run looking for"? Deferred — out of scope per proposal.md's Non-Goals; revisit if operators want run history beyond what `casos_cubiertos.md` already captures per-document.
