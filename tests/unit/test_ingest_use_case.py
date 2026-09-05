import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.application.ingest_use_case import IngestUseCase
from src.core.entities import FichaEstructurada

def test_generar_doc_id_determinista(tmp_path):
    """
    Requirement: 3.4 Implement test_guardar_id_is_generated_hashbased for document ID generation.
    Verify that doc_id is generated deterministically based on filename and size.
    """
    # Create a dummy file
    pdf_path = tmp_path / "documento_test.pdf"
    pdf_path.write_text("contenido de prueba")

    id1 = IngestUseCase._generar_doc_id(pdf_path)
    id2 = IngestUseCase._generar_doc_id(pdf_path)

    # Should be identical for the same file
    assert id1 == id2
    assert id1.startswith("DOC-")
    assert len(id1) == 14 # "DOC-" (4) + 10 chars hash = 14

def test_generar_doc_id_diferente_para_archivos_distintos(tmp_path):
    """Verify that different files produce different IDs."""
    pdf1 = tmp_path / "doc1.pdf"
    pdf1.write_text("contenido 1")

    pdf2 = tmp_path / "doc2.pdf"
    pdf2.write_text("contenido 2")

    assert IngestUseCase._generar_doc_id(pdf1) != IngestUseCase._generar_doc_id(pdf2)

def test_generar_doc_id_diferente_para_mismo_nombre_distinto_tamano(tmp_path):
    """Verify that same name but different size produces different ID."""
    pdf1 = tmp_path / "doc.pdf"
    pdf1.write_text("contenido 1")
    id1 = IngestUseCase._generar_doc_id(pdf1)

    # Overwrite with different content (different size)
    pdf1.write_text("contenido 1 modified and longer")
    id2 = IngestUseCase._generar_doc_id(pdf1)

    assert id1 != id2

def test_process_pdf_happy_path(tmp_path, mock_pdf_inspector, mock_ocr_processor, mock_llm_client, mock_document_repository, mock_semantic_index):
    """
    Requirement: 6.2 Implement test_process_pdf_complete_happy_path for successful end-to-end flow.
    Verify the entire pipeline from PDF detection to persistence.
    """
    # Setup
    pdf_path = tmp_path / "happy_path.pdf"
    pdf_path.write_text("dummy pdf")

    # 1. PDF has text (no OCR needed)
    mock_pdf_inspector.tiene_texto_real.return_value = True

    # 2. Mock MarkItDown result
    with patch("src.application.ingest_use_case.MarkItDown") as mock_md_class:
        mock_md_instance = mock_md_class.return_value
        mock_md_instance.convert.return_value = MagicMock(text_content="Este es un texto suficientemente largo para pasar la validacion")

        # 3. LLM returns structured ficha
        ficha = FichaEstructurada(resumen_ejecutivo="Resumen feliz", fragmentos_clave=["F1"])
        mock_llm_client.depurar.return_value = ficha

        use_case = IngestUseCase(
            pdf_inspector=mock_pdf_inspector,
            ocr_processor=mock_ocr_processor,
            llm_client=mock_llm_client,
            document_repo=mock_document_repository,
            semantic_index=mock_semantic_index,
        )

        # Execute
        doc_id = IngestUseCase._generar_doc_id(pdf_path)
        success = use_case.procesar_pdf(pdf_path)

        # Verify
        assert success is True

        # Verify persistence calls
        mock_document_repository.guardar.assert_called_once_with(doc_id, pdf_path.name, ficha)
        mock_semantic_index.indexar.assert_called_once_with(doc_id, pdf_path.name, ficha)

def test_process_pdf_fails_when_no_text_and_ocr_fails(tmp_path, mock_pdf_inspector, mock_ocr_processor, mock_llm_client, mock_document_repository, mock_semantic_index):
    """
    Requirement: 6.3 Implement test_process_pdf_fails_when_pdf_has_no_text layer (returns False from inspector).
    Verify that if PDF has no text and OCR also fails, the process returns False.
    """
    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.write_text("dummy")

    # 1. No text layer
    mock_pdf_inspector.tiene_texto_real.return_value = False
    # 2. OCR fails
    mock_ocr_processor.aplicar.return_value = None

    use_case = IngestUseCase(
        pdf_inspector=mock_pdf_inspector,
        ocr_processor=mock_ocr_processor,
        llm_client=mock_llm_client,
        document_repo=mock_document_repository,
        semantic_index=mock_semantic_index,
    )

    success = use_case.procesar_pdf(pdf_path)

    assert success is False
    mock_document_repository.guardar.assert_not_called()

def test_process_pdf_fails_when_llm_times_out(tmp_path, mock_pdf_inspector, mock_ocr_processor, mock_llm_client, mock_document_repository, mock_semantic_index):
    """
    Requirement: 6.4 Implement test_process_pdf_fails_when_llm_connection_times_out propagates exception.
    Verify that LLM client exceptions (like timeouts) are handled or propagated.
    """
    pdf_path = tmp_path / "timeout.pdf"
    pdf_path.write_text("dummy")
    mock_pdf_inspector.tiene_texto_real.return_value = True

    with patch("src.application.ingest_use_case.MarkItDown") as mock_md_class:
        mock_md_instance = mock_md_class.return_value
        mock_md_instance.convert.return_value = MagicMock(text_content="Este es un texto suficientemente largo para pasar la validacion")

        # Mock LLM to raise an exception
        mock_llm_client.depurar.side_effect = Exception("LLM Timeout")

        use_case = IngestUseCase(
            pdf_inspector=mock_pdf_inspector,
            ocr_processor=mock_ocr_processor,
            llm_client=mock_llm_client,
            document_repo=mock_document_repository,
            semantic_index=mock_semantic_index,
        )

        with pytest.raises(Exception, match="LLM Timeout"):
            use_case.procesar_pdf(pdf_path)

def test_process_pdf_moves_original_to_processed_dir(tmp_path, mock_pdf_inspector, mock_ocr_processor, mock_llm_client, mock_document_repository, mock_semantic_index):
    """
    Requirement: 6.5 Implement test_process_pdf_moves_original_to_processed_dir on successful completion.
    Verify that the source PDF is moved to the processed directory.
    """
    from src.config.settings import DOCS_PROCESADOS_DIR

    pdf_path = tmp_path / "move_me.pdf"
    pdf_path.write_text("dummy")

    mock_pdf_inspector.tiene_texto_real.return_value = True

    with patch("src.application.ingest_use_case.MarkItDown") as mock_md_class:
        mock_md_instance = mock_md_class.return_value
        mock_md_instance.convert.return_value = MagicMock(text_content="Este es un texto suficientemente largo para pasar la validacion")
        mock_llm_client.depurar.return_value = FichaEstructurada(resumen_ejecutivo="Ok")

        use_case = IngestUseCase(
            pdf_inspector=mock_pdf_inspector,
            ocr_processor=mock_ocr_processor,
            llm_client=mock_llm_client,
            document_repo=mock_document_repository,
            semantic_index=mock_semantic_index,
        )

        success = use_case.procesar_pdf(pdf_path)

        assert success is True
        # Verify file was moved
        assert not pdf_path.exists()
        assert (DOCS_PROCESADOS_DIR / pdf_path.name).exists()
