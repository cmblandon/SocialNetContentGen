## Why

`run_research_cycle` (`src/editorial/application/orchestrator.py`) discovers documents, then loops over them calling `case_curation.curate(scraped_document)` with no error handling around the LLM call inside it (`CaseCurationUseCase.curate` → `self._llm_client.complete(prompt)`, per `case_curation_use_case.py`). If that call raises for any reason — an Anthropic billing/rate-limit error, a transient network failure, a malformed LLM response — the exception propagates all the way up through the FastAPI endpoint as an unhandled 500. Every document already fetched by the scraper in that batch but not yet curated is lost outright: it was never persisted anywhere (a `Document` row is only created for documents that *advance* past curation), and it's never recorded in `casos_cubiertos.md` either (that only happens after a successful curation call). A retry with the same source URLs re-scrapes everything from scratch, re-spending Jina/Firecrawl calls for content already fetched once, and there is no way to pick up curation again for what was already found without providing the URLs again.

This was hit directly: a real `POST /research/run` call scraped a document successfully, then crashed on curation because the Anthropic account had run out of credit, losing that scraped document with no trace of it anywhere.

## What Changes

- Persist every document the scraper successfully fetches immediately after discovery, before curation is ever attempted — decoupling "found via scraping" from "evaluated by curation" as two independently-resumable checkpoints.
- Wrap each document's curation attempt in error isolation: one document's curation failure (LLM error, malformed response, etc.) no longer aborts the rest of the batch — the remaining already-scraped documents in the same run still get their chance at curation/writing/adaptation.
- Record a failure reason against the checkpointed document when curation fails, distinct from "discarded" (which means curation *ran* and scored below threshold) — a failed document is retryable; a discarded one is a permanent, final outcome per `specs/case-curation`.
- Add an explicit **resume** action (`POST /research/resume`) that re-attempts curation → writing → adaptation for every checkpointed document still in a retryable state (pending or failed), with no source URLs needed and no re-scraping — this is what lets the operator recover after fixing whatever broke (e.g. topping up API credit) without spending scraper calls again.
- `research_agent.discover()`'s dedup check is extended so a source URL already checkpointed (pending or failed retry) is not re-scraped on a subsequent `POST /research/run` call with the same URL — only `casos_cubiertos.md` was checked before; now the checkpoint store is checked too.
- Surface failed/pending documents in the admin panel's Pipeline feed (or a lightweight indicator) so the operator knows there's something to resume, and add a "Reanudar pipeline" action alongside "Ejecutar pipeline" that calls the new resume endpoint.

**Non-Goals**:
- No automatic retry-on-a-schedule (cron/background job) — resume stays an explicit operator action, consistent with this project's existing "no autonomous triggering" Non-Goal for the pipeline overall.
- No change to the curation scoring logic, the advancement threshold, or what counts as "discarded" — `specs/case-curation`'s existing scoring/recording requirements are unchanged; this only protects already-scraped content from being lost when curation itself fails to run.
- No retry/checkpointing for the *writing* or *platform-adaptation* stages specifically — those already run synchronously right after a successful curation within the same document's processing step in today's code, and are not the failure this change was written in response to. If a similar loss is later found there, it's a separate change.
- No new scraper-level retry/backoff logic (e.g. auto-retrying a failed Jina fetch) — scraper-level failures are already handled today (fall back to the secondary scraper, then discard-and-report); this change is only about protecting successfully-scraped content from being lost at the *curation* step.

## Capabilities

### New Capabilities
- `research-pipeline-checkpointing`: persisting scraped-but-not-yet-curated documents as a durable checkpoint, isolating per-document curation failures, and providing an explicit resume action to continue processing checkpointed documents without re-scraping.

### Modified Capabilities
- `case-curation`: curation failures (as opposed to curation *outcomes* — advanced/discarded) are now a distinct, retryable state rather than an unhandled crash.
- `content-admin-panel`: the Pipeline view gains visibility into documents awaiting/failed curation and a "Reanudar pipeline" (resume) action.

## Impact

- **Backend**: a new persistence model for checkpointed documents (exact shape decided in design.md); `src/editorial/application/orchestrator.py` (`run_research_cycle` persists before curating, isolates curation failures per document); `src/editorial/application/research_agent_use_case.py` (`discover()`'s dedup check extended); `src/editorial/presentation/routers/research.py` (new `POST /research/resume` endpoint).
- **Frontend**: `frontend/src/lib/api.ts` (new `resumePipeline()` call), `frontend/src/components/PipelineFeed.tsx` (a "Reanudar pipeline" action and a way to see pending/failed checkpointed documents).
- **Existing tests touched**: `test_research_cycle.py` (curation-failure isolation, checkpoint dedup — implemented here rather than in `research_agent_use_case.py`, see design.md Decision 4's final choice), `test_research_endpoint.py` (new resume/summary endpoint tests), `test_editorial_migrations.py` (new table), `PipelineFeed.test.tsx`. `test_research_agent_use_case.py` is unaffected — `ResearchAgentUseCase.discover()` itself was not changed.
- **No breaking changes**: `POST /research/run`'s existing request/response shape is unchanged for the success path; the new checkpoint/resume behavior is additive.
