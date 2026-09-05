"""
Puertos (interfaces/contratos) del dominio — Proyecto Expediente.

Define los contratos que la capa de infrastructure debe implementar.

Define los contratos que la capa de infrastructure debe implementar.
El dominio sólo depende de estas abstracciones, nunca de implementaciones concretas.
Usa typing.Protocol para tipado estructural (duck typing verificado) — los adaptadores
no necesitan heredar de nada para cumplir un contrato.
"""
from pathlib import Path
from typing import Optional, Protocol

from src.core.entities import FichaEstructurada


class IPdfInspector(Protocol):
    """
    Contrato para detectar si un PDF tiene capa de texto real extraíble.
    Separado de IOcrProcessor para poder testear/reemplazar de forma independiente.
    """

    def tiene_texto_real(self, pdf_path: Path) -> bool:
        """Devuelve True si el PDF tiene suficiente texto extraíble sin OCR."""
        ...


class IOcrProcessor(Protocol):
    """
    Contrato para aplicar OCR a un PDF que no tiene capa de texto.
    Separado de IPdfInspector para poder cambiar el motor OCR (ej: Tesseract → Apple Vision)
    sin tocar la lógica de detección.
    """

    def aplicar(self, pdf_path: Path, output_dir: Path) -> Optional[Path]:
        """
        Aplica OCR al PDF y devuelve la ruta del archivo resultante con texto añadido.
        Devuelve None si el proceso falla.
        """
        ...


class IDocumentTextLoader(Protocol):
    """
    CONTRATO DE UNIFICADO: Provee el texto final a partir de una ruta de archivo,
    decidiendo internamente si se requiere inspección o OCR.
    Esta es la interfaz que consume el 'IngestUseCase'.
    """

    def obtener_texto(self, pdf_path: Path, output_dir: Path) -> Optional[str]:
        """
        Procesa el PDF (inspecciona o aplica OCR) y devuelve el texto extraído.
        Devuelve None si el proceso falla catastróficamente.
        """
        ...


class ILLMClient(Protocol):
    """
    Contrato para interactuar con el modelo de lenguaje.
    Implementaciones concretas: LocalLLMClient, (futuro) ClaudeClient.
    """

    def depurar(self, texto: str) -> FichaEstructurada:
        """
        Toma texto crudo y devuelve una FichaEstructurada.
        Maneja chunking internamente si el texto es demasiado largo.
        """
        ...


class IDocumentRepository(Protocol):
    """
    Contrato para persistir metadata estructurada de documentos.
    Implementaciones concretas: SQLiteRepository, (futuro) PostgresRepository.
    """

    def guardar(self, doc_id: str, archivo_origen: str, ficha: FichaEstructurada) -> None:
        """Persiste o actualiza la ficha de un documento."""
        ...


class ISemanticIndex(Protocol):
    """
    Contrato para indexar documentos en un índice semántico/vectorial.
    Implementaciones concretas: ChromaRepository, (futuro) PineconeRepository.
    """

    def indexar(self, doc_id: str, archivo_origen: str, ficha: FichaEstructurada) -> None:
        """Indexa el contenido del documento para búsqueda semántica."""
        ...

