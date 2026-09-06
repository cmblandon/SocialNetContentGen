"""
Tests for the source-URL list endpoints — GET/POST /research/sources and
POST /research/sources/delete — per enhance-admin-panel-ui design.md
Decision 3: the Configuración view's backing API for the list of URLs a
pipeline run (POST /research/run) targets. A POST .../delete rather than
DELETE with a body, per design.md's note on inconsistent cross-client
support for bodies on DELETE requests.
"""
import pytest
from fastapi.testclient import TestClient

from src.editorial.infrastructure.persistence.project_memory import ProjectMemoryStore
from src.editorial.presentation.app import app
from src.editorial.presentation.dependencies import get_memory_store


@pytest.fixture
def client(tmp_path):
    app.dependency_overrides[get_memory_store] = lambda: ProjectMemoryStore(memory_dir=tmp_path)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_source_urls_starts_empty(client):
    response = client.get("/research/sources")

    assert response.status_code == 200
    assert response.json() == {"source_urls": []}


def test_add_source_url_then_list_includes_it(client):
    response = client.post("/research/sources", json={"url": "https://www.aaro.mil/reports/2024.pdf"})

    assert response.status_code == 200

    list_response = client.get("/research/sources")
    assert list_response.json() == {"source_urls": ["https://www.aaro.mil/reports/2024.pdf"]}


def test_adding_a_duplicate_source_url_does_not_duplicate_it(client):
    client.post("/research/sources", json={"url": "https://example.com/a"})
    client.post("/research/sources", json={"url": "https://example.com/a"})

    response = client.get("/research/sources")
    assert response.json() == {"source_urls": ["https://example.com/a"]}


def test_remove_source_url(client):
    client.post("/research/sources", json={"url": "https://example.com/a"})
    client.post("/research/sources", json={"url": "https://example.com/b"})

    response = client.post("/research/sources/delete", json={"url": "https://example.com/a"})

    assert response.status_code == 200
    assert client.get("/research/sources").json() == {"source_urls": ["https://example.com/b"]}
