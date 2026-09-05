import pytest
from unittest.mock import Mock
from src.core.ports import (
    IPdfInspector,
    IOcrProcessor,
    ILLMClient,
    IDocumentRepository,
    ISemanticIndex,
    IDocumentTextLoader,
)

@pytest.fixture
def mock_pdf_inspector():
    """Fixture for IPdfInspector mock."""
    return Mock(spec=IPdfInspector)

@pytest.fixture
def mock_ocr_processor():
    """Fixture for IOcrProcessor mock."""
    return Mock(spec=IOcrProcessor)

@pytest.fixture
def mock_llm_client():
    """Fixture for ILLMClient mock."""
    return Mock(spec=ILLMClient)

@pytest.fixture
def mock_document_repository():
    """Fixture for IDocumentRepository mock."""
    return Mock(spec=IDocumentRepository)

@pytest.fixture
def mock_semantic_index():
    """Fixture for ISemanticIndex mock."""
    return Mock(spec=ISemanticIndex)

@pytest.fixture
def mock_document_text_loader():
    """Fixture for IDocumentTextLoader mock."""
    return Mock(spec=IDocumentTextLoader)

@pytest.fixture
def sample_pdf_path(tmp_path):
    """Provides a path to a dummy PDF file for testing."""
    pdf = tmp_path / "test_document.pdf"
    pdf.write_text("dummy pdf content")
    return pdf

@pytest.fixture
def sample_output_dir(tmp_path):
    """Provides a temporary directory for OCR output."""
    return tmp_path / "ocr_output"
