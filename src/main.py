"""
Punto de entrada principal — Proyecto Expediente.

Composition Root: aquí se instancian todos los adaptadores concretos
y se inyectan en el caso de uso. Es el único lugar del proyecto donde
la capa de infrastructure y la capa de application se conocen.

Uso:
    1. Coloca los PDFs en data/docs_raw/
    2. En otra terminal, levanta el modelo local:
       mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
    3. Corre desde la raíz del proyecto:
       python -m src.main
"""
import logging
from pathlib import Path
from typing import Generator

from src.config.settings import LOG_PATH, DOCS_RAW_DIR, DOCS_PROCESADOS_DIR
from src.application.ingest_use_case import IngestUseCase
from src.infrastructure.llm.local_llm_client import LocalLLMClient
from src.infrastructure.pdf.pdf_reader import OcrProcessor, PdfTextInspector
from src.infrastructure.persistence.chroma_repo import ChromaRepository
from src.infrastructure.persistence.sqlite_repo import SQLiteRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)
logger = logging.getLogger("ingesta.main")


def main() -> None:
    """
    Punto de entrada principal del pipeline de ingesta.
    
    Orquesta la creación de adaptadores y la ejecución del caso de uso.
    """
    # --- Composition Root ---
    # Instancia los adaptadores concretos y los inyecta en el caso de uso.
    # Ninguna otra capa del proyecto necesita saber qué implementación concreta se usa.
    sqlite_repo = SQLiteRepository()

    use_case = IngestUseCase(
        pdf_inspector=PdfTextInspector(),
        ocr_processor=OcrProcessor(),
        llm_client=LocalLLMClient(),
        document_repo=sqlite_repo,
        semantic_index=ChromaRepository(),
    )

    # --- Batch Processing Logic ---
    DOCS_RAW_DIR.mkdir(parents=True, exist_ok=True)
    pdfs: list[Path] = sorted(p for p in DOCS_RAW_DIR.glob("*.pdf") if p.is_file())

    if not pdfs:
        logger.info(f"No hay PDFs nuevos en {DOCS_RAW_DIR}. Coloca archivos y vuelve a correr.")
    else:
        logger.info(f"Encontrados {len(pdfs)} PDF(s) para procesar.")
        exitosos, fallidos = 0, 0
            
        for pdf_path in pdfs:
            try:
                if use_case.procesar_pdf(pdf_path):
                    exitosos += 1
                else:
                    fallidos += 1
            except Exception as e:
                logger.exception(f"Error inesperado procesando {pdf_path.name}: {e}")
                fallidos += 1

        logger.info(f"=== Ingesta completa: {exitosos} exitosos, {fallidos} fallidos ===")

    sqlite_repo.cerrar()


if __name__ == "__main__":
    main()
