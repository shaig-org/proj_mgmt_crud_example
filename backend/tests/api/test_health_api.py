"""Tests for health check endpoint."""

from fastapi.testclient import TestClient

from tests.conftest import client  # noqa: F401


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_check_returns_healthy(self, client: TestClient) -> None:
        """Test health check endpoint returns healthy status."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
