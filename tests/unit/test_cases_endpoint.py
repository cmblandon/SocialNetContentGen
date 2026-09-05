"""
Tests for GET /cases and PATCH /cases/{id} — the content-admin-panel
Covered Cases view's backend (specs/content-admin-panel/spec.md: "search,
browse, and manually edit the covered-cases history").
"""
import pytest
from fastapi.testclient import TestClient

from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore
from src.editorial.presentation.app import app
from src.editorial.presentation.dependencies import get_memory_store


@pytest.fixture
def memory_store(tmp_path):
    return ProjectMemoryStore(memory_dir=tmp_path)


@pytest.fixture
def client(memory_store):
    app.dependency_overrides[get_memory_store] = lambda: memory_store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_cases_returns_all_entries(client, memory_store):
    memory_store.append_caso_cubierto("2026-09-01 | AARO Report A | advanced | score 18/25")
    memory_store.append_caso_cubierto("2026-09-02 | AARO Report B | discarded | score 9/25")

    response = client.get("/cases")

    assert response.status_code == 200
    cases = response.json()
    assert len(cases) == 2
    assert cases[0]["identifier"] == "AARO Report A"


def test_get_cases_with_query_filters_results(client, memory_store):
    memory_store.append_caso_cubierto("2026-09-01 | AARO Radar Report | advanced | score 18/25")
    memory_store.append_caso_cubierto("2026-09-02 | CIA Reading Room File | discarded | score 9/25")

    response = client.get("/cases", params={"q": "radar"})

    assert response.status_code == 200
    cases = response.json()
    assert len(cases) == 1
    assert cases[0]["identifier"] == "AARO Radar Report"


def test_get_cases_returns_empty_list_when_none_exist(client):
    response = client.get("/cases")

    assert response.status_code == 200
    assert response.json() == []


def test_patch_case_updates_the_reason(client, memory_store):
    memory_store.append_caso_cubierto("2026-09-01 | AARO Report A | advanced | original reason")

    response = client.patch("/cases/1", json={"reason": "corrected reason"})

    assert response.status_code == 200
    assert response.json()["reason"] == "corrected reason"
    assert "corrected reason" in memory_store.read_casos_cubiertos()


def test_patch_case_unknown_id_returns_404(client, memory_store):
    memory_store.append_caso_cubierto("2026-09-01 | AARO Report A | advanced | reason")

    response = client.patch("/cases/999", json={"reason": "new reason"})

    assert response.status_code == 404
