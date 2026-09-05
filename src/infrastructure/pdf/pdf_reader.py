"""
Adaptadores de PDF: detección de capa de texto y aplicación de OCR.

Dos clases con responsabilidad única:
  - PdfTextInspector: implementa IPdfInspector
  - OcrProcessor: implementa IOcrProcessor

Requiere para OCR: brew install tesseract tesseract-lang ocrmypdf
"""
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import pypdf

from src.config.settings import settings

logger = logging.getLogger("ingesta.pdf_reader")


class PdfTextInspector:
    """
    Implementa IPdfInspector.
    Heurística: revisa las primeras N páginas del PDF y detecta si tiene
    suficiente texto extraíble sin necesidad de OCR.
    """

    def tiene_texto_real(self, pdf_path: Path) -> bool:
        """
        Devuelve True si el PDF tiene suficiente texto extraíble sin OCR.
        Documentos desclasificados a veces tienen portadas casi vacías,
        por eso revisamos varias páginas y no solo la primera.
        """
        try:
            reader = pypdf.PdfReader(str(pdf_path))
            n_paginas = min(3, len(reader.pages))
            total_chars = sum(
                len((reader.pages[i].extract_text() or "").strip())
                for i in range(n_paginas)
            )
            return total_chars > (settings.min_chars_texto_real * n_paginas)
        except Exception as e:
            logger.warning(f"No se pudo inspeccionar {pdf_path.name}: {e}")
            return False


class OcrProcessor:
    """
    Implementa IOcrProcessor.
    Aplica OCR con ocrmypdf (Tesseract por debajo) para añadir capa de texto
    a PDFs escaneados. Reemplazable por cualquier otro motor sin tocar
    la lógica de detección (PdfTextInspector).
    """

    def aplicar(self, pdf_path: Path, output_dir: Path) -> Optional[Path]:
        """
        Aplica OCR al PDF y devuelve la ruta del archivo resultante.
        Devuelve None si ocrmypdf no está instalado o el proceso falla.
        """
        if shutil.which("ocrmypdf") is None:
            logger.error(
                "ocrmypdf no está instalado. Instálalo con: "
                "brew install tesseract tesseract-lang ocrmypdf"
            )
            return None

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"ocr_{pdf_path.name}"

        try:
            # --skip-text: si alguna página ya tiene texto, no la reprocesa
            # -l spa+eng: documentos FOIA/CIA pueden estar en español o inglés
            subprocess.run(
                ["ocrmypdf", "--skip-text", "-l", "spa+eng", str(pdf_path), str(output_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            logger.info(f"OCR aplicado: {pdf_path.name} -> {output_path.name}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Fallo OCR en {pdf_path.name}: {e.stderr}")
            return None
