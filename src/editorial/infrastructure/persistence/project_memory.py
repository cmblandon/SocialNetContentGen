"""
ProjectMemoryStore — the orchestrator's project memory, per the proposal's
orchestrator prompt and specs/editorial-orchestration/spec.md ("Maintain
project memory across cycles"):

  - casos_cubiertos.md: every document evaluated (advanced or discarded),
    so nothing is reprocessed.
  - calendario.md: what was published/scheduled, when, on which network.
  - manual_de_marca.md: tone, editorial red lines, example hooks that
    worked — authored/edited by a human, read-only from the orchestrator's
    side.

Implemented as plain files on disk rather than routed through deepagents'
internal virtual-filesystem backend, so this bookkeeping is deterministic
and testable independent of the LLM (consistent with design.md Decision 6's
preference for structural enforcement over relying on agent behavior).
"""
from pathlib import Path

_CASOS_CUBIERTOS_FILENAME = "casos_cubiertos.md"
_CALENDARIO_FILENAME = "calendario.md"
_MANUAL_DE_MARCA_FILENAME = "manual_de_marca.md"


class ProjectMemoryStore:
    def __init__(self, memory_dir: Path):
        self._memory_dir = Path(memory_dir)
        self._memory_dir.mkdir(parents=True, exist_ok=True)

    def read_casos_cubiertos(self) -> str:
        return self._read(_CASOS_CUBIERTOS_FILENAME)

    def append_caso_cubierto(self, entry: str) -> None:
        self._append(_CASOS_CUBIERTOS_FILENAME, entry)

    def read_calendario(self) -> str:
        return self._read(_CALENDARIO_FILENAME)

    def append_calendario_entry(self, entry: str) -> None:
        self._append(_CALENDARIO_FILENAME, entry)

    def read_manual_de_marca(self) -> str:
        return self._read(_MANUAL_DE_MARCA_FILENAME)

    def _read(self, filename: str) -> str:
        path = self._memory_dir / filename
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _append(self, filename: str, entry: str) -> None:
        path = self._memory_dir / filename
        with path.open("a", encoding="utf-8") as f:
            f.write(entry.rstrip("\n") + "\n")
