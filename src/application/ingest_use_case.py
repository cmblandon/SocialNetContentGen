"""
Caso de uso: ingesta de un documento PDF.

Orquesta todas las capas del pipeline sin conocer los detalles de
implementación — trabaja contra los puertos (interfaces) del core.
"""
import hashlib
import logging
import shutil
from pathlib import Path
from typing import Optional

from markitdown import MarkItDown

from src.config.settings import DOCS_RAW_DIR, DOCS_PROCESADOS_DIR
from src.core.ports import (
    IDocumentRepository,
    ILLMClient,
    IOcrProcessor,
    IPdfInspector,
    ISemanticIndex,
)

logger = logging.getLogger("ingesta.use_case")


class IngestUseCase:
    """
    Caso de uso principal del pipeline.
    Recibe sus dependencias por constructor (Dependency Injection).

    IPdfInspector y IOcrProcessor se inyectan por separado para poder:
      - Testear la lógica de detección sin levantar Tesseract
      - Reemplazar el motor OCR sin tocar la detección (y viceversa)
    """

    def __init__(
        self,
        pdf_inspector: IPdfInspector,
        ocr_processor: IOcrProcessor,
        llm_client: ILLMClient,
        document_repo: IDocumentRepository,
        semantic_index: ISemanticIndex,
    ) -> None:
        """Inicializa el caso de uso con las dependencias necesarias."""
        self._pdf_inspector = pdf_inspector
        self._ocr_processor = ocr_processor
        self._llm_client = llm_client
        self._document_repo = document_repo
        self._semantic_index = semantic_index
        self._markitdown = MarkItDown()

    def procesar_pdf(self, pdf_path: Path) -> bool:
        """
        Ejecuta el pipeline completo para un único PDF.
        Devuelve True si el documento fue procesado con éxito.
        """
        logger.info(f"--- Procesando: {pdf_path.name} ---")

        # 1. Detecta si necesita OCR y, de ser así, lo aplica
        pdf_listo: Optional[Path] = self._preparar_pdf(pdf_path)
        if pdf_listo is None:
            return False

        # 2. Extrae texto con MarkItDown
        texto_crudo: Optional[str] = self._extraer_texto(pdf_listo, pdf_path.name)
        if texto_crudo is None:
            return False

        # 3. Depura y estructura con el modelo local (chunking automático si es largo)
        ficha = self._llm_client.depurar(texto_crudo)

        # 4. Persiste en SQLite + ChromaDB
        doc_id = self._generar_doc_id(pdf_path)
        self._document_repo.guardar(doc_id, pdf_path.name, ficha)
        self._semantic_index.indexar(doc_id, pdf_path.name, ficha)

        # 5. Mueve el PDF original a procesados/ para no reprocesarlo
        DOCS_PROCESADOS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pdf_path), str(DOCS_PROCESADOS_DIR / pdf_path.name))

        logger.info(
            f"OK {doc_id} | confiabilidad={ficha.confiabilidad_extraccion} | "
            f"redaccion={ficha.nivel_redaccion}"
        )
        return True

    def _preparar_pdf(self, pdf_path: Path) -> Optional[Path]:
        """
        Coordina la detección de texto y el OCR.
        El inspector y el procesador OCR son responsabilidades separadas
        que se inyectan de forma independiente.
        """
        if self._pdf_inspector.tiene_texto_real(pdf_path):
            logger.info(f"{pdf_path.name}: capa de texto OK, sin necesidad de OCR")
            return pdf_path

        logger.info(f"{pdf_path.name}: sin capa de texto útil, aplicando OCR...")
        ocr_dir = DOCS_RAW_DIR / "_ocr_temp"
        resultado: Optional[Path] = self._ocr_processor.aplicar(pdf_path, ocr_dir)
        if resultado is None:
            logger.error(f"No se pudo preparar {pdf_path.name} para extracción. Se omite.")
        return resultado

    def _extraer_texto(self, pdf_listo: Path, nombre_original: str) -> Optional[str]:
        """Extrae el texto del PDF usando MarkItDown."""
        try:
            resultado = self._markitdown.convert(str(pdf_listo))
            texto_crudo = resultado.text_content
        except Exception as e:
            logger.error(f"MarkItDown falló en {nombre_original}: {e}")
            return None

        if not texto_crudo or len(texto_crudo.strip()) < 20:
            logger.warning(f"{nombre_original}: texto extraído insuficiente, se omite.")
            return None

        return texto_crudo

    @staticmethod
    def _generar_doc_id(pdf_path: Path) -> str:
        """ID determinista basado en nombre + tamaño del archivo, para
        poder re-correr el pipeline sin duplicar documentos ya ingeridos."""
        contenido_clave = f"{pdf_path.name}_{pdf_path.stat().st_size}"
        hash_corto = hashlib.sha256(contenido_clave.encode()).hexdigest()[:10]
        return f"DOC-{hash_corto}"
