# Archivo Desclasificado

A pipeline that turns official declassified UFO/UAP documents into
narrative, source-cited stories, adapts them per social platform, and
publishes them behind a mandatory human-approval gate. Built in two
bounded contexts across two OpenSpec changes: the local ingestion pipeline
("Proyecto Expediente", below) and the editorial service
(`src/editorial/` + `frontend/`, implementing
`openspec/changes/archivo-desclasificado-pipeline/`).

## End-to-end pipeline

```
   INGESTION (local, manual)                    EDITORIAL SERVICE (src/editorial/ + frontend/)
  ┌─────────────────────────┐   ┌──────────────────────────────────────────────────────────────────┐
  │ PDF -> OCR? -> MarkItDown│   │ research-agent -> case-curation -> story-writing -> platform-      │
  │ -> Depurador (MLX local) │──▶│ adaptation -> [human approval, admin panel] -> publishing (Postiz) │
  │ -> SQLite + ChromaDB     │   │                                                                    │
  └─────────────────────────┘   └──────────────────────────────────────────────────────────────────┘
```

- **Ingestion** (this section, §1-6 below): manual PDF drop-in, 100% local, produces a `FichaEstructurada` in `expedientes.sqlite`.
- **research-agent / case-curation** ([§ Research sources](#research-sources-and-the-scraper-fallback), [§ scoring rubric](#case-curation-scoring-rubric)): discovers or accepts a document, scores it, decides whether it's worth writing.
- **story-writing / platform-adaptation** ([§ manual CLI](#running-the-manual-story--platform-adaptation-cli)): turns a curated document into a chaptered story and four platform-specific versions.
- **orchestration / human approval** (see the "Editorial Service" and "Editorial Admin Panel" sections below): `run_cycle`/`run_research_cycle` tie the above together; nothing reaches a publisher without an explicit approval recorded via the API or the admin panel.
- **publishing** ([§ Publishing](#publishing-and-the-publisher-swap-mechanism)): approved content goes out through `ISocialPublisher` (Postiz by default), with every attempt recorded for the calendar view.

Each stage's own README section below has the concrete setup/run
instructions; this is just the map connecting them.

# Pipeline de ingesta — Proyecto Expediente

Convierte PDFs de documentos desclasificados en fichas estructuradas
(JSON) almacenadas localmente, listas para que los agentes de guion
(vía API cloud) las consuman sin gastar tokens en ruido.

```
PDF crudo -> ¿tiene texto? -> [OCR si no] -> MarkItDown -> Depurador (modelo local MLX) -> SQLite + ChromaDB
```

## 1. Instalación (una sola vez)

```bash
# Herramientas de sistema para OCR (solo si vas a necesitar OCR)
brew install tesseract tesseract-lang ocrmypdf

# Entorno Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Descarga el modelo local (una sola vez)

MLX descarga el modelo la primera vez que lo usas y lo cachea localmente.

```bash
# En una terminal aparte, deja esto corriendo mientras usas el pipeline:
mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
```

Si tu M3 Pro va lento con 7B, prueba con:
`mlx-community/Llama-3.2-3B-Instruct-4bit`

## 3. Configuración (.env)

El proyecto utiliza `pydantic-settings` para la configuración. Las rutas base (`data/`, `src/`) se detectan automáticamente, pero puedes sobreescribir variables o configurar API keys creando un archivo `.env` en la raíz del proyecto (este archivo está excluido del control de versiones):

```env
# Ejemplo de .env
ANTHROPIC_API_KEY=sk-ant-api03-...
ELEVENLABS_API_KEY=...
# LOCAL_LLM_URL=http://localhost:8080/v1/chat/completions
```

## 4. Uso

```bash
# 1. Coloca tus PDFs en data/docs_raw/
cp ~/Downloads/documentos_foia/*.pdf data/docs_raw/

# 2. Con el servidor MLX corriendo en otra terminal, ejecuta desde la raíz:
python -m src.main
```

## 5. Estructura del proyecto (Clean Architecture)

```
proyecto-expediente/
├── data/                    # Datos generados (ignorado en git)
│   ├── docs_raw/            # PDFs de entrada
│   ├── docs_procesados/     # PDFs ya procesados
│   └── knowledge_base/      # SQLite (expedientes.sqlite) y ChromaDB
│
├── src/
│   ├── core/                # Dominio puro — sin dependencias externas
│   │   ├── entities.py      # FichaEstructurada (dataclass canónica)
│   │   └── ports.py         # Interfaces: IPdfInspector, IOcrProcessor, ILLMClient, IDocumentRepository, ISemanticIndex
│   │
│   ├── config/
│   │   └── settings.py      # Configuración centralizada y validada con pydantic
│   │
│   ├── infrastructure/      # Adaptadores concretos de I/O
│   │   ├── pdf/
│   │   │   └── pdf_reader.py # Detección de texto y OCR
│   │   ├── llm/
│   │   │   └── local_llm_client.py
│   │   └── persistence/
│   │       ├── sqlite_repo.py
│   │       └── chroma_repo.py
│   │
│   ├── application/         # Casos de uso
│   │   ├── chunking.py      # Función pura para chunking
│   │   └── ingest_use_case.py # IngestUseCase
│   │
│   ├── prompts/
│   │   └── depurador.md     # Template para el LLM
│   │
│   └── main.py              # Composition Root — punto de entrada
│
├── tests/                   # Pruebas automatizadas
├── README.md
└── requirements.txt
```

**Principio clave**: `src/core/` no importa nada de `src/infrastructure/`. Las dependencias apuntan hacia adentro (hacia el dominio).

## 6. Verificar resultados rápido

```bash
sqlite3 data/knowledge_base/expedientes.sqlite "SELECT id, archivo_origen, confiabilidad_extraccion FROM documentos;"
```

## Notas importantes

- **Nada de esto sale a la nube (aún).** El texto crudo, el OCR y la depuración
  corren 100% en tu máquina. Solo cuando conectemos Agentes cloud, se enviará el `resumen_ejecutivo`
  + `fragmentos_clave` ya depurados — no el documento completo.
- **`confiabilidad_extraccion: "baja"`** es una señal para revisar ese
  documento a mano antes de usarlo en un expediente.
- **Reprocesar todo**: si cambias el prompt en `src/prompts/depurador.md`
  y quieres reingerir documentos ya procesados, muévelos de vuelta de
  `data/docs_procesados/` a `data/docs_raw/`.
- **Agregar un nuevo adaptador** (ej. PostgreSQL en vez de SQLite): implementa
  `IDocumentRepository` en `src/infrastructure/persistence/` y cámbialo
  en `src/main.py` — ninguna otra capa necesita cambiar.

## Editorial Service (`src/editorial/` — "Archivo Desclasificado")

This is a second, distinct bounded context being built on top of the ingestion
pipeline above, implementing the `archivo-desclasificado-pipeline` OpenSpec
change (see `openspec/changes/archivo-desclasificado-pipeline/`). It turns
curated documents into narrative stories, adapts them per social platform, and
publishes them behind a mandatory human-approval gate.

### How it relates to the ingestion pipeline

- The ingestion pipeline (`src/core`, `src/application`, `src/infrastructure`)
  is unchanged and keeps owning `FichaEstructurada` records in
  `data/knowledge_base/expedientes.sqlite`.
- `src/editorial/` owns its own schema (`data/knowledge_base/editorial.sqlite`,
  managed by Alembic — see `alembic.ini`) built around a different concern:
  editorial case records, not raw LLM-depuration output.
- When an editorial `Document` originates from a manually-ingested PDF, it
  stores a reference to the source `FichaEstructurada` via
  `Document.source_ficha_id` instead of duplicating its fields.

### Module layout

Follows the same Clean/Hexagonal Architecture split as the ingestion pipeline:

```
src/editorial/
├── core/
│   ├── entities.py          # ChapterDraft, StoryDraft, PlatformAdaptations, ...
│   ├── exceptions.py         # StoryGenerationError
│   └── ports.py              # ISourceScraper, ISocialPublisher, ILLMClient (Protocols)
├── application/
│   ├── story_writing_use_case.py        # Document -> StoryDraft (chapters + hooks)
│   ├── platform_adaptation_use_case.py  # Chapter -> TikTok/Instagram/X/Facebook
│   ├── research_agent_use_case.py       # candidate URLs -> ScrapedDocument list
│   ├── case_curation_use_case.py        # ScrapedDocument -> score + narrative angle
│   └── manual_curation_cli.py           # Phase 2 manual entrypoint (see below)
├── infrastructure/
│   ├── llm/
│   │   └── anthropic_llm_client.py      # Cloud ILLMClient implementation
│   ├── scraping/
│   │   ├── jina_scraper.py              # Default ISourceScraper (cheap, raw text)
│   │   ├── firecrawl_scraper.py         # Fallback ISourceScraper (AI-structured)
│   │   └── doc_type.py                  # Shared URL-extension -> doc_type heuristic
│   ├── publishing/
│   │   └── postiz_publisher.py          # Default ISocialPublisher (self-hosted Postiz)
│   └── persistence/
│       ├── models.py        # SQLAlchemy models: Document, Story, Chapter,
│       │                    # PlatformVersion, PublishRecord
│       ├── ficha_reader.py   # Read-only access to the ingestion pipeline's SQLite
│       ├── project_memory.py # ProjectMemoryStore: casos_cubiertos.md, calendario.md, manual_de_marca.md
│       ├── session.py        # SQLAlchemy session factory for editorial.sqlite
│       └── migrations/      # Alembic environment + revisions
└── presentation/
    ├── app.py                # FastAPI composition root (routers added per phase)
    ├── dependencies.py       # Shared DI providers (memory store, LLM client, publisher)
    └── routers/
        ├── approval.py       # POST /platform-versions/{id}/approve|reject|publish
        ├── research.py       # POST /research/run; GET/POST /research/sources; POST /research/sources/delete
        └── publish_records.py # GET /publish-records
```

### Research sources and the scraper fallback

`research_agent_use_case.ALLOWED_SOURCE_DOMAINS` is the source allowlist per
`specs/research-agent/spec.md`: `war.gov`, `cia.gov`, `archives.gov`,
`aaro.mil`, `odni.gov`, `theblackvault.com` (locator only — the research
agent doesn't verify it resolves back to the original agency; that's a
manual/future check). Any URL outside this list is discarded before ever
being fetched.

Scraping goes through `ISourceScraper` (design.md Decision 7): `JinaScraperAdapter`
is the default (cheap, returns raw text/markdown, so `extraction_confidence`
is always `"baja"`); `FirecrawlScraperAdapter` is the fallback used only when
Jina returns nothing (protected/complex pages), doing AI-structured
extraction (`extraction_confidence = "alta"`). Swap or add an implementation
by writing a new class satisfying `ISourceScraper` — nothing else changes.
Configure via `.env`: `JINA_API_KEY`, `FIRECRAWL_API_KEY` (both optional;
Firecrawl is skipped entirely if unset).

**Scope note**: `ResearchAgentUseCase.discover()` processes a list of
candidate URLs the caller supplies — it does not itself crawl a source's
listing pages to find new links. Autonomous link discovery is a larger
scraping project not yet built.

### Case-curation scoring rubric

`CaseCurationUseCase` asks the LLM to score a document 1-5 on each of
`novedad`, `potencial_narrativo`, `respaldo_documental`, `elemento_visual`,
`encaje_audiencia` (per `specs/case-curation/spec.md`), sums them
(`CurationScore.total`, max 25), and advances only at
`ADVANCEMENT_THRESHOLD = 15` or above — a case scoring lower is discarded.
Every evaluated case (advanced or discarded) is recorded in
`casos_cubiertos.md` with its score, so it's never re-scored; an advanced
case must also carry a non-empty `narrative_angle` or the use case raises
`CurationError` rather than silently advancing an unjustified case.

Orchestration lives in two deliberately separate places:

- `orchestrator_agents.py` — the `deepagents`/LangGraph wiring (`writer_agent`,
  `platform_adapter_agent` as subagents, each a thin tool wrapping the
  matching Phase 2 use case). This is where an LLM's judgment calls
  (which angle to pursue, how to phrase a hook) belong.
- `orchestrator.py` — `run_cycle`, the deterministic bookkeeping: checks a
  document is ready to write from (real agency, real doc type, enough
  extracted text — otherwise discard and record why, never invent
  details), delegates to the use cases, persists the result as
  `pending_review`, and updates `casos_cubiertos.md`. This does not need
  the LLM in the loop and must behave identically every run.

### Publishing and the publisher swap mechanism

Publishing goes through `ISocialPublisher` (design.md Decision 7):
`PostizPublisherAdapter` is the default (self-hosted Postiz, raw HTTP).
Swap it for Ayrshare, Blotato, or anything else by writing a new class
satisfying `ISocialPublisher` (`publish(platform, content, scheduled_at) ->
PublishResult`) and pointing `dependencies.get_publisher()` at it — nothing
in `PublishingUseCase` or the approval flow changes. Configure via `.env`:
`POSTIZ_API_KEY`, `POSTIZ_BASE_URL` (defaults to `http://localhost:5000`,
i.e. a local self-hosted instance).

`PublishingUseCase.publish()` is only ever reachable through
`approval_gate.run_if_approved` — it makes exactly one publish attempt per
call and never retries automatically; a failure leaves the
`PlatformVersion` in `FAILED`, which the approval gate then refuses to act
on again without a fresh, explicit approval (see
`specs/publishing/spec.md`, "report failures without silent repeated
retries"). Scheduling reads an `optimal_time:<platform>=HH:MM` line from
`calendario.md`; if none exists for the platform, it proposes
`DEFAULT_PROPOSED_TIME` (`12:00`) as a new line and does **not** publish —
per spec, publishing immediately without a defined time is not allowed.

### Running the editorial API locally

```bash
source venv/bin/activate
uvicorn src.editorial.presentation.app:app --reload

# Apply the editorial schema first (note: must be `python3 -m alembic`, not
# bare `alembic` — the latter doesn't have the project root on sys.path and
# fails importing the models from env.py):
python3 -m alembic upgrade head
```

- `GET /health` — confirms the service is up.
- `POST /platform-versions/{id}/approve` / `POST /platform-versions/{id}/reject`
  — the human-approval gate: a `PlatformVersion` starts `pending_review` and
  stays there until one of these is called; nothing is allowed to act on it
  until its status is `approved` (enforced by `approval_gate.run_if_approved`,
  not by convention). An already-decided item returns `409`; an unknown id
  returns `404`. **Approving no longer triggers publishing** (changed by
  `enhance-admin-panel-ui` — see below); it only records the decision.
- `POST /platform-versions/{id}/publish` — the explicit publish action
  (`enhance-admin-panel-ui`, replacing the old approve-triggers-publish
  behavior): invokes `PublishingUseCase` for one `approved` platform
  version, gated by `approval_gate.run_if_approved`. Returns the outcome
  fields (`published`, `external_post_id`, `error_message`,
  `proposed_time`) flat in the response body. `404` on an unknown id;
  `409` if the platform version isn't `approved` yet. Invokable
  individually per platform version, or looped by the frontend for a bulk
  "publish this network for every selected approved case" action — there
  is no dedicated bulk endpoint (see design.md Decision 2).
- `POST /research/run` — the manual trigger for a research+curation pass
  (design.md defers autonomous daily/cron scheduling as a Non-Goal; call
  this yourself when you want a new cycle, or use the admin panel's
  "Ejecutar pipeline" button). Body: `{"source_urls": [...]}` (at least one
  required). Runs discover → curate → write → adapt → persist for every URL
  that clears the allowlist, dedup, and curation threshold, and returns the
  same summary shape as `run_cycle`.
- `GET /research/sources` / `POST /research/sources` (body `{"url": ...}`) /
  `POST /research/sources/delete` (body `{"url": ...}`) — list, add, and
  remove the operator-configured source-URL list the admin panel's
  Configuración view manages and "Ejecutar pipeline" targets. Backed by a
  new `fuentes.md` memory file (one URL per line); adding a duplicate is a
  no-op.
- `GET /publish-records` — lists every publish attempt (platform, status,
  external post id, scheduled/published timestamps, error message) — the
  read model the admin panel's calendar view consumes.
- `GET /chapters/pending` — every chapter with at least one non-terminal
  (`pending_review` or `approved`) platform version, with full context
  (source document, story summary, script, all platform versions) — the
  read model behind the admin panel's Pipeline feed. A chapter drops out
  only once every platform version reaches a terminal state (`published`,
  `failed`, or `rejected`).

### Running the manual story + platform-adaptation CLI

Until Phase 4 (`research-agent`/`case-curation`) automates document discovery
and scoring, you can manually point the editorial service's writer/adapter at
any document already processed by the ingestion pipeline (i.e. already in
`data/knowledge_base/expedientes.sqlite`):

```bash
source venv/bin/activate
export ANTHROPIC_API_KEY=sk-ant-api03-...   # or set it in .env

python -m src.editorial.application.manual_curation_cli \
  --doc-id <the ingestion pipeline's document id> \
  --doc-type report \
  --narrative-angle "military witness + radar corroboration, classified 40 years"
```

This prints the generated story summary, each chapter's script and source
citation, and a short summary of its four platform adaptations, for manual
review. It does not persist anything (it's a read-only preview tool); to
actually persist a story as pending-review rows and go through the approval
gate, use `orchestrator.run_cycle` with a real, already-persisted `Document`.

### Running the editorial database migrations

```bash
# Must be `python3 -m alembic`, not bare `alembic` — the latter doesn't
# have the project root on sys.path and fails importing the models.
python3 -m alembic upgrade head    # create the editorial schema
python3 -m alembic downgrade base  # revert it
```

## Editorial Admin Panel (`frontend/` — Next.js)

An internal, single-operator UI with a dark "declassified case file" visual
identity (`enhance-admin-panel-ui`): a **Pipeline** feed (`/`, the default
route) for reviewing/approving/publishing cases and triggering pipeline
runs, the editorial **Calendario** (`/calendar`), **Casos cubiertos**
(`/cases`), and **Configuración** (`/settings`) for managing the source-URL
list. See `docs/frontend-standards.md` for the full architecture and
standards; this section is the local-dev walkthrough.

### Running it locally against the backend

```bash
# 1. Backend: apply migrations and start the API (from the project root)
source venv/bin/activate
python3 -m alembic upgrade head
uvicorn src.editorial.presentation.app:app --reload   # http://localhost:8000

# 2. Frontend: configure and start the dev server (in a second terminal)
cd frontend
npm install
cp .env.local.example .env.local   # set ADMIN_PANEL_TOKEN to any value
npm run dev                         # http://localhost:3000
```

Open `http://localhost:3000`, you'll be redirected to `/login` — enter the
`ADMIN_PANEL_TOKEN` value from `.env.local`.

### Running the frontend's own tests

```bash
cd frontend
npm test          # Jest unit tests (components, mocked API)
npm run test:e2e  # Playwright E2E — needs both servers running (above)
                   # AND seeded data: a pending chapter, an
                   # optimal_time:<platform>=HH:MM line in calendario.md,
                   # and a couple of casos_cubiertos.md entries. See
                   # docs/frontend-standards.md's Testing Standards for
                   # the exact seed shape the two specs assume.
```

### CORS

The backend allows `http://localhost:3000` via `CORSMiddleware`
(`src/editorial/presentation/app.py`) — without it, every browser request
from the frontend to the API fails outright. If you run the frontend on a
different port/host, add it to `allow_origins` there.

