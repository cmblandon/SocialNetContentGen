"""
Entidades del dominio — Proyecto Expediente.

Estas clases representan los conceptos centrales del negocio.
No importan nada de infrastructure ni de librerías externas.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FichaEstructurada:
    """
    Resultado del procesamiento de un documento por el LLM local.
    Representa la forma canónica de un documento ya depurado.
    """
    resumen_ejecutivo: str
    fragmentos_clave: list[str] = field(default_factory=list)
    fecha_documento: Optional[str] = None
    organismo_emisor: Optional[str] = None
    nivel_redaccion: Optional[str] = None
    confiabilidad_extraccion: Optional[str] = None
    idioma_original: Optional[str] = None

    @classmethod
    def vacia_por_error(cls) -> "FichaEstructurada":
        """Devuelve una ficha vacía cuando el LLM no puede procesar el documento."""
        return cls(
            resumen_ejecutivo="[ERROR: no se pudo depurar el documento]",
            confiabilidad_extraccion="baja",
            nivel_redaccion="desconocida",
        )

    @classmethod
    def desde_dict(cls, data: dict) -> "FichaEstructurada":
        """Construye una FichaEstructurada desde el dict devuelto por el LLM."""
        return cls(
            resumen_ejecutivo=data.get("resumen_ejecutivo", ""),
            fragmentos_clave=data.get("fragmentos_clave", []),
            fecha_documento=data.get("fecha_documento"),
            organismo_emisor=data.get("organismo_emisor"),
            nivel_redaccion=data.get("nivel_redaccion"),
            confiabilidad_extraccion=data.get("confiabilidad_extraccion"),
            idioma_original=data.get("idioma_original"),
        )

    def a_dict(self) -> dict:
        """Serializa la ficha a dict (útil para JSON/logging)."""
        return {
            "fecha_documento": self.fecha_documento,
            "organismo_emisor": self.organismo_emisor,
            "resumen_ejecutivo": self.resumen_ejecutivo,
            "fragmentos_clave": self.fragmentos_clave,
            "nivel_redaccion": self.nivel_redaccion,
            "confiabilidad_extraccion": self.confiabilidad_extraccion,
            "idioma_original": self.idioma_original,
        }
