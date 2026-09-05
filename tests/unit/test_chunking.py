import pytest
from src.application.chunking import dividir_en_chunks
from src.config.settings import settings

def test_dividir_en_chunks_short_text():
    """
    Requirement: Chunk short documents without overlap.
    The system SHALL return the original text as a single chunk when length does not exceed chunk_size_chars threshold.
    """
    # Case: text well under threshold
    texto_corto = "Este es un texto corto que no debería dividirse."
    resultado = dividir_en_chunks(texto_corto)

    assert resultado == [texto_corto]
    assert len(resultado) == 1

def test_dividir_en_chunks_exactly_at_threshold():
    """
    Scenario: Text exactly at boundary.
    WHEN input text length equals chunk_size_chars precisely
    THEN divider_en_chunks treats it as short document (single chunk)
    """
    texto_limite = "a" * settings.chunk_size_chars
    resultado = dividir_en_chunks(texto_limite)

    assert resultado == [texto_limite]
    assert len(resultado) == 1

@pytest.mark.parametrize("input_length, expected_chunks", [
    (6100, 2),   # Crossing one boundary: [0:6000], [5700:6100]
    (12000, 3),  # Multiple boundaries: [0:6000], [5700:11700], [11400:12000]
    (15000, 3),  # Multiple boundaries: [0:6000], [5700:11700], [11400:15000]
    (18000, 4),  # More boundaries
])
def test_dividir_en_chunks_long_documents(input_length, expected_chunks):
    """
    Requirement: Chunk long documents with overlapping fragments.
    Verify that long texts are divided into multiple chunks with correct overlap.
    """
    texto = "a" * input_length
    resultado = dividir_en_chunks(texto)

    assert len(resultado) == expected_chunks

    # Verify first chunk
    assert len(resultado[0]) == settings.chunk_size_chars

    # Verify overlap in second chunk if it exists
    if len(resultado) > 1:
        # The second chunk should start at (chunk_size - overlap)
        # We can verify this by checking if the overlap region is identical
        overlap_region_1 = resultado[0][-settings.chunk_overlap_chars:]
        overlap_region_2 = resultado[1][:settings.chunk_overlap_chars]
        assert overlap_region_1 == overlap_region_2

def test_dividir_en_chunks_empty_string():
    """
    Scenario: Empty document.
    WHEN input text is an empty string
    THEN divider_en_chunks returns a list with one empty string element
    """
    resultado = dividir_en_chunks("")
    assert resultado == [""]
    assert len(resultado) == 1
