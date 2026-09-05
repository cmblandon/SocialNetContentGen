"""
Tests for CaseCurationUseCase — per specs/case-curation/spec.md. Scoring
is inherently judgment-based (novelty, narrative potential, ...), so it's
delegated to the LLM like story-writing/platform-adaptation; this use case
validates the LLM's scores, enforces the >=15/25 threshold, and — the part
that must never depend on the LLM behaving correctly — permanently records
every evaluated case (advanced or discarded) in /casos_cubiertos.md.
"""
import json

import pytest

from src.editorial.application.case_curation_use_case import (
    ADVANCEMENT_THRESHOLD,
    CaseCurationUseCase,
    CurationError,
)
from src.editorial.core.ports import ScrapedDocument
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore


class FakeLLMClient:
    def __init__(self, response_text: str):
        self._response_text = response_text
        self.last_prompt: str | None = None

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response_text


def _document() -> ScrapedDocument:
    return ScrapedDocument(
        title="AARO 2024 Annual Report",
        agency="AARO",
        doc_type="report",
        extracted_text="A pilot reported an unidentified radar contact, classified for 40 years.",
    )


def _payload(**scores) -> dict:
    defaults = dict(
        novedad=4,
        potencial_narrativo=4,
        respaldo_documental=4,
        elemento_visual=3,
        encaje_audiencia=3,
    )
    defaults.update(scores)
    return {"scores": defaults, "narrative_angle": "military witness + radar corroboration"}


def _use_case(payload: dict, tmp_path) -> tuple[CaseCurationUseCase, ProjectMemoryStore]:
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    llm = FakeLLMClient(json.dumps(payload))
    return CaseCurationUseCase(llm_client=llm, memory_store=memory_store), memory_store


def test_advances_a_document_scoring_at_or_above_the_threshold(tmp_path):
    payload = _payload()  # 4+4+4+3+3 = 18
    use_case, memory_store = _use_case(payload, tmp_path)
    assert sum(payload["scores"].values()) >= ADVANCEMENT_THRESHOLD

    result = use_case.curate(_document())

    assert result.advanced is True
    assert result.narrative_angle == "military witness + radar corroboration"
    assert result.score.total == 18
    assert "advanced" in memory_store.read_casos_cubiertos()


def test_discards_a_document_scoring_below_the_threshold(tmp_path):
    payload = _payload(novedad=1, potencial_narrativo=1, respaldo_documental=1, elemento_visual=1, encaje_audiencia=1)
    use_case, memory_store = _use_case(payload, tmp_path)

    result = use_case.curate(_document())

    assert result.advanced is False
    assert result.narrative_angle is None
    assert "discarded" in memory_store.read_casos_cubiertos()


def test_raises_when_a_score_is_out_of_the_1_to_5_range(tmp_path):
    payload = _payload(novedad=6)
    use_case, _ = _use_case(payload, tmp_path)

    with pytest.raises(CurationError):
        use_case.curate(_document())


def test_raises_when_advanced_but_narrative_angle_is_missing(tmp_path):
    payload = _payload()
    payload["narrative_angle"] = ""
    use_case, _ = _use_case(payload, tmp_path)

    with pytest.raises(CurationError):
        use_case.curate(_document())


def test_skips_rescoring_a_document_already_recorded(tmp_path):
    memory_store = ProjectMemoryStore(memory_dir=tmp_path)
    memory_store.append_caso_cubierto("2026-09-01 | AARO 2024 Annual Report | advanced | score 18/25")
    llm = FakeLLMClient(json.dumps(_payload()))
    use_case = CaseCurationUseCase(llm_client=llm, memory_store=memory_store)

    result = use_case.curate(_document())

    assert result is None
    assert llm.last_prompt is None


def test_prompt_includes_document_fields(tmp_path):
    payload = _payload()
    use_case, _ = _use_case(payload, tmp_path)
    document = _document()

    use_case.curate(document)

    prompt = use_case._llm_client.last_prompt  # noqa: SLF001 (test-only introspection)
    assert document.title in prompt
    assert document.agency in prompt
    assert document.extracted_text in prompt


def test_records_the_total_score_in_the_memory_entry(tmp_path):
    payload = _payload()  # total 18
    use_case, memory_store = _use_case(payload, tmp_path)

    use_case.curate(_document())

    assert "18/25" in memory_store.read_casos_cubiertos()
