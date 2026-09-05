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
│   └── ports.py            # ISourceScraper, ISocialPublisher, ILLMClient (Protocols)
├── application/             # Use cases (story-writing, platform-adaptation, ...)
├── infrastructure/
│   └── persistence/
│       ├── models.py        # SQLAlchemy models: Document, Story, Chapter,
│       │                    # PlatformVersion, PublishRecord
│       └── migrations/      # Alembic environment + revisions
└── presentation/
    └── app.py                # FastAPI composition root (routers added per phase)
```

### Running the editorial API locally

```bash
source venv/bin/activate
uvicorn src.editorial.presentation.app:app --reload
```

- `GET /health` — confirms the service is up.

### Running the editorial database migrations

```bash
alembic upgrade head    # create the editorial schema
alembic downgrade base  # revert it
```

