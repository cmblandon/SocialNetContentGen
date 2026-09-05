from fastapi.testclient import TestClient

from src.editorial.presentation.app import app


def test_health_check_returns_ok():
    """Requirement 1.8: GET /health confirms the editorial FastAPI service is up."""
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
