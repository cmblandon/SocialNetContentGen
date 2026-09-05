"""
Cliente HTTP para el modelo de lenguaje local (mlx_lm.server).
Implementa el puerto ILLMClient definido en core/ports.py.

Requiere el servidor corriendo en otra terminal:
    mlx_lm.server --model mlx-community/Qwen2.5-7B-Instruct-4bit --port 8080
"""
import json
import logging
import re
from pathlib import Path
from typing import Optional

import requests

from src.application.chunking import dividir_en_chunks
from src.config.settings import PROMPT_DEPURADOR_PATH, settings
from src.core.entities import FichaEstructurada

logger = logging.getLogger("ingesta.local_llm_client")


class LocalLLMClient:
    """
    Adaptador concreto que implementa ILLMClient.
    Se comunica con el servidor local de mlx_lm vía API compatible con OpenAI.
    Maneja chunking automático para documentos largos.
    """

    def __init__(self) -> None:
        """Inicializa el cliente con la plantilla de prompt del archivo depurador.md."""
        self._prompt_template: str = PROMPT_DEPURADOR_PATH.read_text(encoding="utf-8")

    def depurar(self, texto: str) -> FichaEstructurada:
        """
        Depura un documento completo, dividiéndolo en chunks si es largo
        y fusionando los resultados en una sola FichaEstructurada.
        """
        chunks = dividir_en_chunks(texto)
        logger.info(f"Documento dividido en {len(chunks)} chunk(s) para depuración")

        resultados_parciales: list[FichaEstructurada] = []
        for i, chunk in enumerate(chunks):
            logger.info(f"  Depurando chunk {i + 1}/{len(chunks)}...")
            resultado: Optional[FichaEstructurada] = self._depurar_chunk(chunk)
            if resultado:
                resultados_parciales.append(resultado)

        if not resultados_parciales:
            return FichaEstructurada.vacia_por_error()

        if len(resultados_parciales) == 1:
            return resultados_parciales[0]

        return self._fusionar_resultados(resultados_parciales)

    def _depurar_chunk(self, texto_chunk: str) -> Optional[FichaEstructurada]:
        """Llama al modelo local para un solo chunk de texto."""
        prompt = self._prompt_template.format(texto=texto_chunk)

        try:
            resp = requests.post(
                settings.local_llm_url,
                json={
                    "model": settings.local_llm_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": settings.local_llm_temperature,
                },
                timeout=settings.local_llm_timeout_sec,
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            logger.error(
                f"No se pudo conectar al modelo local en {settings.local_llm_url}. "
                "¿Está corriendo mlx_lm.server?"
            )
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Error llamando al modelo local: {e}")
            return None

        data = resp.json()
        contenido = data["choices"][0]["message"]["content"]
        parsed: Optional[dict] = self._extraer_json(contenido)
        return FichaEstructurada.desde_dict(parsed) if parsed else None

    def _extraer_json(self, respuesta_texto: str) -> Optional[dict]:
        """
        El modelo a veces envuelve el JSON en ```json ... ``` a pesar de la
        instrucción. Esto limpia y parsea de forma tolerante.
        """
        texto = respuesta_texto.strip()
        texto = re.sub(r"^```(json)?", "", texto).strip()
        texto = re.sub(r"```$", "", texto).strip()

        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", texto, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        logger.error(f"No se pudo parsear JSON de la respuesta del LLM: {texto[:300]}")
        return None

    def _fusionar_resultados(self, resultados: list[FichaEstructurada]) -> FichaEstructurada:
        """
        Documento multi-chunk: fusiona fragmentos_clave y toma metadata del
        primer chunk que trajo datos (usualmente donde está el encabezado).
        """
        base = next(
            (r for r in resultados if r.fecha_documento or r.organismo_emisor),
            resultados[0],
        )

        todos_fragmentos: list[str] = []
        for r in resultados:
            todos_fragmentos.extend(r.fragmentos_clave)

        resumen_fusionado = " [...] ".join(
            r.resumen_ejecutivo for r in resultados if r.resumen_ejecutivo
        )[:1500]

        return FichaEstructurada(
            resumen_ejecutivo=resumen_fusionado,
            fragmentos_clave=todos_fragmentos,
            fecha_documento=base.fecha_documento,
            organismo_emisor=base.organismo_emisor,
            nivel_redaccion=base.nivel_redaccion,
            confiabilidad_extraccion=base.confiabilidad_extraccion,
            idioma_original=base.idioma_original,
        )
