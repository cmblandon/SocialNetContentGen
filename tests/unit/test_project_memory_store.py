"""
Tests for ProjectMemoryStore — the orchestrator's project memory
(casos_cubiertos.md, calendario.md, manual_de_marca.md), per the
orchestrator prompt in the proposal and specs/editorial-orchestration/spec.md
("Maintain project memory across cycles"). Kept as plain, directly-tested
file I/O rather than routed through deepagents' internal virtual-filesystem
backend, so the read-at-start/update-at-end behavior is deterministic and
easy to verify independent of the LLM.
"""
from src.editorial.infrastructure.persistence.project_memory import (
    ProjectMemoryStore,
)


def test_reading_casos_cubiertos_before_any_entry_returns_empty(tmp_path):
    store = ProjectMemoryStore(memory_dir=tmp_path)

    assert store.read_casos_cubiertos() == ""


def test_appending_a_caso_cubierto_makes_it_readable(tmp_path):
    store = ProjectMemoryStore(memory_dir=tmp_path)

    store.append_caso_cubierto("2026-09-04 | doc-123 | advanced | score 18/25")

    content = store.read_casos_cubiertos()
    assert "2026-09-04 | doc-123 | advanced | score 18/25" in content


def test_appending_multiple_casos_preserves_earlier_entries(tmp_path):
    store = ProjectMemoryStore(memory_dir=tmp_path)

    store.append_caso_cubierto("entry one")
    store.append_caso_cubierto("entry two")

    content = store.read_casos_cubiertos()
    assert "entry one" in content
    assert "entry two" in content
    assert content.index("entry one") < content.index("entry two")


def test_casos_cubiertos_persists_to_a_real_file_on_disk(tmp_path):
    store = ProjectMemoryStore(memory_dir=tmp_path)
    store.append_caso_cubierto("entry one")

    reopened_store = ProjectMemoryStore(memory_dir=tmp_path)

    assert "entry one" in reopened_store.read_casos_cubiertos()


def test_reading_calendario_before_any_entry_returns_empty(tmp_path):
    store = ProjectMemoryStore(memory_dir=tmp_path)

    assert store.read_calendario() == ""


def test_appending_a_calendario_entry_makes_it_readable(tmp_path):
    store = ProjectMemoryStore(memory_dir=tmp_path)

    store.append_calendario_entry("2026-09-04 10:00 | tiktok | chapter-1 | post_id abc123")

    assert "post_id abc123" in store.read_calendario()


def test_reading_manual_de_marca_before_it_exists_returns_empty(tmp_path):
    store = ProjectMemoryStore(memory_dir=tmp_path)

    assert store.read_manual_de_marca() == ""


def test_reading_manual_de_marca_returns_manually_authored_content(tmp_path):
    (tmp_path / "manual_de_marca.md").write_text("# Tone\nNever sensationalize.\n")

    store = ProjectMemoryStore(memory_dir=tmp_path)

    assert "Never sensationalize." in store.read_manual_de_marca()
