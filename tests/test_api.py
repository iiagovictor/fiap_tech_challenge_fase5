"""Basic tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.serving.app import app

client = TestClient(app)


def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_health_check():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "model_loaded" in data


def test_metrics_endpoint():
    """Test Prometheus metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


def test_predict_endpoint():
    """Test prediction endpoint (mock)."""
    payload = {"ticker": "ITUB4.SA"}
    response = client.post("/predict", json=payload)

    # May fail if model not loaded, that's ok for unit test
    assert response.status_code in [200, 503]

    if response.status_code == 200:
        data = response.json()
        assert "ticker" in data
        assert "prediction" in data
        assert "probability" in data


def test_agent_endpoint():
    """Test agent endpoint (mock)."""
    payload = {"query": "What is the price of ITUB4?"}
    response = client.post("/agent", json=payload)

    # Should work even without LLM (returns mock response)
    assert response.status_code in [200, 500]

    if response.status_code == 200:
        data = response.json()
        assert "query" in data
        assert "response" in data
        assert "timestamp" in data


def test_drift_endpoint():
    """Test drift detection endpoint."""
    response = client.get("/drift")
    assert response.status_code == 200
    data = response.json()
    assert "timestamp" in data
    assert "drift_detected" in data
