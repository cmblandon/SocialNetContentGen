## Why

The **Proyecto Expediente** pipeline currently has zero automated tests. The core domain logic (PDF text extraction, OCR orchestration, LLM integration) is critical infrastructure that needs reliable test coverage before production deployment. Without tests:

- Changes to the ingestion pipeline risk breaking undocumented behaviors
- Integration of new adapters (PostgreSQL, Pinecone, cloud LLMs) requires manual verification
- Code refactoring becomes risky due to lack of regression safety
- Onboarding new developers slows down without a test baseline

This change establishes comprehensive unit tests following the project's Domain-Driven Design layered architecture, enabling confident iteration on the ingestion pipeline.

## What Changes

### Added Capabilities
- Unit testing infrastructure with pytest fixtures for mocking external dependencies
- Test coverage across all port/interface implementations (IPdfInspector, IOcrProcessor, ILLMClient, IDocumentRepository, ISemanticIndex)
- Pure function tests for domain logic isolated from I/O operations
- Parameterized tests for chunking algorithm with various input sizes
- Exception handling tests for boundary conditions and error scenarios

### New Files
- `tests/conftest.py` - pytest configuration and shared fixtures
- `tests/__init__.py` - Python package marker for tests directory
- `tests/unit/test_chunking.py` - Tests for the text chunking algorithm
- `tests/unit/test_pdf_reader.py` - Tests for PDF text detection and OCR processing
- `tests/unit/test_sqlite_repo.py` - Tests for SQLite document repository
- `tests/unit/test_chroma_repo.py` - Tests for ChromaDB semantic indexing (mocked)
- `tests/unit/test_local_llm_client.py` - Tests for local LLM client (mocked)
- `tests/unit/test_ingest_use_case.py` - Tests for the main ingestion use case
- `tests/__init__.py` - Test package marker

### Dependencies
- **pytest>=8.0.0** - Test framework (new)
- **pytest-mock>=3.14.0** - Mocking library for dependency injection testing (new)
- **pytest-cov>=5.0.0** - Test coverage reporting (new)

## Capabilities

### New Capabilities
- **chunking**: Text chunking algorithm with overlap handling and edge cases
- **pdf_reader**: PDF text detection heuristics and OCR processor implementation
- **sqlite_repo**: SQLite document repository CRUD operations and validation
- **chroma_repo**: ChromaDB semantic indexing (interface tests)
- **local_llm_client**: LLM client integration (unit tests for HTTP client logic only)
- **ingest_use_case**: Complete ingestion pipeline orchestration with mocked dependencies

### Modified Capabilities
None - This is a new testing capability, not modifying existing requirement specifications.

## Impact

**Code Under Test:**
- `src/application/chunking.py` - Pure function testable in isolation (100% coverage target)
- `src/infrastructure/pdf/pdf_reader.py` - PDF inspection and OCR processing (85% coverage target)
- `src/infrastructure/persistence/sqlite_repo.py` - SQLite repository implementation (95% coverage target)
- `src/application/ingest_use_case.py` - Use case orchestration with dependency injection (70% coverage target, external deps mocked)

**Infrastructure Impact:**
- Adds test dependencies to requirements.txt
- Creates comprehensive test suite in tests/unit/ directory
- Establishes pytest configuration for the project
- Sets foundation for future integration and end-to-end tests

**No Breaking Changes:**
This is purely additive - no existing functionality is modified or removed. All existing code remains unchanged; only testing infrastructure is added.
