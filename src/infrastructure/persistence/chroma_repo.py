"""
Repositorio ChromaDB para indexación semántica de documentos.
Implementa el puerto ISemanticIndex definido en core/ports.py.
"""
import logging

import chromadb
from sentence_transformers import SentenceTransformer

from src.config.settings import CHROMA_DIR, settings
from src.core.entities import FichaEstructurada

logger = logging.getLogger("ingesta.chroma_repo")

_COLLECTION_NAME = "expedientes"


class ChromaRepository:
    """
    Adaptador concreto que implementa ISemanticIndex.
    Indexa y recupera documentos usando embeddings locales multilingües.

    El modelo de embeddings se carga de forma perezosa (lazy) la primera vez
    que se necesita, para no consumir memoria si ChromaDB no se usa.
    """

    def __init__(self) -> None:
        self._client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self._coleccion = self._client.get_or_create_collection(_COLLECTION_NAME)
        self._modelo: SentenceTransformer | None = None

    def _get_modelo(self) -> SentenceTransformer:
        if self._modelo is None:
            logger.info(f"Cargando modelo de embeddings local: {settings.embedding_model}")
            self._modelo = SentenceTransformer(settings.embedding_model)
        return self._modelo

    def indexar(self, doc_id: str, archivo_origen: str, ficha: FichaEstructurada) -> None:
        """
        Indexa el resumen ejecutivo + fragmentos clave en ChromaDB para
        búsqueda semántica posterior (esto es lo que consulta el Agente 0
        "Bibliotecario" cuando arma contexto para el Verificador/Guionista).
        """
        texto_indexable = ficha.resumen_ejecutivo + "\n" + "\n".join(ficha.fragmentos_clave)
        if not texto_indexable.strip():
            logger.warning(f"{doc_id}: nada indexable, se omite ChromaDB")
            return

        modelo = self._get_modelo()
        embedding = modelo.encode(texto_indexable).tolist()

        self._coleccion.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[texto_indexable],
            metadatas=[{
                "archivo_origen": archivo_origen,
                "fecha_documento": ficha.fecha_documento or "",
                "organismo_emisor": ficha.organismo_emisor or "",
                "confiabilidad_extraccion": ficha.confiabilidad_extraccion or "",
            }],
        )
        logger.info(f"Indexado en ChromaDB: {doc_id}")
