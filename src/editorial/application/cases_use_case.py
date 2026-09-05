"""
CasesUseCase — supports the content-admin-panel Covered Cases view
(specs/content-admin-panel/spec.md). Parses the append-only
casos_cubiertos.md log ("{date} | {identifier} | {outcome} | {reason}",
written by CaseCurationUseCase and orchestrator.run_cycle) into
addressable CaseEntry records. A case's id is its 1-based line number —
stable as long as entries are only edited in place, never reordered or
deleted, which is the only mutation this use case exposes.
"""
from dataclasses import dataclass
from typing import Optional

from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore


class CaseNotFoundError(Exception):
    """Raised when an operation targets a case id with no matching line."""


@dataclass
class CaseEntry:
    id: str
    date: str
    identifier: str
    outcome: str
    reason: str


class CasesUseCase:
    def __init__(self, memory_store: ProjectMemoryStore):
        self._memory_store = memory_store

    def list_cases(self) -> list[CaseEntry]:
        content = self._memory_store.read_casos_cubiertos()
        if not content.strip():
            return []
        return [
            self._parse_line(index, line)
            for index, line in enumerate(content.splitlines(), start=1)
            if line.strip()
        ]

    def search_cases(self, query: str) -> list[CaseEntry]:
        query_lower = query.lower()
        return [
            case
            for case in self.list_cases()
            if query_lower in case.identifier.lower() or query_lower in case.reason.lower()
        ]

    def get_case(self, case_id: str) -> Optional[CaseEntry]:
        return next((case for case in self.list_cases() if case.id == case_id), None)

    def update_case_reason(self, case_id: str, new_reason: str) -> CaseEntry:
        cases = self.list_cases()
        target = next((case for case in cases if case.id == case_id), None)
        if target is None:
            raise CaseNotFoundError(f"No case found with id '{case_id}'.")

        target.reason = new_reason
        rewritten_content = "\n".join(self._format_line(case) for case in cases) + "\n"
        self._memory_store.write_casos_cubiertos(rewritten_content)

        return target

    def _parse_line(self, line_number: int, line: str) -> CaseEntry:
        parts = [part.strip() for part in line.split("|", maxsplit=3)]
        date, identifier, outcome, reason = (parts + ["", "", "", ""])[:4]
        return CaseEntry(id=str(line_number), date=date, identifier=identifier, outcome=outcome, reason=reason)

    def _format_line(self, case: CaseEntry) -> str:
        return f"{case.date} | {case.identifier} | {case.outcome} | {case.reason}"
