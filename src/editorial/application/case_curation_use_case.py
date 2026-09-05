"""
CaseCurationUseCase — per specs/case-curation/spec.md. Scoring novelty,
narrative potential, etc. is a judgment call delegated to the LLM (like
story-writing/platform-adaptation); this use case validates the scores,
enforces the >=15/25 threshold, and permanently records every evaluated
case in /casos_cubiertos.md — the recording happens regardless of the
LLM's judgment, so no case is ever silently re-evaluated.
"""
import json
from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.editorial.core.ports import ILLMClient, ScrapedDocument
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore

ADVANCEMENT_THRESHOLD = 15
MIN_CRITERION_SCORE = 1
MAX_CRITERION_SCORE = 5

_CRITERIA = (
    "novedad",
    "potencial_narrativo",
    "respaldo_documental",
    "elemento_visual",
    "encaje_audiencia",
)

_PROMPT_TEMPLATE = """\
You are the editorial curator of "Archivo Desclasificado". Score the \
document below from 1 to 5 on each criterion: novedad, potencial_narrativo, \
respaldo_documental, elemento_visual, encaje_audiencia. If the total is 15 \
or higher, also provide a brief narrative_angle note explaining what makes \
this case work as a story.

Title: {title}
Agency: {agency}
Extracted text:
{extracted_text}

Respond with JSON matching this shape:
{{"scores": {{"novedad": 1-5, "potencial_narrativo": 1-5, \
"respaldo_documental": 1-5, "elemento_visual": 1-5, "encaje_audiencia": 1-5}}, \
"narrative_angle": "..."}}
"""


class CurationError(Exception):
    """Raised when the LLM's curation output can't be trusted: a score is
    out of range, or a case scoring at/above threshold lacks the required
    narrative-angle note."""


@dataclass
class CurationScore:
    novedad: int
    potencial_narrativo: int
    respaldo_documental: int
    elemento_visual: int
    encaje_audiencia: int

    @property
    def total(self) -> int:
        return (
            self.novedad
            + self.potencial_narrativo
            + self.respaldo_documental
            + self.elemento_visual
            + self.encaje_audiencia
        )


@dataclass
class CurationResult:
    document: ScrapedDocument
    score: CurationScore
    advanced: bool
    narrative_angle: Optional[str]


class CaseCurationUseCase:
    def __init__(self, llm_client: ILLMClient, memory_store: ProjectMemoryStore):
        self._llm_client = llm_client
        self._memory_store = memory_store

    def curate(self, document: ScrapedDocument) -> Optional[CurationResult]:
        if document.title in self._memory_store.read_casos_cubiertos():
            return None

        prompt = _PROMPT_TEMPLATE.format(
            title=document.title,
            agency=document.agency,
            extracted_text=document.extracted_text,
        )
        raw_response = self._llm_client.complete(prompt)
        payload = self._parse_json(raw_response)

        score = self._build_score(payload.get("scores", {}))
        advanced = score.total >= ADVANCEMENT_THRESHOLD
        narrative_angle = payload.get("narrative_angle") or None

        if advanced and not narrative_angle:
            raise CurationError(
                "A case scoring at or above the advancement threshold must "
                "include a narrative-angle note."
            )

        self._record(document, score, advanced)

        return CurationResult(
            document=document,
            score=score,
            advanced=advanced,
            narrative_angle=narrative_angle if advanced else None,
        )

    def _parse_json(self, raw_response: str) -> dict:
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError as error:
            raise CurationError(f"LLM response is not valid JSON: {error}") from error

    def _build_score(self, raw_scores: dict) -> CurationScore:
        values = {}
        for criterion in _CRITERIA:
            value = raw_scores.get(criterion)
            if not isinstance(value, int) or not (MIN_CRITERION_SCORE <= value <= MAX_CRITERION_SCORE):
                raise CurationError(
                    f"Criterion '{criterion}' must be an integer between "
                    f"{MIN_CRITERION_SCORE} and {MAX_CRITERION_SCORE}, got {value!r}."
                )
            values[criterion] = value
        return CurationScore(**values)

    def _record(self, document: ScrapedDocument, score: CurationScore, advanced: bool) -> None:
        today = date.today().isoformat()
        outcome = "advanced" if advanced else "discarded"
        self._memory_store.append_caso_cubierto(
            f"{today} | {document.title} | {outcome} | score {score.total}/25"
        )
