"""
Repositorio SQLite para persistir metadata estructurada de documentos.
Implementa el puerto IDocumentRepository definido en core/ports.py.
"""
import json
import logging
import sqlite3
from datetime import datetime, timezone

from src.config.settings import SQLITE_PATH
from src.core.entities import FichaEstructurada

logger = logging.getLogger("ingesta.sqlite_repo")


class SQLiteRepository:
    """
    Adaptador concreto que implementa IDocumentRepository.
    Persiste y recupera la metadata estructurada de documentos en SQLite.
    """

    def __init__(self) -> None:
        self._conn = self._inicializar()

    def _inicializar(self) -> sqlite3.Connection:
        SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(SQLITE_PATH))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documentos (
                id TEXT PRIMARY KEY,
                archivo_origen TEXT NOT NULL,
                fecha_documento TEXT,
                organismo_emisor TEXT,
                resumen_ejecutivo TEXT,
                fragmentos_clave TEXT,      -- JSON list
                nivel_redaccion TEXT,
                confiabilidad_extraccion TEXT,
                idioma_original TEXT,
                fecha_ingesta TEXT NOT NULL,
                usado_en_expediente TEXT   -- se llena cuando el Agente 2/3 lo consume
            )
            """
        )
        conn.commit()
        return conn

    def guardar(self, doc_id: str, archivo_origen: str, ficha: FichaEstructurada) -> None:
        """Persiste o actualiza la ficha de un documento en SQLite."""
        self._conn.execute(
            """
            INSERT OR REPLACE INTO documentos
            (id, archivo_origen, fecha_documento, organismo_emisor, resumen_ejecutivo,
             fragmentos_clave, nivel_redaccion, confiabilidad_extraccion, idioma_original, fecha_ingesta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                archivo_origen,
                ficha.fecha_documento,
                ficha.organismo_emisor,
                ficha.resumen_ejecutivo,
                json.dumps(ficha.fragmentos_clave, ensure_ascii=False),
                ficha.nivel_redaccion,
                ficha.confiabilidad_extraccion,
                ficha.idioma_original,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()
        logger.info(f"Guardado en SQLite: {doc_id}")

    def cerrar(self) -> None:
        """Cierra la conexión a la base de datos."""
        self._conn.close()
