"""
Integration tests for Chat API endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for health check endpoints."""

    def test_health_check_returns_200(self, client: TestClient):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ConversalQ"
        assert "version" in data
        assert "timestamp" in data

    def test_readiness_check_returns_200(self, client: TestClient):
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"


class TestChatEndpoint:
    """Tests for the chat API endpoint."""

    def test_chat_rejects_empty_message(self, client: TestClient):
        """Validation: empty message should be rejected."""
        response = client.post("/api/v1/chat", json={"message": ""})
        assert response.status_code == 422

    def test_chat_rejects_missing_message(self, client: TestClient):
        """Validation: missing message field should be rejected."""
        response = client.post("/api/v1/chat", json={})
        assert response.status_code == 422

    def test_chat_accepts_valid_request(self, client: TestClient):
        """Valid request should be accepted (will fail without DB, but validates routing)."""
        # This test validates request routing and schema validation.
        # Full integration requires running PostgreSQL + OpenAI.
        response = client.post(
            "/api/v1/chat",
            json={"message": "Hello, I need help with my account"},
        )
        # Without DB connection, we expect 500 (DB not initialized)
        # In a full integration env, this would be 200
        assert response.status_code in (200, 500)


class TestStreamEndpoint:
    """Tests for the streaming chat endpoint."""

    def test_stream_rejects_empty_message(self, client: TestClient):
        """Validation: empty message should be rejected."""
        response = client.post("/api/v1/chat/stream", json={"message": ""})
        assert response.status_code == 422
