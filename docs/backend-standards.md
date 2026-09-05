---
description: Backend development standards for this project's two Python bounded contexts (ingestion pipeline and editorial service) — architecture, ports/adapters, database patterns, testing, and security conventions actually in use here.
globs: ["src/**/*.py", "tests/**/*.py", "alembic.ini", "pytest.ini", "requirements.txt"]
alwaysApply: true
---

# Backend Project Standards and Best Practices (Python)

## Overview

This backend is two independent bounded contexts sharing one Python codebase
and one `venv`:

1. **Ingestion pipeline** (`src/core`, `src/application`, `src/infrastructure`,
   `src/config`) — turns raw PDFs into structured `FichaEstructurada` records,
   100% local (local MLX model, SQLite, ChromaDB). See the root `README.md`
   for its data flow.
2. **Editorial service** (`src/editorial/`) — the
   `archivo-desclasificado-pipeline` OpenSpec change
   (`openspec/changes/archivo-desclasificado-pipeline/`). Turns curated
   documents into narrative stories, adapts them per social platform, and
   publishes them behind a mandatory human-approval gate, exposed over
   FastAPI. See `docs/data-model.md` for its schema.

Both follow the same architectural style (below); neither uses PostgreSQL,
Prisma, or a `domain/`-named layer — those belonged to a different,
unrelated template and have been removed from this document.

## Technology Stack

- **Python 3.10+**, fully typed (PEP 484)
- **Ingestion pipeline**: `mlx-lm` (local model server), `markitdown` +
  `pypdf` (PDF text/OCR), `chromadb` + `sentence-transformers` (local vector
  store), `pydantic-settings` (config)
- **Editorial service**: `fastapi` + `uvicorn` (HTTP), `sqlalchemy>=2.0`
  (declarative `Mapped`/`mapped_column` style) + `alembic` (migrations),
  `httpx` (outbound calls to scrapers/publishers, and required by FastAPI's
  `TestClient`)
- **Database**: SQLite for both contexts, in separate files under
  `data/knowledge_base/` (not committed — see `.gitignore`). No PostgreSQL/
  Docker dependency exists or is planned for the current phases (see
  design.md Decision 4 — this may be revisited if concurrent-write needs
  emerge).
- **Testing**: `pytest`, `pytest-mock`, `pytest-cov` (coverage reporting is
  available; no coverage threshold is currently enforced in `pytest.ini`)

## Architecture: Clean/Hexagonal, not domain/application/presentation/infrastructure

Both bounded contexts use the same four layers, but named to match what's
actually in this repo — don't introduce a `domain/` folder, this project uses
`core/`:

```
src/<context>/
├── core/            # Entities (dataclasses) + ports (typing.Protocol)
│                    # No dependency on infrastructure or external libraries.
├── application/     # Use cases — orchestrate ports to implement a workflow.
├── infrastructure/  # Concrete adapters implementing core's ports:
│                    # persistence (SQLAlchemy/SQLite), LLM clients, PDF/OCR,
│                    # scrapers, publishers.
└── presentation/    # FastAPI routes (editorial service only — the
                     # ingestion pipeline has no HTTP surface, it's CLI-driven
                     # via src/main.py).
```

`src/config/settings.py` (ingestion) is shared, centralized `pydantic-settings`
configuration; the editorial service does not yet have its own settings
module — add one there if editorial-specific env vars are needed (e.g. the
Postiz/Firecrawl/Jina API keys from Phase 4-5).

### Ports: `typing.Protocol`, not `abc.ABC`

This codebase uses structural typing for all ports, not abstract base
classes. Adapters do not need to inherit from anything:

```python
# src/editorial/core/ports.py
from typing import Optional, Protocol, runtime_checkable

@runtime_checkable
class ISourceScraper(Protocol):
    def fetch(self, source_url: str) -> Optional["ScrapedDocument"]:
        ...
```

Mark a port `@runtime_checkable` only when a test needs `isinstance()`
conformance checking (see `tests/unit/test_editorial_ports.py`); it isn't
required for ports only ever consumed via type hints.

### Entities: plain dataclasses

Core entities are `@dataclass`, not Pydantic models and not ORM models —
see `src/core/entities.py`'s `FichaEstructurada`. Pydantic is reserved for
FastAPI request/response validation; SQLAlchemy models are reserved for
persistence (`src/editorial/infrastructure/persistence/models.py`). Don't
collapse these three concerns into one class.

## Coding Standards

- **Naming**: snake_case for functions/variables, PascalCase for classes,
  UPPER_SNAKE_CASE for constants — same as any standard Python project.
- **Language**: all code, comments, docstrings, and identifiers in English
  (per CLAUDE.md Section 2), even where a data field's real-world content is
  Spanish (e.g. a document's `resumen_ejecutivo` text itself).
- **Type hints**: mandatory on every function signature, including return
  types. Use `Optional[T]` for nullable values.
- **Docstrings**: used on classes and non-obvious methods to explain intent
  or a constraint the reader can't infer from the signature (see
  `src/editorial/infrastructure/persistence/models.py` for the current
  style) — not on every trivial getter.

## Testing Standards

- **Location**: flat `tests/unit/` (not mirrored into subdirectories),
  named `test_<module_or_feature>.py`.
- **Style**: plain `test_*` functions are the default; nested `Test*`
  classes are acceptable when grouping many scenarios for one component
  (see `tests/unit/test_pdf_reader.py`) — either is fine, pick whichever
  reads clearer for the case at hand.
- **Fixtures**: shared fixtures (mocked ports, temp paths) live in
  `tests/conftest.py`; test-local fixtures live in the test file itself.
- **Mocking**: `unittest.mock.Mock(spec=ITheProtocol)` or `pytest-mock`'s
  `mocker` fixture for dependency substitution — see `tests/conftest.py`.
- **TDD**: every OpenSpec change's `tasks.md` pairs a "write failing test"
  task with a "make it pass" task — write the test first, confirm it fails
  for the expected reason, then implement.
- **In-memory/temp databases only**: SQLAlchemy tests use
  `sqlite:///:memory:`; Alembic migration tests use a `tmp_path`-scoped
  file. Never point a test at `data/knowledge_base/*.sqlite`.

## Database Patterns (editorial service)

- **Declarative models**: SQLAlchemy 2.0 `DeclarativeBase` +
  `Mapped[...]`/`mapped_column(...)`, not the legacy `Column(...)` style.
- **Enums**: `sa.Enum(..., native_enum=False)` for portability — SQLite has
  no native enum type, and this avoids a footgun if the DB ever moves to
  PostgreSQL (native enums can't be silently redefined across tables).
- **Migrations**: one Alembic environment per context that has a database
  (currently just the editorial service — `alembic.ini` at the repo root,
  `script_location = src/editorial/infrastructure/persistence/migrations`).
  Every schema change ships as a new revision with both `upgrade()` and a
  working `downgrade()`.
- **Cascade deletes**: relationships that own their children use
  `cascade="all, delete-orphan"` (e.g. deleting a `Document` removes its
  `Story`/`Chapter`/`PlatformVersion`/`PublishRecord` chain) — see
  `docs/data-model.md`.

## API Design Standards (editorial service)

- **FastAPI app**: composition root at `src/editorial/presentation/app.py`;
  register new routers there as phases add them (approval endpoints in
  Phase 3, research trigger in Phase 4, publish-records in Phase 5, cases in
  Phase 6 — see `openspec/changes/archivo-desclasificado-pipeline/tasks.md`).
- **Status codes**: use FastAPI's defaults unless a spec requirement says
  otherwise (e.g. `specs/publishing/spec.md` requiring specific
  approve/reject transitions).
- **Errors**: raise `fastapi.HTTPException` with a clear `detail`; don't let
  raw exceptions leak past a route handler.
- **No response envelope convention has been established yet** — decide it
  when the first real (non-`/health`) endpoint is built, and document the
  choice here.

## Security Best Practices

- **Secrets**: `.env` (gitignored), loaded via `pydantic-settings`. Never
  hardcode API keys — `anthropic_api_key` and `elevenlabs_api_key` are
  already declared (empty by default) in `src/config/settings.py`; add new
  keys (Firecrawl, Jina, Postiz/Ayrshare/Blotato) the same way when their
  phase starts.
- **Input validation**: Pydantic models for any FastAPI request body, once
  routes beyond `/health` exist.
- **Dependency injection**: use cases and adapters take their ports as
  constructor arguments — no global singletons, no module-level database
  sessions.

## Development Workflow

```bash
# Setup (once)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Ingestion pipeline
python -m src.main

# Editorial service
uvicorn src.editorial.presentation.app:app --reload
alembic upgrade head      # apply editorial schema migrations
alembic downgrade base    # revert them

# Testing
pytest                     # full suite
pytest tests/unit/test_editorial_models.py -v   # one module
pytest --cov=src tests/    # with coverage report (no gate enforced yet)
```

- **Branches**: `feature/<change-name>` per OpenSpec change (see
  `docs/openspec-tasks-mandatory-steps.md`, Step 0).
- **Commits**: descriptive, English, imperative mood.
- **OpenSpec discipline**: a fix/change requested mid-implementation updates
  the change's `proposal.md`/`specs/`/`tasks.md` first — see CLAUDE.md
  Section 7. Don't patch code without updating the artifact that specified it.
