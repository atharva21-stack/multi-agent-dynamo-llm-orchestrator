"""Integration tests for the FastAPI endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app


@pytest.fixture
def mock_orchestrator():
    orch = MagicMock()
    orch.submit_request = AsyncMock(return_value={
        "request_id": "test-request-id-123",
        "estimated_tokens": 5000,
        "estimated_cost_usd": 0.075,
    })
    orch.get_request_state = AsyncMock(return_value={
        "request_id": "test-request-id-123",
        "status": "completed",
        "user_request": "Test request",
        "result": {"output": "Test result"},
        "agent_results": [],
        "total_tokens": 4500,
        "total_cost_usd": 0.068,
        "duration_ms": 5000.0,
        "error": None,
        "created_at": None,
        "completed_at": None,
    })
    orch.get_metrics = AsyncMock(return_value={
        "total_requests": 100,
        "successful_requests": 95,
        "failed_requests": 5,
        "avg_latency_ms": 8000.0,
        "p95_latency_ms": 15000.0,
        "p99_latency_ms": 25000.0,
        "total_tokens": 500000,
        "total_cost_usd": 15.0,
        "agent_metrics": [],
    })
    return orch


@pytest.fixture
def test_client(mock_orchestrator):
    app = create_app()
    app.state.orchestrator = mock_orchestrator
    app.state.redis = None
    app.state.environment = "test"
    with TestClient(app) as client:
        yield client


@pytest.mark.integration
class TestProcessEndpoint:
    def test_submit_valid_request(self, test_client):
        response = test_client.post(
            "/api/v1/process",
            json={"request": "Research the top 5 SaaS companies and their market share analysis"},
        )
        assert response.status_code == 202
        data = response.json()
        assert "request_id" in data
        assert data["status"] == "pending"

    def test_submit_too_short_request(self, test_client):
        response = test_client.post(
            "/api/v1/process",
            json={"request": "short"},
        )
        assert response.status_code == 422

    def test_submit_with_context(self, test_client):
        response = test_client.post(
            "/api/v1/process",
            json={
                "request": "Research the enterprise CRM market in North America",
                "context": {"region": "NA"},
                "priority": 5,
            },
        )
        assert response.status_code == 202


@pytest.mark.integration
class TestStatusEndpoint:
    def test_get_existing_status(self, test_client):
        response = test_client.get("/api/v1/status/test-request-id-123")
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == "test-request-id-123"
        assert data["status"] == "completed"

    def test_get_nonexistent_status(self, test_client, mock_orchestrator):
        from unittest.mock import AsyncMock
        mock_orchestrator.get_request_state = AsyncMock(side_effect=KeyError("not found"))
        response = test_client.get("/api/v1/status/nonexistent-id")
        assert response.status_code == 404


@pytest.mark.integration
class TestMetricsEndpoint:
    def test_get_metrics(self, test_client):
        response = test_client.get("/api/v1/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "total_tokens" in data


@pytest.mark.integration
class TestHealthEndpoint:
    def test_health_check(self, test_client):
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data

    def test_root_endpoint(self, test_client):
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "agent-inference-stack"
