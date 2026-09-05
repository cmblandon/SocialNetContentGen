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
│   └── manual_curation_cli.py           # Phase 2 manual entrypoint (see below)
├── infrastructure/
│   ├── llm/
│   │   └── anthropic_llm_client.py      # Cloud ILLMClient implementation
│   └── persistence/
│       ├── models.py        # SQLAlchemy models: Document, Story, Chapter,
│       │                    # PlatformVersion, PublishRecord
│       ├── ficha_reader.py   # Read-only access to the ingestion pipeline's SQLite
│       ├── project_memory.py # ProjectMemoryStore: casos_cubiertos.md, calendario.md, manual_de_marca.md
│       ├── session.py        # SQLAlchemy session factory for editorial.sqlite
│       └── migrations/      # Alembic environment + revisions
└── presentation/
    ├── app.py                # FastAPI composition root (routers added per phase)
    └── routers/
        └── approval.py       # POST /platform-versions/{id}/approve|reject
```

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
  — the Phase 3 stand-in for the real admin panel (Phase 6). This is the
  human-approval gate: a `PlatformVersion` starts `pending_review` and stays
  there until one of these is called; nothing (no future publisher) is
  allowed to act on it until its status is `approved` (enforced by
  `approval_gate.run_if_approved`, not by convention). An already-decided
  item returns `409`; an unknown id returns `404`.

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
alembic upgrade head    # create the editorial schema
alembic downgrade base  # revert it
```

