# Test Suite - Proyecto Expediente

This directory contains the automated test suite for the Proyecto Expediente ingestion pipeline.

## Structure

The tests are organized by layer to match the Domain-Driven Design (DDD) architecture of the project:

- `tests/unit/`: Unit tests for individual components.
    - `test_chunking.py`: Tests for the pure text chunking algorithm.
    - `test_pdf_reader.py`: Tests for PDF inspection and OCR orchestration.
    - `test_sqlite_repo.py`: Tests for the SQLite persistence adapter.
    - `test_chroma_repo.py`: Tests for the ChromaDB semantic index adapter.
    - `test_local_llm_client.py`: Tests for the local LLM client communication and fusion logic.
    - `test_ingest_use_case.py`: Integration tests for the main ingestion use case orchestration.

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
