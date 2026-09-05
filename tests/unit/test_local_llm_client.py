import pytest
import json
from unittest.mock import patch, MagicMock
from src.infrastructure.llm.local_llm_client import LocalLLMClient
from src.core.entities import FichaEstructurada

@pytest.fixture
def llm_client():
    """Provides a LocalLLMClient instance."""
    return LocalLLMClient()

def test_depurar_returns_structured_output(llm_client):
    """
    Requirement: 5.3 Implement test_depurar_returns_structured_output from mocked results.
    Verify that the client correctly parses a valid JSON response from the LLM.
    """
    mock_response_json = {
        "choices": [{
            "message": {
                "content": '```json\n{\n"resumen_ejecutivo": "Resumen de prueba",\n"fragmentos_clave": ["Frag 1", "Frag 2"],\n"confiabilidad_extraccion": "alta"\n}\n```'
            }
        }]
    }

    with patch("requests.post") as mock_post:
        # Setup mock response
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response_json
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        # Use a short text to ensure only one chunk is processed
        resultado = llm_client.depurar("Texto corto")

        assert isinstance(resultado, FichaEstructurada)
        assert resultado.resumen_ejecutivo == "Resumen de prueba"
        assert resultado.fragmentos_clave == ["Frag 1", "Frag 2"]
        assert resultado.confiabilidad_extraccion == "alta"

def test_depurar_fusion_logic(llm_client):
    """
    Requirement: 5.4 Verify chunk fusion logic when multiple chunks produce valid results.
    Verify that multiple chunk results are fused correctly.
    """
    # We mock _depurar_chunk to avoid HTTP calls and control results
    res1 = FichaEstructurada(
        resumen_ejecutivo="Resumen 1",
        fragmentos_clave=["F1"],
        fecha_documento="2023-01-01",
        organismo_emisor="Org A"
    )
    res2 = FichaEstructurada(
        resumen_ejecutivo="Resumen 2",
        fragmentos_clave=["F2"],
        fecha_documento=None,
        organismo_emisor=None
    )

    with patch.object(LocalLLMClient, "_depurar_chunk") as mock_chunk:
        mock_chunk.side_effect = [res1, res2]

        # Use a long text to trigger multiple chunks
        # Threshold is 6000, so 7000 should produce 2 chunks (with overlap)
        texto_largo = "a" * 7000
        resultado = llm_client.depurar(texto_largo)

        # Verify fusion
        assert resultado.resumen_ejecutivo == "Resumen 1 [...] Resumen 2"
        assert resultado.fragmentos_clave == ["F1", "F2"]
        assert resultado.fecha_documento == "2023-01-01"
        assert resultado.organismo_emisor == "Org A"

def test_depurar_handles_json_errors(llm_client):
    """Verify that malformed JSON responses are handled gracefully."""
    mock_response_json = {
        "choices": [{
            "message": {"content": "Not a JSON at all"}
        }]
    }

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_response_json
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        resultado = llm_client.depurar("Texto corto")

        # Should return the empty/error ficha
        assert resultado == FichaEstructurada.vacia_por_error()
