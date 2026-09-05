"""
Tests for CasesUseCase — supports the content-admin-panel Covered Cases
view (specs/content-admin-panel/spec.md: "search, browse, and manually
edit the covered-cases history"). casos_cubiertos.md is an append-only,
unstructured text log (one line per evaluated case, written by
CaseCurationUseCase as "{date} | {identifier} | {outcome} | {reason}");
this use case parses it into addressable entries. A case's id is its
1-based line number in the file — stable as long as lines are only edited
in place, never reordered or deleted, which is the only operation this
use case exposes.
"""
from src.editorial.application.cases_use_case import CasesUseCase
from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore


def _store_with_entries(tmp_path, *entries: str) -> ProjectMemoryStore:
    store = ProjectMemoryStore(memory_dir=tmp_path)
    for entry in entries:
        store.append_caso_cubierto(entry)
    return store


def test_lists_all_entries_with_stable_ids(tmp_path):
    store = _store_with_entries(
        tmp_path,
        "2026-09-01 | AARO Report A | advanced | score 18/25",
        "2026-09-02 | AARO Report B | discarded | score 9/25",
    )
    use_case = CasesUseCase(memory_store=store)

    cases = use_case.list_cases()

    assert [c.id for c in cases] == ["1", "2"]
    assert cases[0].date == "2026-09-01"
    assert cases[0].identifier == "AARO Report A"
    assert cases[0].outcome == "advanced"
    assert cases[0].reason == "score 18/25"
    assert cases[1].outcome == "discarded"


def test_list_cases_returns_empty_when_no_entries_exist(tmp_path):
    store = ProjectMemoryStore(memory_dir=tmp_path)
    use_case = CasesUseCase(memory_store=store)

    assert use_case.list_cases() == []


def test_search_filters_by_identifier_substring(tmp_path):
    store = _store_with_entries(
        tmp_path,
        "2026-09-01 | AARO Radar Report | advanced | score 18/25",
        "2026-09-02 | CIA Reading Room File | discarded | score 9/25",
    )
    use_case = CasesUseCase(memory_store=store)

    results = use_case.search_cases("radar")

    assert len(results) == 1
    assert results[0].identifier == "AARO Radar Report"


def test_search_filters_by_reason_substring(tmp_path):
    store = _store_with_entries(
        tmp_path,
        "2026-09-01 | Case A | advanced | military witness corroboration",
        "2026-09-02 | Case B | discarded | insufficient documentation",
    )
    use_case = CasesUseCase(memory_store=store)

    results = use_case.search_cases("insufficient")

    assert len(results) == 1
    assert results[0].identifier == "Case B"


def test_get_case_returns_the_matching_entry(tmp_path):
    store = _store_with_entries(
        tmp_path,
        "2026-09-01 | Case A | advanced | score 18/25",
        "2026-09-02 | Case B | discarded | score 9/25",
    )
    use_case = CasesUseCase(memory_store=store)

    case = use_case.get_case("2")

    assert case is not None
    assert case.identifier == "Case B"


def test_get_case_returns_none_for_unknown_id(tmp_path):
    store = _store_with_entries(tmp_path, "2026-09-01 | Case A | advanced | score 18/25")
    use_case = CasesUseCase(memory_store=store)

    assert use_case.get_case("999") is None


def test_update_case_reason_edits_only_the_targeted_entry(tmp_path):
    store = _store_with_entries(
        tmp_path,
        "2026-09-01 | Case A | advanced | original reason",
        "2026-09-02 | Case B | discarded | untouched reason",
    )
    use_case = CasesUseCase(memory_store=store)

    updated = use_case.update_case_reason("1", "corrected reason")

    assert updated.reason == "corrected reason"
    cases = use_case.list_cases()
    assert cases[0].reason == "corrected reason"
    assert cases[1].reason == "untouched reason"  # unaffected


def test_update_case_reason_raises_for_unknown_id(tmp_path):
    store = _store_with_entries(tmp_path, "2026-09-01 | Case A | advanced | reason")
    use_case = CasesUseCase(memory_store=store)

    import pytest
    from src.editorial.application.cases_use_case import CaseNotFoundError

    with pytest.raises(CaseNotFoundError):
        use_case.update_case_reason("999", "new reason")
