import pytest
from unittest.mock import Mock

from src.config.settings import DATA_DIR
from src.core.ports import (
    IPdfInspector,
    IOcrProcessor,
    ILLMClient,
    IDocumentRepository,
    ISemanticIndex,
    IDocumentTextLoader,
)


def _snapshot_data_dir() -> set:
    """Paths directly under data/, or an empty set if it does not exist."""
    if not DATA_DIR.exists():
        return set()
    return {path.name for path in DATA_DIR.iterdir()}


@pytest.fixture(autouse=True)
def data_dir_is_not_polluted():
    """
    Fail any test that creates something under `data/`.

    Several clients and stores default their directory to a path under
    DATA_DIR and `mkdir` it on construction, so a default-constructed
    instance in a test writes into the developer's working tree. That is easy
    to do by accident and easy to miss — one such test left dozens of fixture
    files behind before anyone noticed. Tests must pass a `tmp_path`-scoped
    directory instead (see docs/backend-standards.md, Testing Standards).
    """
    before = _snapshot_data_dir()
    yield
    created = _snapshot_data_dir() - before
    if created:
        raise AssertionError(
            f"Test created {sorted(created)} under {DATA_DIR}. Pass a "
            "tmp_path-scoped directory to stores/clients instead of relying "
            "on their DATA_DIR defaults."
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
