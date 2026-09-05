## Context

Proyecto Expediente is a local PDF ingestion pipeline that transforms scanned documents into structured JSON records using an on-device LLM. The system follows Domain-Driven Design layered architecture with strict separation of concerns: `core` domain layer depends only on interfaces (ports), while `infrastructure` adapters implement those interfaces. Currently, the entire codebase has zero test coverage, making it risky to introduce external dependencies or refactor components without understanding undocumented behaviors.

This design document outlines how to establish comprehensive unit testing infrastructure that respects the layered architecture and enables independent testing of each component while mocking cross-layer dependencies.

## Goals / Non-Goals

**Goals:**
- Establish pytest as the test framework with proper configuration and fixtures
- Create unit tests for all pure functions (`chunking.py`) in isolation
- Mock external I/O dependencies (LLM HTTP client, ChromaDB, PDF libraries) to enable deterministic testing
- Implement parameterized tests for algorithms that need edge case coverage
- Achieve meaningful code coverage (>70% across all testable components)
- Follow the existing DDD architecture by testing ports/interfaces and their adapters separately

**Non-Goals:**
- Integration tests for live LLM calls or external databases (these come in integration test phase)
- E2E tests with real PDF processing end-to-end (reserved for e2e phase)
- Testing infrastructure dependencies themselves (pytest, chromadb, sentence-transformers)
- Test coverage reporting during CI/CD (that comes later, post-implementation)

## Decisions

### 1. Test Framework: pytest
**Decision:** Use pytest as the test framework exclusively.
**Rationale:** The project's existing OpenSpec configuration already specifies pytest>=8.0.0 as a dev dependency. No learning curve for Python developers. Rich ecosystem of plugins (mock, cov) without configuration overhead.

### 2. Testing Strategy: Isolation through Mocking
**Decision:** All tests that involve the application layer (`core/` and `application/`) will mock infrastructure dependencies using pytest-mock. This follows the open-closed principle by keeping core domain logic independent from volatile infrastructure implementations.
**Why not alternatives?**
- **Integration tests would be slow:** LLM calls to mlx_lm server are asynchronous and network-bound; ChromaDB requires embedding model loading (CPU/GPU startup). Would add 5-30s per test suite.
- **Direct import of adapters:** While possible, this couples tests to specific implementations. If we later add PostgreSQL repository or Cloud LLM client, all existing tests would need updating.
- **pytest-mock enables structural duck typing verification:** Our ports are defined with `typing.Protocol` (structural typing). Mocks verify contracts are honored without inheritance requirements.

### 3. Fixture Organization Pattern: Module-level Shared Fixtures
**Decision:** Create a `conftest.py` at the tests/ root with shared fixtures and individual test files import selectively.
**Rationale:** This is the pytest convention for shared resources. The conftest pattern automatically imports fixtures into all tests below it, avoiding repetitive fixture definitions while keeping test files self-contained.

### 4. Pure Function Testing: No Mocking Needed
**Decision:** `chunking.py` gets direct unit tests without mocking since it has zero dependencies.
**Why:** This is a pure transformation function that takes text and returns chunked strings. It's the only component with 100% testability. We should achieve 100% branch coverage here before testing dependent components.

### 5. Repository Adapter Testing: Mocked Interfaces
**Decision:** SQLite and ChromaDB adapters are tested against their respective interface contracts (IDocumentRepository, ISemanticIndex), not direct imports.
**Pattern for repository tests:**
```python
from src.core.ports import IDocumentRepository
from unittest.mock import Mock

# Mock the repository without importing sqlite_repo.py
mock_repo = Mock(spec=IDocumentRepository)  # Validates interface compliance
```
**Why this matters:** If we add PostgreSQL or MySQL adapters later, existing tests automatically validate new implementations without modification.

### 6. LLM Client Testing: Stubbed Depurar Method
**Decision:** `LocalLLMClient.depurar()` is too complex for direct testing (network calls, JSON parsing, chunk fusion). We test it by mocking the method's return value rather than implementing a real stub.
```python
from unittest.mock import patch

with patch('src.application.ingest_use_case.LocalLLMClient.depurar') as mock_depurar:
    # Test uses pre-defined mock return values, no actual HTTP calls
    pass
```
**Alternative considered:** Create `FakeLLMClient` that implements ILLMClient entirely in-memory. Rejected because it duplicates the business logic we're testing and creates circular dependencies.

### 7. Parameterized Chunking Tests: pytest-parametrize Matrix
**Decision:** Use `@pytest.mark.parametrize` to exercise chunking algorithm across multiple input sizes and boundary conditions.
**Test matrix:**
- Short text (< 3000 chars): Single chunk path, verify no overlap applied
- Medium (3000-6000): Single chunk threshold boundary
- Long (6000+): Multi-chunk path, verify overlap calculation
- Empty string: Edge case validation
- Unicode-heavy text: Verify no encoding issues with Spanish document content

### 8. Exception Boundary Testing: Error Scenarios
**Decision:** Each component that can fail is tested for its documented error paths using pytest.raises.
**Examples to cover:**
- PDF without extractable text → PdfTextInspector.tiene_texto_real() returns False
- ChromaDB indexing failures → ISemanticIndex.indexar() throws exception
- LLM connection timeout → LocalLLMClient.depurar() propagates ConnectionError

### 9. Mocking Strategy for IngestUseCase: Dependency Injection Testing
**Decision:** Test the use case by providing real IPdfInspector and IOcrProcessor implementations, but mocking ILLMClient as a dependency injection test instead of an implementation stub.
```python
from src.core.ports import IDocumentRepository
from unittest.mock import Mock

def test_ingest_use_case_with_mocked_llm(mock_pdf_inspector, mock_ocr_processor, mocker):
    mock_llm = mocker.Mock(spec=ILLMClient)  # Validates contract
    use_case = IngestUseCase(
        pdf_inspector=mock_pdf_inspector,
        ocr_processor=mock_ocr_processor,
        llm_client=mock_llm,  # Injected mock
        document_repo=document_repo,
        semantic_index=chroma_repo,
    )
    # Verify use case orchestrates correctly with mocked dependencies
```

### 10. Test File Organization: Unit Tests Grouping
**Decision:** Organize test files by module/layer for easy navigation and maintenance:
- `tests/unit/test_chunking.py` - Chunking algorithm
- `tests/unit/test_pdf_reader.py` - PDF inspection and OCR (infrastructure adapter)
- `tests/unit/test_sqlite_repo.py` - SQLite repository adapter
- `tests/unit/test_chroma_repo.py` - ChromaDB adapter (mocked tests only)
- `tests/unit/test_local_llm_client.py` - LLM client unit tests (stubbed depurar)
- `tests/unit/test_ingest_use_case.py` - Use case orchestration

### 11. Dependency Injection in Tests: Conftest Fixtures Pattern
**Decision:** Use pytest fixtures for creating and injecting dependencies rather than inline setup code.
**Benefits:**
- DRY: Shared fixture for mock PDF inspector reused across all tests needing PDF inspection behavior
- Explicit dependencies: Test functions clearly show what they need via `@pytest.fixture` annotations
- Fast setup/teardown: Fixtures are created only when used, not on every test import

### 12. No Coverage Reporting Yet
**Decision:** We do NOT add pytest-cov or upload coverage to CI during implementation.
**Rationale:** This adds noise and false positives (coverage tools don't understand mocking). We will add coverage reporting in a future change once tests are stable.

## Risks / Trade-offs

### Risk 1: Mocked tests don't catch implementation bugs in adapters
**Mitigation:** While mocked tests validate interface compliance, they won't catch adapter-specific bugs (e.g., ChromaDB client initialization issues). Solution: Add integration tests later that actually instantiate real adapters.

### Risk 2: PDF mocking is complex due to binary format
**Mitigation:** Use `BytesIO` with sample PDF bytes or pytest-mock library's `mocker.do_mock()` to create realistic mock objects. Document the mock implementation details in test docstrings for transparency.

### Risk 3: LLM client tests become brittle if prompt template changes
**Mitigation:** Mock only the `.depurar()` method call, never the internal `_prompt_template` string. Tests verify contract satisfaction, not implementation details of how prompts are constructed.

### Risk 4: SQLite testing doesn't cover concurrency scenarios
**Mitigation:** Unit tests alone cannot verify concurrent access patterns. This is acknowledged as an integration test responsibility, documented for future phase.

## Migration Plan

### Phase 1: Test Infrastructure Setup (Current Implementation)
1. Add pytest and related dev dependencies to requirements-dev.txt or pip freeze output
2. Create `conftest.py` with base fixtures (mock implementations of core ports)
3. Verify existing pipeline still passes all new tests without errors

### Phase 2: Pure Function Tests
1. Test `dividir_en_chunks()` in isolation — no mocking required
2. Achieve 100% branch coverage on pure transformation logic
3. Commit as stable baseline for regression testing

### Phase 3: Adapter Layer Tests (in dependency order)
1. SQLite repository tests — simplest adapter, first to be mocked
2. ChromaDB indexing tests — mocks ISemanticIndex interface contract
3. PDF reader tests — most complex mocks but only I/O-dependent component

### Phase 4: Application Layer Tests
1. IngestUseCase orchestration with mocked dependencies
2. Chunking function dependency chain verification (ensure chunking results propagate correctly through use case)

### Rollback Strategy
If tests break existing functionality:
1. Keep `.gitignore` rules as-is — tests are additive, not modifying tracked files
2. Use `git diff` to identify which new test cases triggered failures
3. Remove problematic test scenarios while preserving infrastructure (conftest, fixtures)

**Note:** This is non-breaking because we're adding tests without changing any production code. Rollback would only involve deleting the entire tests/ directory if they somehow impact runtime behavior.

## Open Questions

1. **Test data PDF creation:** Should we maintain a small set of real PDF samples in `tests/data/` for realistic mocking, or generate synthetic PDF bytes? Decision pending — likely create a helper factory that generates minimal valid PDFs via an external library.

2. **Embedding model initialization:** ChromaDB's sentence-transformers model takes 2-5 minutes to download first time. For integration tests we'll mock this, but for future e2e phase should we use pytest-xdist parallelization or isolate embedding model tests entirely? Documented for next phase.

3. **Async vs sync test isolation:** Some mocked operations may be async (if LLM client returns coroutines). Should we add `pytest-asyncio` plugin now or defer to when async tests become necessary? Awaiting observation of actual test behavior.

4. **Fixture naming convention:** Use descriptive fixture names like `mock_pdf_inspector`, `mock_llm_client` following pytest naming conventions for auto-discovery, or prefix with project-specific tags? Following standard pytest fixture discovery (names starting with `mock_` for dependency injection mocks).
