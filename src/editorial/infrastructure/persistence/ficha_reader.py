"""
Read-only access to the ingestion pipeline's SQLite file
(data/knowledge_base/expedientes.sqlite), from the editorial bounded
context. Deliberately separate from SQLiteRepository (which only exposes
`guardar`) — see design.md Decision 3: editorial reads FichaEstructurada
records without taking a dependency on the ingestion context's own
repository class.
"""
import json
import sqlite3
from typing import Optional

from src.config.settings import SQLITE_PATH
from src.core.entities import FichaEstructurada


def read_ficha_by_id(doc_id: str) -> Optional[FichaEstructurada]:
    """Returns the FichaEstructurada stored under doc_id, or None if absent."""
    conn = sqlite3.connect(str(SQLITE_PATH))
    try:
        cursor = conn.execute(
            """
            SELECT fecha_documento, organismo_emisor, resumen_ejecutivo,
                   fragmentos_clave, nivel_redaccion, confiabilidad_extraccion,
                   idioma_original
            FROM documentos
            WHERE id = ?
            """,
            (doc_id,),
        )
        row = cursor.fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    (
        fecha_documento,
        organismo_emisor,
        resumen_ejecutivo,
        fragmentos_clave_json,
        nivel_redaccion,
        confiabilidad_extraccion,
        idioma_original,
    ) = row

    return FichaEstructurada(
        resumen_ejecutivo=resumen_ejecutivo,
        fragmentos_clave=json.loads(fragmentos_clave_json) if fragmentos_clave_json else [],
        fecha_documento=fecha_documento,
        organismo_emisor=organismo_emisor,
        nivel_redaccion=nivel_redaccion,
        confiabilidad_extraccion=confiabilidad_extraccion,
        idioma_original=idioma_original,
    )
