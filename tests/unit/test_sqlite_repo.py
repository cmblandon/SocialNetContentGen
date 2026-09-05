import pytest
import sqlite3
import json
from pathlib import Path
from unittest.mock import patch
from src.infrastructure.persistence.sqlite_repo import SQLiteRepository
from src.core.entities import FichaEstructurada

@pytest.fixture
def temp_db(tmp_path):
    """Creates a temporary database path for each test."""
    db_path = tmp_path / "test_expedientes.sqlite"
    return db_path

@pytest.fixture
def sqlite_repo(temp_db):
    """
    Provides a SQLiteRepository instance configured to use a temporary database.
    Patches SQLITE_PATH in the module to ensure it uses the temporary file.
    """
    with patch("src.infrastructure.persistence.sqlite_repo.SQLITE_PATH", temp_db):
        repo = SQLiteRepository()
        yield repo
        repo.cerrar()

def test_guardar_creates_table(sqlite_repo, temp_db):
    """
    Requirement: 3.2 Implement test_guardar_creates_table if not exists on first insert.
    Verify that the 'documentos' table is created automatically upon instantiation or first save.
    """
    # Verify table doesn't exist initially (though __init__ creates it)
    # Since __init__ creates it, we just verify it exists after instantiation
    conn = sqlite3.connect(str(temp_db))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documentos';")
    assert cursor.fetchone() is not None
    conn.close()

def test_guardar_all_fields_mapped(sqlite_repo, temp_db):
    """
    Requirement: 3.3 Implement test_guardar_all_fields_mapped correctly from FichaEstructurada.
    Verify that all fields from FichaEstructurada are correctly persisted in SQLite.
    """
    doc_id = "test-id-123"
    archivo = "documento.pdf"
    ficha = FichaEstructurada(
        resumen_ejecutivo="Resumen de prueba",
        fragmentos_clave=["Fragmento 1", "Fragmento 2"],
        fecha_documento="2023-10-27",
        organismo_emisor="Ministerio de Salud",
        nivel_redaccion="alto",
        confiabilidad_extraccion="alta",
        idioma_original="español"
    )

    sqlite_repo.guardar(doc_id, archivo, ficha)

    # Verify persistence
    conn = sqlite3.connect(str(temp_db))
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM documentos WHERE id=?", (doc_id,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == doc_id
    assert row[1] == archivo
    assert row[2] == "2023-10-27"
    assert row[3] == "Ministerio de Salud"
    assert row[4] == "Resumen de prueba"
    assert json.loads(row[5]) == ["Fragmento 1", "Fragmento 2"]
    assert row[6] == "alto"
    assert row[7] == "alta"
    assert row[8] == "español"
    assert row[9] is not None  # fecha_ingesta

def test_guardar_timestamp_populated(sqlite_repo, temp_db):
    """
    Requirement: 3.5 Implement test_guardar_timestamp_always_populated_utc for ingest timestamp.
    Verify that fecha_ingesta is automatically populated with an ISO format UTC timestamp.
    """
    doc_id = "test-ts-123"
    archivo = "test.pdf"
    ficha = FichaEstructurada(resumen_ejecutivo="Test TS")

    sqlite_repo.guardar(doc_id, archivo, ficha)

    conn = sqlite3.connect(str(temp_db))
    cursor = conn.cursor()
    cursor.execute("SELECT fecha_ingesta FROM documentos WHERE id=?", (doc_id,))
    ts = cursor.fetchone()[0]
    conn.close()

    assert ts is not None
    # Verify it's a valid ISO format timestamp (basic check)
    assert "T" in ts
    assert ts.endswith("+00:00") or ts.endswith("Z")
