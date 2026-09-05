"""
Tests for the editorial service's read-only reader over the ingestion
pipeline's SQLite file. Read-only and separate from SQLiteRepository (which
only exposes `guardar`) — see design.md Decision 3: editorial reads the
ingestion schema without depending on the ingestion bounded context's own
repository class.
"""
from unittest.mock import patch

from src.core.entities import FichaEstructurada
from src.infrastructure.persistence.sqlite_repo import SQLiteRepository
from src.editorial.infrastructure.persistence.ficha_reader import read_ficha_by_id


def test_reads_a_previously_ingested_ficha(tmp_path):
    db_path = tmp_path / "expedientes.sqlite"

    with patch("src.infrastructure.persistence.sqlite_repo.SQLITE_PATH", db_path):
        repo = SQLiteRepository()
        repo.guardar(
            "doc-123",
            "documento.pdf",
            FichaEstructurada(
                resumen_ejecutivo="Resumen de prueba",
                fragmentos_clave=["Fragmento 1", "Fragmento 2"],
                fecha_documento="2024-03-01",
                organismo_emisor="AARO",
                confiabilidad_extraccion="alta",
            ),
        )
        repo.cerrar()

    with patch("src.editorial.infrastructure.persistence.ficha_reader.SQLITE_PATH", db_path):
        ficha = read_ficha_by_id("doc-123")

    assert ficha is not None
    assert ficha.resumen_ejecutivo == "Resumen de prueba"
    assert ficha.fragmentos_clave == ["Fragmento 1", "Fragmento 2"]
    assert ficha.fecha_documento == "2024-03-01"
    assert ficha.organismo_emisor == "AARO"


def test_returns_none_when_doc_id_not_found(tmp_path):
    db_path = tmp_path / "expedientes.sqlite"

    with patch("src.infrastructure.persistence.sqlite_repo.SQLITE_PATH", db_path):
        repo = SQLiteRepository()
        repo.cerrar()

    with patch("src.editorial.infrastructure.persistence.ficha_reader.SQLITE_PATH", db_path):
        ficha = read_ficha_by_id("does-not-exist")

    assert ficha is None
