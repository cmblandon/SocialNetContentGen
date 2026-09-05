"""
Tests for CORS configuration — required for the Next.js admin panel
(Phase 6, running on a different origin/port) to call this API from the
browser at all. Not itemized as its own task in tasks.md; added because
the frontend cannot function without it, discovered while wiring up the
Phase 6 E2E environment.
"""
from fastapi.testclient import TestClient

from src.editorial.presentation.app import app


def test_allows_cross_origin_requests_from_the_local_frontend_dev_server():
    client = TestClient(app)

    response = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_preflight_request_is_allowed_for_the_local_frontend_dev_server():
    client = TestClient(app)

    response = client.options(
        "/platform-versions/some-id/approve",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
