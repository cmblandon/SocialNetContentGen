## Why

"Proyecto Expediente" currently stops at local ingestion: PDFs dropped by hand into `data/docs_raw/` become structured `FichaEstructurada` records in SQLite/ChromaDB, and nothing downstream exists. There is no automated discovery of new official declassified UFO/UAP documents, no narrative story generation, no per-platform (TikTok/Facebook/X/Instagram) adaptation, and no gated way to review and publish content. To turn the ingestion pipeline into an actual editorial operation ("Archivo Desclasificado"), we need the remaining multiagent pipeline — research, curation, writing, platform adaptation, orchestration with mandatory human approval, and publishing — built on top of the existing Clean Architecture core.

## What Changes

- Add a `research_agent` capability that automates discovery and structured extraction of official documents from war.gov/UFO, cia.gov/readingroom, archives.gov, AARO/ODNI reports, and The Black Vault (as a locator only), replacing the manual "drop a PDF" step for these sources while keeping manual ingestion available.
- Add a `case_curation` capability that scores incoming documents (novedad, potencial narrativo, respaldo documental, elemento visual, encaje de audiencia), enforces the ≥15/25 threshold, and records every evaluated case (advanced or discarded) so nothing is reprocessed.
- Add a `story_writing` capability that converts a curated document into a hooked narrative, splitting into 60–90s chapters when the source material is extensive, each chapter independently publishable with a real (non-fabricated) cliffhanger.
- Add a `platform_adaptation` capability that rewrites each chapter into TikTok/Reels, Instagram (reel + optional carousel), X thread, and Facebook post formats without altering the underlying facts or spoken script.
- Add an `editorial_orchestration` capability: a deepagents/LangGraph root agent that runs the daily cycle (investigate → curate → write → adapt → approve → publish), maintains project memory (`casos_cubiertos.md`, `calendario.md`, `manual_de_marca.md`) in a virtual filesystem, delegates each stage to its subagent, and — non-negotiably — blocks on explicit human approval before anything reaches the publisher.
- Add a `publishing` capability that schedules/publishes only human-approved platform versions through a connected social API (Postiz self-hosted first; Ayrshare/Blotato as swappable connectors), records publish results in `calendario.md`, and reports (not silently retries) failures to the orchestrator.
- Add a `content_admin_panel` capability: a Next.js panel backed by the new FastAPI service, centered on the human-approval queue (source document, story summary, chapter scripts, per-platform versions, approve/reject), plus editorial calendar and covered-cases views.
- Introduce the backend service layer needed to host the above: FastAPI app, SQLAlchemy models and migrations for the `Document → Story → Chapter → PlatformVersion → PublishRecord` chain, and the deepagents/LangGraph runtime dependency.

## Capabilities

### New Capabilities
- `research-agent`: Discovers and extracts structured records (title, date, agency, doc type, full text/summary) from official declassified UFO/UAP sources, deduplicated against covered cases.
- `case-curation`: Scores and filters documents for narrative/production readiness, and maintains the permanent record of every case evaluated.
- `story-writing`: Turns a curated document into a hook-driven, chapterized, fact-bound narrative script with visual and sourcing notes.
- `platform-adaptation`: Reformats a chapter's script into TikTok/Reels, Instagram, X, and Facebook variants without changing facts or the core spoken script.
- `editorial-orchestration`: Runs the end-to-end daily cycle, owns project memory, delegates to subagents, and enforces the mandatory human-approval gate before publishing.
- `publishing`: Schedules and publishes human-approved content via a pluggable social API connector and records outcomes for later metrics correlation.
- `content-admin-panel`: Next.js administration UI for the approval queue, editorial calendar, and covered-cases management, backed by a new FastAPI service.

### Modified Capabilities
_None — this change is additive on top of the existing ingestion pipeline (`chunking`, PDF reading) and does not alter their requirements._

## Impact

- **New runtime dependency**: `deepagents` (LangChain/LangGraph) for orchestration, subagent isolation, virtual-filesystem memory, and human-in-the-loop interrupts.
- **New backend service**: FastAPI app + SQLAlchemy/Alembic models (`Document`, `Story`, `Chapter`, `PlatformVersion`, `PublishRecord`), separate from (but consuming) the existing local ingestion pipeline's `IDocumentRepository`/`ISemanticIndex` outputs.
- **New frontend app**: Next.js admin panel (new top-level directory), calling the FastAPI service.
- **New external integrations**: a scraping/extraction tool (Firecrawl and/or Jina AI Reader) for `research-agent`; a publishing connector (Postiz self-hosted to start) for `publishing`; Anthropic API (already stubbed in `src/config/settings.py` as `anthropic_api_key`) for `story-writing` and `platform-adaptation`.
- **Existing code touched**: `src/core/entities.py` / `src/core/ports.py` gain new ports for the additional stages; `src/config/settings.py` gains configuration for the new external services; no changes to the existing OCR/depurador/chunking flow.
- **Editorial/legal surface**: introduces content that must always distinguish documented fact from speculation, always cite the official source, and never publish without explicit human approval — these are treated as hard requirements in the specs, not just documentation.
