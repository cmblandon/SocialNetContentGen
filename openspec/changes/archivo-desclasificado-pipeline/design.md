## Context

The project ("Proyecto Expediente") currently implements only the first half of a pipeline: local PDFs → OCR (if needed) → MarkItDown → a local MLX model that produces a `FichaEstructurada` (dataclass) → persisted to SQLite (`src/infrastructure/persistence/sqlite_repo.py`) and indexed in ChromaDB. It follows a Clean/Hexagonal Architecture split (`src/core` = entities + `typing.Protocol` ports, `src/infrastructure` = adapters, `src/application` = use cases, `src/config/settings.py` = centralized `pydantic-settings` config). `src/config/settings.py` already carries an empty `anthropic_api_key`, anticipating cloud agents.

This change adds everything downstream and upstream of that pipeline: automated discovery of official documents, editorial curation, narrative writing, per-platform adaptation, an orchestrator with a mandatory human-approval gate, publishing, and an admin panel to operate all of it. The proposal defines seven new capabilities; this document decides how they fit together technically and in what order they get built.

Two generic docs in `docs/` (`backend-standards.md`, `data-model.md`) describe a `domain/application/presentation/infrastructure` FastAPI+PostgreSQL layout inherited from an unrelated template project (candidate/recruitment domain) — they are not an accurate description of this repo's actual structure and are treated here as style guidance only (naming conventions, testing patterns), not as an architecture to copy verbatim.

## Goals / Non-Goals

**Goals:**
- Deliver the full path from "new official document exists" to "human-approved, per-platform content is published", matching the seven capabilities in the proposal.
- Keep every new external integration (scraper, LLM, publisher) behind a `typing.Protocol` port, mirroring the existing `src/core/ports.py` style, so providers (Firecrawl↔Jina, Postiz↔Ayrshare↔Blotato) are swappable without touching orchestration or agent logic.
- Make the human-approval gate a structural property of the data model and orchestration graph (a piece of content cannot reach the publisher without a persisted `approved` state), not merely a prompt instruction.
- Guarantee provenance: every `Story`/`Chapter` that reaches publishing resolves back to a cited official `Document` (agency, date, doc type).
- Reuse the existing ingestion pipeline's output (`FichaEstructurada` records) as one valid input into `research-agent`/`case-curation`, instead of duplicating PDF/OCR handling.

**Non-Goals:**
- Fully autonomous, unattended daily scheduling (cron) of the editorial cycle. v1 runs are triggered on demand (CLI or an admin-panel action); turning that into a scheduled job is a follow-up change once the manual flow is proven.
- Multi-user roles/permissions in the admin panel. A single internal operator is assumed; auth is a minimal shared-credential gate, not a user-management system.
- Voice and video generation (ElevenLabs, Kling, CapCut). This change stops at approved script + per-platform copy; audio/video production is a separate, later pipeline stage.
- Custom agent-trace/observability UI. LangSmith (external, native to LangChain/deepagents) is used instead; the admin panel at most links out to it.
- Analytics/engagement dashboards. Only the publish API's returned post ID is stored for later manual correlation.

## Decisions

### 1. Orchestration framework: deepagents (LangChain/LangGraph)
Chosen over CrewAI/AutoGen because it ships, out of the box, the three things this pipeline structurally needs: isolated subagent contexts, a virtual filesystem usable as project memory (`casos_cubiertos.md`, `calendario.md`, `manual_de_marca.md`), and native human-in-the-loop interrupts — plus LangGraph checkpointing for free, so an interrupted (pending-approval) run survives a process restart. Building the same guarantees on top of CrewAI/AutoGen would mean hand-rolling the approval-gate persistence this design otherwise gets for free.
**Alternative considered:** CrewAI/AutoGen with a hand-built approval queue table — rejected: more code to maintain for a capability (durable interrupt/resume) the chosen framework already provides.

### 2. One Python service, not a polyglot split
The orchestrator and all five agents run inside the existing Python codebase (new `src/editorial/` bounded context, same `core/application/infrastructure` layering as the ingestion pipeline), exposed over FastAPI. deepagents is a Python library; there is no benefit to hosting agent logic anywhere else.
**Alternative considered:** a separate agents microservice — rejected as premature; nothing here requires independent scaling or deployment yet.

### 3. New bounded context, not an extension of the ingestion schema
`research-agent` produces its own `Document` record (title, agency, published_date, doc_type, source_url, extracted_text/summary, extraction_confidence) rather than repurposing the ingestion pipeline's `documentos` SQLite table (`FichaEstructurada`: resumen_ejecutivo, fragmentos_clave, …) — the shapes and lifecycles differ (one is "raw depuration output", the other is "editorial case record"). When a document originates from the existing manual PDF pipeline, its `Document` record stores a reference to the source `FichaEstructurada` id instead of duplicating fields.
**Alternative considered:** extend `FichaEstructurada`/`documentos` directly — rejected: would couple the local-LLM depuration concern to the editorial/publishing concern, breaking the existing pipeline's single responsibility.

### 4. Database: SQLite for v1, via SQLAlchemy behind a repository port
The new `Document → Story → Chapter → PlatformVersion → PublishRecord` chain is modeled with SQLAlchemy and starts on SQLite (`data/knowledge_base/`), matching the project's current zero-infra local-first posture and avoiding a Postgres/Docker dependency this single-operator tool doesn't yet need. Repositories are defined against `Protocol` interfaces so swapping to Postgres later (if concurrent multi-writer approval becomes real) only touches the infrastructure layer.
**Alternative considered:** PostgreSQL from day one (as the generic `backend-standards.md` template assumes) — deferred: no concurrent-write or scale requirement exists yet to justify the extra operational surface.

### 5. Approval gate: LangGraph `interrupt()` backed by a persisted `PublishRecord.status`
The orchestration graph pauses at a `request_human_approval` node before ever invoking the publisher subagent/tool. The pause is dual-recorded: LangGraph's checkpointer persists the graph state, and each `Chapter`'s `PlatformVersion`s carry an explicit `status` enum (`pending_review | approved | rejected | published | failed`) in SQL. The admin panel reads/writes the SQL status; the orchestrator resumes the graph only when it observes `approved`. This means a piece of content is technically unreachable by the publisher without a DB-level approval row, independent of whether the prompt "remembers" the rule.
**Alternative considered:** rely solely on the agent prompt ("never publish without approval") — rejected per the proposal's own non-negotiable rule; prompts are not enforcement.

### 6. Guardrails enforced by schema validation, not prompt text alone
`writer_agent` and `platform_adapter_agent` must emit structured (Pydantic-validated) output — e.g., a `Chapter` is invalid without a non-empty `source_citation` (agency + doc type + date); a `Story` cannot be marked ready without at least one direct reference into the source `Document`'s extracted text. Validation failures loop back to the writer/curator rather than silently passing malformed content forward.
**Alternative considered:** trust prompt-only compliance — rejected: the proposal explicitly treats fabrication/uncited claims as an unacceptable failure mode, which calls for a technical backstop.

### 7. External providers behind ports, cheapest-first defaults
- `ISourceScraper`: Firecrawl and Jina AI Reader implementations behind one interface; default to Jina (generous free tier) with Firecrawl as the fallback for protected/complex pages, per the proposal's own comparison.
- `ISocialPublisher`: Postiz (self-hosted) as the first implementation; Ayrshare/Blotato are alternate implementations of the same port, swappable without touching `publisher_agent` logic.
- `ILLMClient` (editorial): a cloud Claude client (new implementation of a port analogous to the existing `ILLMClient`, but distinct from the ingestion pipeline's local-MLX implementation) is used for `story-writing`/`platform-adaptation`, since quality/fact-fidelity matters more than cost here — consistent with the proposal's explicit reasoning for preferring an LLM over generic "auto-script" tools.

### 8. Phased delivery order (see Migration Plan) prioritizes visible output over completeness
Rather than building all seven capabilities in dependency order (research → curate → write → adapt → orchestrate → publish → panel), the plan builds `story-writing`/`platform-adaptation` first against the *already-existing* manually-ingested documents, before building the automated front door (`research-agent`/`case-curation`) or the back door (`publishing`). This surfaces working, reviewable narrative output fastest and de-risks the highest-judgment part of the system (turning a document into a faithful story) before investing in scraping infrastructure or a publishing integration.

## Risks / Trade-offs

- **[Risk]** `deepagents`/LangGraph is a new, heavier dependency with no prior usage in this codebase → **[Mitigation]** isolate it entirely inside `src/editorial/infrastructure/agents/`, behind the same `Protocol`-port discipline as everything else; add a wiring smoke test so a framework upgrade that breaks the graph fails fast in CI, not in production.
- **[Risk]** Official-site scraping (war.gov/UFO, cia.gov/readingroom) can break silently on layout/anti-bot changes → **[Mitigation]** `research_agent` treats an inaccessible/unverifiable source as "discard and report", never as a hard pipeline failure, per the proposal; Jina+Firecrawl hybrid gives a fallback path.
- **[Risk]** Human-approval-only publishing creates a hard bottleneck if the operator is unavailable → **[Accepted trade-off]** intentional per editorial policy given the speculative subject matter; not something to design around in v1.
- **[Risk]** Misinformation/defamation exposure inherent to UAP content → **[Mitigation]** enforced via the schema-validated citation requirement (Decision 6) and the structural approval gate (Decision 5), not prompt text alone.
- **[Risk]** Firecrawl's per-page AI-extraction credit multiplier and Ayrshare's per-volume pricing can escalate cost quickly → **[Mitigation]** default to Jina + self-hosted Postiz (Decision 7); Firecrawl/Ayrshare remain available as a drop-in swap behind the same ports if volume justifies the cost later.
- **[Risk]** Introducing a second database schema (editorial) alongside the existing ingestion SQLite file could create ambiguity about which store owns "the document" → **[Mitigation]** Decision 3's explicit foreign reference (`Document.source_ficha_id`) instead of duplication keeps a single source of truth per concern.

## Migration Plan

Additive, phased; each phase ships independently and does not require rolling back a previous one:

1. **Foundation**: FastAPI app skeleton, SQLAlchemy models + Alembic migrations for `Document/Story/Chapter/PlatformVersion/PublishRecord`, new ports (`ISourceScraper`, `ISocialPublisher`, editorial `ILLMClient`) with no implementations wired yet.
2. **story-writing + platform-adaptation**: implemented as plain use cases (no deepagents yet) consuming existing `FichaEstructurada` records manually marked "curated" via a CLI flag or fixture — produces the first end-to-end narrative + per-platform output for manual review.
3. **editorial-orchestration**: introduce deepagents/LangGraph wrapping the Phase 2 use cases as subagents/tools, add the virtual-filesystem memory files, and implement the approval-gate interrupt (Decision 5) against a stub/manual "approve" action.
4. **research-agent + case-curation**: automate the front door (scraping, scoring, `casos_cubiertos.md` bookkeeping), replacing the Phase 2 manual-curation fixture as the orchestrator's real input.
5. **publishing**: implement `ISocialPublisher` (Postiz first) and wire it behind the approval gate; `calendario.md` bookkeeping goes live.
6. **content-admin-panel**: Next.js app against the FastAPI service, replacing the stub approval action from Phase 3 with the real approval queue, calendar, and covered-cases views.

Rollback per phase: since each phase is additive behind its own module/port and its own Alembic migration, disabling a phase means not registering its route/subagent; standard `alembic downgrade` reverts its schema if needed.

## Open Questions

- Where is Postiz (or the chosen publisher) self-hosted — same host as the FastAPI service, or a separate box/container? Affects Phase 5 deployment steps.
- Is SQLite sufficient for the editorial schema through all phases, or should Phase 1 already target Postgres in anticipation of the admin panel's concurrent reads/writes? (Decision 4 assumes SQLite is fine; revisit if Phase 6 usage proves otherwise.)
- What minimal auth is acceptable for the admin panel in Phase 6 (shared token, basic auth, single hardcoded operator login)? Needs a decision before Phase 6 starts.
- Once the manual-trigger flow (Phases 1–6) is validated, what should trigger the daily cycle in production — cron, an admin-panel button, or an external scheduler call? (Explicitly deferred as a Non-Goal, but the follow-up change needs this answered.)
- Confirm actual expected daily/weekly document volume before Phase 4, to validate that Jina's free tier is sufficient or Firecrawl's paid credits are budgeted.
