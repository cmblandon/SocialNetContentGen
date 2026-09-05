"""
Lógica pura de división de texto en chunks solapados.
Sin dependencias de I/O — es una función de transformación pura, fácil de testear.
"""
from src.config.settings import settings


def dividir_en_chunks(texto: str) -> list[str]:
    """
    Divide texto largo en fragmentos solapados para no exceder el
    contexto cómodo del modelo local.

    El solape evita cortar una idea justo en el límite entre dos chunks.
    Si el texto cabe en un único chunk, lo devuelve tal cual.
    """
    if len(texto) <= settings.chunk_size_chars:
        return [texto]

    chunks: list[str] = []
    inicio = 0
    while inicio < len(texto):
        fin = inicio + settings.chunk_size_chars
        chunks.append(texto[inicio:fin])
        inicio = fin - settings.chunk_overlap_chars
    return chunks
