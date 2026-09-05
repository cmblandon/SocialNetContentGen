"""
Unit test suite for Proyecto Expediente PDF ingestion pipeline.

This package contains comprehensive unit tests following the Domain-Driven Design
layered architecture, testing each component in isolation by mocking external
dependencies (LLM clients, vector stores, PDF libraries).

Test Organization:
    tests/
    └── __init__.py              # Package marker
    └── conftest.py             # Shared fixtures and mocks
    └── unit/
        ├── test_chunking.py          # Text chunking algorithm (pure functions)
        ├── test_pdf_reader.py        # PDF inspection & OCR (mocked I/O)
        ├── test_sqlite_repo.py       # SQLite repository adapter
        ├── test_chroma_repo.py       # ChromaDB indexing (interface tests only)
        ├── test_local_llm_client.py  # LLM client stubbed tests
        └── test_ingest_use_case.py   # Complete pipeline integration
"""
