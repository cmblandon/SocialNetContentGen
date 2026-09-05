# Test Suite - Archivo Desclasificado

This directory contains the automated test suite for both bounded contexts
in this repo: the Proyecto Expediente ingestion pipeline and the editorial
service being built on top of it (`archivo-desclasificado-pipeline`
OpenSpec change).

## Structure

The tests are organized by layer to match the Clean/Hexagonal architecture
of the project (see `docs/backend-standards.md`):

- `tests/unit/`: Unit tests for individual components, flat (not mirrored
  into subdirectories).
  - **Ingestion pipeline** (`src/core`, `src/application`, `src/infrastructure`):
    - `test_chunking.py`: Tests for the pure text chunking algorithm.
    - `test_pdf_reader.py`: Tests for PDF inspection and OCR orchestration.
    - `test_sqlite_repo.py`: Tests for the SQLite persistence adapter.
    - `test_chroma_repo.py`: Tests for the ChromaDB semantic index adapter.
    - `test_local_llm_client.py`: Tests for the local LLM client communication and fusion logic.
    - `test_ingest_use_case.py`: Integration tests for the main ingestion use case orchestration.
  - **Editorial service** (`src/editorial`):
    - `test_editorial_models.py`: SQLAlchemy models — fields, relationships, cascade deletes, the approval-status lifecycle.
    - `test_editorial_migrations.py`: Alembic migration creates and reverts the schema cleanly.
    - `test_editorial_ports.py`: Structural (`isinstance`) conformance for `ISourceScraper`/`ISocialPublisher`/`ILLMClient`.
    - `test_editorial_app.py`: FastAPI route tests (starts with `/health`; grows per phase — see `openspec/changes/archivo-desclasificado-pipeline/tasks.md`).

- `tests/conftest.py`: Shared pytest fixtures and mock implementations of core ports.

## Running Tests

### Prerequisites
Ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

### Execute all tests
Run the full suite from the project root:
```bash
pytest
```

### Run specific tests
To run tests for a specific component:
```bash
pytest tests/unit/test_chunking.py
```

### Coverage Report
To generate a coverage report:
```bash
pytest --cov=src
```

## Testing Strategy

We use a **port-and-adapter** testing strategy:
1. **Pure Functions**: Tested in isolation without mocks.
2. **Adapters**: Tested against their `Protocol` interfaces. External I/O (databases, APIs) is mocked using `pytest-mock` to ensure fast, deterministic tests.
3. **Use Cases**: Tested by injecting mock adapters, verifying the orchestration logic and the flow of data between components.
