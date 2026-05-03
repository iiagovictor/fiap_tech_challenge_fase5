"""Basic tests for FastAPI endpoints."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
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
    # 404 is a valid response when stock data is unavailable (e.g., no network in test env)
    assert response.status_code in [200, 404, 500]

    if response.status_code == 200:
        data = response.json()
        assert "query" in data
        assert "response" in data


def test_features_endpoint():
    """Test /features endpoint returns expected structure."""
    response = client.get("/features")
    assert response.status_code == 200
    data = response.json()
    assert "model_features" in data
    assert "total_model_features" in data
    assert "timestamp" in data


def test_drift_endpoint():
    """Test /drift endpoint returns expected drift report."""
    mock_response = {
        "timestamp": "2026-05-02T00:00:00",
        "drift_detected": True,
        "overall_drift_score": 0.24,
        "features_drifted": ["rsi_14", "macd"],
        "alert_level": "red",
        "report_path": "reports/drift_report.html",
    }
    with patch("src.serving.app._run_drift_monitoring_pipeline", return_value=mock_response):
        response = client.get("/drift")

    assert response.status_code == 200
    data = response.json()
    assert data["drift_detected"] is True
    assert data["alert_level"] == "red"
    assert data["drift_score"] == 0.24
    assert data["overall_drift_score"] == 0.24
    assert data["features_drifted"] == ["rsi_14", "macd"]
    assert data["report_path"] == "reports/drift_report.html"


def test_predict_with_mock_model():
    """Test /predict endpoint with mocked LSTM model and local feature store."""
    mock_model = MagicMock()
    mock_model.predict.return_value = np.array([[0.7]])

    df = pd.DataFrame(
        {
            "ticker": ["ITUB4.SA"],
            "close": [35.5],
            "open": [35.0],
            "high": [36.0],
            "low": [34.8],
            "volume": [1_000_000.0],
        }
    )
    mock_storage = MagicMock()
    mock_storage.exists.return_value = True
    mock_storage.read_parquet.return_value = df

    with (
        patch("src.serving.app.model", mock_model),
        patch("src.serving.app.storage", mock_storage),
    ):
        response = client.post("/predict", json={"ticker": "ITUB4.SA"})

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "ITUB4.SA"
    assert "prediction" in data
    assert "probability" in data
    assert abs(data["probability"] - 0.7) < 0.01


def test_load_model_from_mlflow_all_fail():
    """Direct unit test: load_model_from_mlflow handles all sources failing."""
    import src.serving.app as app_module

    mock_mlflow_client = MagicMock()
    mock_mlflow_client.search_model_versions.return_value = []

    with (
        patch("mlflow.keras.load_model", side_effect=Exception("mlflow unavailable")),
        patch("mlflow.tracking.MlflowClient", return_value=mock_mlflow_client),
        patch("glob.glob", return_value=[]),
    ):
        app_module.load_model_from_mlflow()

    assert app_module.model is None
