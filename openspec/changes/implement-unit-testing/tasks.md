## 1. Test Infrastructure Setup

- [x] 1.1 Install pytest>=8.0.0, pytest-mock>=3.14.0, and pytest-cov>=5.0.0 dependencies
- [x] 1.2 Create tests/__init__.py to make tests directory a Python package
- [x] 1.3 Create tests/conftest.py with shared fixtures and mock implementations
- [x] 1.4 Configure pytest configuration (pytest.ini) with proper options

## 2. Pure Function Tests - Chunking Algorithm

- [x] 2.1 Implement test_dividir_en_chunks_short_text for documents under 6000 chars
- [x] 2.2 Implement test_dividir_en_chunks_boundary_exact for text exactly at 6000 chars threshold
- [x] 2.3 Implement test_dividir_en_chunks_crossing_one_boundary for 6100 char input
- [x] 2.4 Implement test_dividir_en_chunks_multiple_boundaries for very long documents
- [x] 2.5 Implement test_dividir_en_chunks_empty_string edge case handling

## 3. Repository Adapter Tests - SQLite

- [x] 3.1 Create mock repository fixture implementing IDocumentRepository interface contract
- [ ] 3.2 Implement test_guardar_creates_table if not exists on first insert
- [ ] 3.3 Implement test_guardar_all_fields_mapped correctly from FichaEstructurada
- [x] 3.4 Implement test_guardar_id_is_generated_hashbased for document ID generation
- [ ] 3.5 Implement test_guardar_timestamp_always_populated_utc for ingest timestamp

## 4. Repository Adapter Tests - ChromaDB

- [x] 4.1 Create mock chromadb repository using unittest.mock with ISemanticIndex specification
- [x] 4.2 Implement test_indexar_creates_collection if not exists
- [x] 4.3 Implement test_indexar_upserts_with_embedded_vector representation
- [x] 4.4 Implement test_indexar_includes_metadata from FichaEstructurada fields
- [x] 4.5 Implement test_indexar_skips_when_no_indexable_text present

## 5. LLM Client Unit Tests - Stubbed Implementation

- [x] 5.1 Create mock LLM client for dependency injection testing pattern
- [x] 5.2 Mock depurar method to return pre-defined FichaEstructurada instances
- [x] 5.3 Implement test_depurar_returns_structured_output from mocked results
- [x] 5.4 Verify chunk fusion logic when multiple chunks produce valid results

## 6. Integration Tests - Complete Pipeline

- [ ] 6.1 Create mock PDF inspector and OCR processor fixtures with realistic behavior
- [x] 6.2 Implement test_process_pdf_complete_happy_path for successful end-to-end flow
- [x] 6.3 Implement test_process_pdf_fails_when_pdf_has_no_text layer (returns False from inspector)
- [x] 6.4 Implement test_process_pdf_fails_when_llm_connection_times_out propagates exception
- [x] 6.5 Implement test_process_pdf_moves_original_to_processed_dir on successful completion

## 7. Documentation and Verification

- [x] 7.1 Create README for tests directory explaining test structure and running instructions
- [x] 7.2 Verify all tests pass with pytest -v (verbose mode)
- [x] 7.3 Validate no import errors or circular dependencies in test suite
