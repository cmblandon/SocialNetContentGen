# Development Guide

Step-by-step setup and workflow for this project: the local ingestion
pipeline ("Proyecto Expediente") and the editorial service being built on
top of it (`archivo-desclasificado-pipeline` OpenSpec change). There is no
Docker, no PostgreSQL, and no frontend yet — this guide only documents what
actually exists or is in active development; see
`openspec/changes/archivo-desclasificado-pipeline/` for what's planned but
not yet built.

## Prerequisites

- **Python** 3.10+
- **Apple Silicon Mac** (for the local MLX model server used by the
  ingestion pipeline — this dependency is Apple-Silicon-specific)
- **Homebrew** (for OCR system tools, only if you'll process scanned PDFs)
- **Git**

```bash
python3 --version
git --version
```

## 1. Clone and Set Up the Environment

```bash
git clone <repo-url>
cd SocialNetContentGen

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` covers both bounded contexts: the ingestion pipeline
(`mlx-lm`, `markitdown`, `pypdf`, `chromadb`, `sentence-transformers`,
`pydantic-settings`), the editorial service (`fastapi`, `uvicorn`,
`sqlalchemy`, `alembic`, `httpx`), and testing (`pytest`, `pytest-mock`,
`pytest-cov`).

## 2. OCR System Tools (optional)

Only needed if you'll ingest scanned (image-only) PDFs:

```bash
brew install tesseract tesseract-lang ocrmypdf
```

## 3. Environment Configuration (`.env`)

Both contexts read configuration via `pydantic-settings`
(`src/config/settings.py`). Base paths (`data/`, `src/`) are auto-detected;
override anything else via a `.env` file at the project root (gitignored):

```env
# Local model server (ingestion pipeline)
LOCAL_LLM_URL=http://localhost:8080/v1/chat/completions

# Cloud API keys (editorial service — add keys as their phase is built)
ANTHROPIC_API_KEY=sk-ant-api03-...
ELEVENLABS_API_KEY=...
```

## 4. Ingestion Pipeline

Start the local model server (leave running in its own terminal):

```bash
mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
# Slower Mac? Use: mlx-community/Llama-3.2-3B-Instruct-4bit
```

Then, from the project root, with the venv active:

```bash
cp ~/Downloads/some_document.pdf data/docs_raw/
python -m src.main
```

Verify results:

```bash
sqlite3 data/knowledge_base/expedientes.sqlite \
  "SELECT id, archivo_origen, confiabilidad_extraccion FROM documentos;"
```

## 5. Editorial Service

Apply migrations, then run the API:

```bash
alembic upgrade head
uvicorn src.editorial.presentation.app:app --reload
```

- API root: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- Health check: `curl http://localhost:8000/health`

Revert the schema if needed:

```bash
alembic downgrade base
```

Only `/health` exists as of Phase 1 — see
`openspec/changes/archivo-desclasificado-pipeline/tasks.md` for what each
later phase adds (approval endpoints, research trigger, publish records,
cases).

## 6. Frontend (planned, not yet implemented)

The admin panel (Next.js) is Phase 6 of the OpenSpec change — see
`docs/frontend-standards.md`. This section will be filled in once
`frontend/` exists.

## 7. Testing

```bash
# Full suite
pytest

# One module
pytest tests/unit/test_editorial_models.py -v

# With coverage report (no threshold is enforced in pytest.ini yet)
pytest --cov=src tests/ --cov-report=html
open htmlcov/index.html
```

Conventions: see `docs/backend-standards.md` (flat `tests/unit/`, TDD
red/green pairing per OpenSpec task, in-memory/temp DBs only in tests).

## 8. Development Workflow

1. Create a feature branch per OpenSpec change:
   ```bash
   git checkout -b feature/<change-name>
   ```
2. Follow the change's `tasks.md`, TDD-first (failing test, then
   implementation) — see `docs/openspec-tasks-mandatory-steps.md` for the
   mandatory step structure (branch first, test/DB verification report,
   curl testing for new endpoints, Playwright E2E once a frontend exists).
3. Run tests and confirm they pass before marking a task complete.
4. Commit with clear, English, imperative-mood messages.

```bash
pytest
mypy src/          # if/when a mypy config is added — not yet configured
ruff check src/    # if/when a ruff config is added — not yet configured
```

## Troubleshooting

**`mlx_lm.server` not running / ingestion hangs or times out**
```bash
# Confirm the server is up in its own terminal
curl http://localhost:8080/v1/models
```

**OCR fails (`ocrmypdf`/`tesseract` not found)**
```bash
brew install tesseract tesseract-lang ocrmypdf
```

**`alembic upgrade head` fails**
```bash
alembic current             # check current revision
alembic history              # see the revision chain
# If the editorial DB is in a bad local state during development (never do
# this against data you care about):
rm data/knowledge_base/editorial.sqlite
alembic upgrade head
```

**Port 8000 already in use**
```bash
lsof -i :8000
kill -9 <PID>
# or
uvicorn src.editorial.presentation.app:app --reload --port 8001
```

**Import errors when running pytest**
```bash
# Run from the project root so `src` resolves; or:
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

## Useful Resources

- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/en/20/
- Alembic: https://alembic.sqlalchemy.org/
- pytest: https://docs.pytest.org/
- MLX: https://github.com/ml-explore/mlx-examples
