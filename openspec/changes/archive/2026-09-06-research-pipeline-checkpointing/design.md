## Context

Today's flow, all inside one `POST /research/run` call (`orchestrator.run_research_cycle`):

```python
research_result = research_agent.discover(source_urls, query=query)   # scrape

for scraped_document in research_result.documents:                    # loop, in-memory only
    curation_result = case_curation.curate(scraped_document)           # <-- no try/except
    if curation_result is None or not curation_result.advanced:
        continue
    document = Document(...)                                          # only NOW persisted
    session.add(document); session.commit()
    documents_with_angles.append((document, curation_result.narrative_angle))

return run_cycle(session, documents_with_angles, ...)                  # write + adapt + persist
```

Nothing survives between `discover()` returning and a document successfully clearing curation. `CaseCurationUseCase.curate()` calls `self._llm_client.complete(prompt)` (`case_curation_use_case.py`) with no error handling; any exception there (Anthropic billing/rate-limit error, network failure, malformed JSON response — `CurationError` is raised deliberately for the JSON/score-shape cases, but the raw LLM call itself is unguarded) propagates straight out of the `for` loop, aborting every remaining document in `research_result.documents` and returning a 500 to the caller. Documents already fetched are gone: never persisted, never recorded in `casos_cubiertos.md` (`CaseCurationUseCase._record` only runs *after* a successful LLM call).

**A second, subtler loss discovered while implementing**: `run_cycle` (write_story → adapt_chapter → persist_story) is called exactly **once**, after the *entire* curation loop finishes, over the accumulated `documents_with_angles` batch — it is not called per-document as each one advances. This means if curation crashes on, say, the 3rd of 5 documents, the 1st and 2nd documents — which already cleared curation, already got a bare `Document` row `session.add`'d and committed, and are sitting in `documents_with_angles` — **never reach `run_cycle` at all**, since the function returns (via the unhandled exception) before that final call is made. They become orphaned `Document` rows with no `Story`/`Chapter`/`PlatformVersion` ever created for them, and no error recorded against them either. Decision 2 below is written with this in mind: the shared per-document helper must curate **and**, if advanced, write/adapt/persist **immediately** for that one document, not accumulate a batch for a single later `run_cycle` call — this is required to actually stop the loss, not just to checkpoint the pre-curation scrape.

`ResearchAgentUseCase.discover()`'s only dedup check is against `casos_cubiertos.md` (`if source_url in already_covered: continue`) — a URL that was scraped but never reached that file (because curation crashed) looks exactly like a URL never attempted, so a retry re-scrapes it.

## Goals / Non-Goals

**Goals:**
- No successfully-scraped document is ever silently lost, regardless of what happens downstream in curation.
- One document's curation failure doesn't block the rest of the batch from being processed in the same run.
- An operator can resume processing everything that was scraped-but-not-yet-successfully-curated without re-supplying source URLs and without re-scraping.
- A retried `POST /research/run` with the same URLs doesn't re-scrape content already checkpointed.

**Non-Goals** (see proposal.md for the full list):
- No automatic/scheduled retry.
- No change to curation's scoring/threshold/advancement rules.
- No checkpointing inside the writing/platform-adaptation stages.

## Decisions

### 1. A new `DiscoveredDocument` table, not a status field on `Document`
New SQLAlchemy model, `discovered_documents`, mirroring `ScrapedDocument`'s fields (`title`, `agency`, `doc_type`, `extracted_text`, `published_date`, `source_url`, `extraction_confidence`) plus:
- `status: CurationStatus` (new enum: `PENDING`, `ADVANCED`, `DISCARDED`, `FAILED`)
- `error_message: Optional[str]` (populated only when `status == FAILED`)
- `narrative_angle: Optional[str]` (populated once curated and advanced, mirroring `Story.narrative_angle`)
- `document_id: Optional[str]` (FK to `documents.id`, set once a real `Document`/`Story` chain is created for an advanced case — links the checkpoint back to the eventual case record)
- `created_at`, `updated_at`

**Alternative considered**: add a `curation_status` column directly to `Document` and create a `Document` row immediately on scrape (before curation), rather than only for advanced cases as today. Rejected: `Document` currently means "an editorial case with a story" throughout the codebase (`Document.stories` relationship, the admin panel's cases view reading from `casos_cubiertos.md` not the DB, `manual_curation_cli` assuming a `Document` is ready-to-write-from) — repurposing it to also mean "anything ever scraped, including permanently discarded/failed ones" would be a much larger, riskier semantic change than adding one narrowly-scoped new table. A dedicated table also mirrors this project's existing pattern of "plain records for one clear purpose" (see `PublishRecord` existing alongside `PlatformVersion` rather than folding publish state into it).

### 2. Curation failure isolation: per-document try/except, and `run_cycle` called once per advancing document — not batched at the end
`CaseCurationUseCase.curate()` keeps raising `CurationError`/letting LLM-client exceptions propagate — that's still correct behavior *for that one call*. The isolation belongs in the orchestration loop that iterates multiple documents: the per-document helper catches any exception from `case_curation.curate(...)`, marks that document's checkpoint `FAILED` with the exception's message, and continues to the next document rather than letting the exception unwind the whole request.

Critically, this also fixes the second loss described in Context: `run_cycle` (`orchestrator.py`) is not changed — it keeps its existing, independently-tested contract (`run_cycle(session, documents_with_angles: list[tuple[Document, str]], ...)`, batch-shaped, per `test_orchestrator_cycle.py`). What changes is *how many times, and when* `run_research_cycle` calls it: today it accumulates every advanced document into one list and calls `run_cycle` exactly once at the very end; the fix calls `run_cycle(session, [(document, narrative_angle)], ...)` — a single-element list — **immediately** after each individual document advances, inside the per-document helper, so a later document's curation crash can no longer strand an earlier document's already-advanced-but-not-yet-written case. `run_research_cycle` (and the new resume path) then aggregate the per-call `CycleSummary` objects (simple field-wise sum; add a small `CycleSummary.merge`/`__iadd__` helper if that reads cleaner than manual accumulation) into the one `CycleSummary` returned to the caller — the response shape callers see is unchanged.
**Alternative considered**: catch inside `CaseCurationUseCase.curate()` and return a sentinel/result-with-error instead of raising — rejected; `curate()`'s contract (raise on malformed output, return `None`/`CurationResult` otherwise) is already exercised by existing tests and other callers' expectations; changing it to a three-way "success/discarded/errored" return shape is a wider-reaching signature change for less benefit than catching one level up, where the batching concern actually lives.
**Alternative considered**: change `run_cycle` itself to accept and process one document at a time. Rejected — `run_cycle` already has a solid, separately-tested multi-document batch contract with no bugs of its own (the loss only happens in how `run_research_cycle` *calls* it); calling it N times with 1-element lists reuses that tested contract unchanged rather than reshaping it.

### 3. `POST /research/resume` — reprocesses checkpointed documents, takes no `source_urls`
New endpoint, same underlying per-document curate→write→adapt→persist logic as `run_research_cycle`'s inner loop, but sourced from `DiscoveredDocument` rows with `status IN (PENDING, FAILED)` instead of from a fresh `discover()` call. Refactor: extract the "given a `ScrapedDocument`-shaped record, curate it and (if advanced) write/adapt/persist it" logic into a shared function both `run_research_cycle` and the new resume path call, so the two entry points (fresh discovery vs. resuming) share one curation-and-beyond implementation and can't drift apart.
**Alternative considered**: fold resume into `POST /research/run` itself (e.g., calling it with an empty `source_urls` list means "just resume") — rejected; `source_urls` already has a `Field(min_length=1)` validator and a dedicated existing test asserting that, and conflating "start fresh" with "resume" into one endpoint's implicit behavior based on an empty list is a less discoverable API than a separate, explicitly-named action — matching this project's existing preference for one small endpoint per distinct action (`/approve` vs `/reject` vs `/publish`, not one overloaded endpoint).

### 4. Dedup: `discover()` also checks `DiscoveredDocument.source_url` for non-terminal rows
`ResearchAgentUseCase.discover()` gains an optional dependency check (or the checkpoint-read happens in `run_research_cycle` before calling `discover()`, filtering `source_urls` first — simpler, keeps `ResearchAgentUseCase` itself free of a new DB dependency it didn't have before). **Chosen**: `run_research_cycle` filters `source_urls` against `DiscoveredDocument` rows with `status IN (PENDING, FAILED)` before calling `discover()`, skipping any URL already checkpointed and not yet resolved — `ResearchAgentUseCase` itself stays unchanged (it already takes no DB session; giving it one now just for this dedup check would be a bigger, less isolated change than filtering one level up where a `Session` is already in scope).
**Alternative considered**: teach `ResearchAgentUseCase.discover()` to take the DB session and do this check itself, symmetric with its existing `casos_cubiertos.md` dedup. Rejected for the reason above — `research_agent_use_case.py` currently has zero SQLAlchemy dependency (its only stateful dependency is `ProjectMemoryStore`, a plain-file store), and introducing `Session` there is a bigger architectural shift than filtering the URL list before it's called.

### 5. Checkpoint rows are never deleted — kept as a permanent audit trail
Once a `DiscoveredDocument` reaches `ADVANCED` or `DISCARDED`, it stays in the table (status updated in place, `document_id` set for `ADVANCED` ones) rather than being deleted — consistent with `casos_cubiertos.md`'s "every case evaluated, advanced or discarded, permanently recorded" philosophy (`specs/case-curation`). `FAILED` rows stay `FAILED` until a resume attempt changes their status (to `ADVANCED`, `DISCARDED`, or back to `FAILED` again with an updated `error_message` if it fails the same way twice).

### 6. Frontend: a lightweight "needs attention" indicator + one resume action, not a whole new view
Per this project's "no unnecessary complexity for a single-operator tool" precedent (`enhance-admin-panel-ui` design.md): `PipelineFeed.tsx` gets a small banner/pill when `GET`-ing pending/failed checkpoint counts shows anything outstanding (e.g. "3 documentos pendientes de curación, 1 fallido — Reanudar pipeline"), with a "Reanudar pipeline" button calling the new resume endpoint. No dedicated list/table view of checkpointed documents in this change — if that's needed later (e.g. to see *which* document failed and why before deciding to retry), it's a natural follow-up, not required to fix the actual bug this change addresses.

## Risks / Trade-offs

- **[Risk]** A new table means a new Alembic migration — the first schema change since the initial editorial schema. **[Mitigation]** Follow the exact existing pattern (`src/editorial/infrastructure/persistence/migrations/versions/0001_initial_editorial_schema.py`) for a new revision; both `upgrade()` and `downgrade()` required, per `docs/backend-standards.md`.
- **[Risk]** Extracting the shared curate→write→adapt→persist logic (Decision 3) touches `run_research_cycle`, a function with existing test coverage and callers. **[Mitigation]** Keep `run_research_cycle`'s existing signature and `CycleSummary` return shape unchanged; the refactor is internal (a private helper both it and the new resume path call), not a public contract change — all of `test_research_cycle.py`'s existing tests must keep passing unmodified.
- **[Risk]** If curation keeps failing for the same systemic reason (e.g. credit still not topped up), calling resume repeatedly just re-fails every `FAILED` row again, each time consuming an LLM call attempt that immediately errors. **[Accepted]**: this is the same class of cost as any retry-on-demand action; the operator controls when to call resume, and a resume attempt failing again is informative (confirms the underlying issue isn't fixed yet), not harmful.
- **[Risk]** Concurrent runs (a fresh `/research/run` while a resume is also in flight) could race on the same `DiscoveredDocument` rows. **[Accepted, matches existing precedent]**: this project has no concurrency control anywhere in the editorial pipeline today (single-operator tool, SQLite backing store); out of scope here same as everywhere else.

## Migration Plan

1. Add the `DiscoveredDocument` model + `CurationStatus` enum, new Alembic revision.
2. Extract the shared per-document curate→write→adapt→persist helper; have `run_research_cycle` checkpoint before curating and use the helper, catching and recording curation failures per document instead of letting them propagate.
3. Extend the pre-`discover()` URL filter in `run_research_cycle` against non-terminal `DiscoveredDocument` rows.
4. Add `POST /research/resume`, using the same shared helper against `PENDING`/`FAILED` rows.
5. Frontend: pending/failed indicator + "Reanudar pipeline" action in `PipelineFeed.tsx`.
6. Mandatory verification: full unit-test run, curl testing (including deliberately simulating a curation failure to confirm checkpointing and resume both work end-to-end), E2E regression check, documentation updates.

Rollback: revert the commit(s) and run the migration's `downgrade()` to drop the new table — no existing table's schema is altered, so this is a clean, additive rollback.

## Open Questions

- Should `GET /research/pending` (or similar) exist to let the operator inspect *which* documents are pending/failed and why, beyond a count/banner? Deferred per Decision 6 — start minimal, add a detail view if the count-only banner proves insufficient in practice.
