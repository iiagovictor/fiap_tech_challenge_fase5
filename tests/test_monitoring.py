"""Tests for monitoring (Prometheus metrics, drift) and baseline models and storage."""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Prometheus Metrics
# ──────────────────────────────────────────────────────────────────────────────


def _labeled_mock():
    """MagicMock where .labels(...) returns self, so .labels(...).inc() works."""
    m = MagicMock()
    m.labels.return_value = m
    return m


_METRICS_PATCH = dict(
    MODEL_PREDICTIONS_TOTAL=_labeled_mock(),
    MODEL_PREDICTION_LATENCY=_labeled_mock(),
    PREDICTION_CONFIDENCE=_labeled_mock(),
    MODEL_PREDICTION_ERRORS=_labeled_mock(),
    FEATURE_RETRIEVAL_LATENCY=_labeled_mock(),
    DATA_DRIFT_SCORE=_labeled_mock(),
    LLM_REQUEST_LATENCY=_labeled_mock(),
    LLM_TOKENS_USED=_labeled_mock(),
    AGENT_TOOL_CALLS=_labeled_mock(),
    GUARDRAIL_VIOLATIONS=_labeled_mock(),
    PII_DETECTIONS=_labeled_mock(),
)


class TestPrometheusMetrics:
    """Tests for monitoring/metrics.py helper functions (mocked Prometheus objects)."""

    @pytest.fixture(autouse=True)
    def patch_prom_globals(self):
        """Replace every module-level Prometheus object with a fresh MagicMock."""
        mocks = {k: _labeled_mock() for k in _METRICS_PATCH}
        with patch.multiple("src.monitoring.metrics", **mocks):
            self._mocks = mocks
            yield

    def test_track_prediction_success(self):
        from src.monitoring.metrics import track_prediction

        track_prediction("lstm", "1", latency=0.05, confidence=0.75)
        self._mocks["MODEL_PREDICTIONS_TOTAL"].labels.assert_called_once()
        self._mocks["MODEL_PREDICTION_LATENCY"].observe.assert_called_once_with(0.05)
        self._mocks["PREDICTION_CONFIDENCE"].observe.assert_called_once_with(0.75)

    def test_track_prediction_with_error(self):
        from src.monitoring.metrics import track_prediction

        track_prediction("lstm", "1", latency=0.05, confidence=0.75, error="timeout")
        self._mocks["MODEL_PREDICTION_ERRORS"].labels.assert_called_once()

    def test_track_prediction_no_error_field_not_called(self):
        from src.monitoring.metrics import track_prediction

        track_prediction("baseline", "2", latency=0.01, confidence=0.51)
        self._mocks["MODEL_PREDICTION_ERRORS"].labels.assert_not_called()

    def test_track_feature_retrieval_online(self):
        from src.monitoring.metrics import track_feature_retrieval

        track_feature_retrieval("online", latency=0.003)
        self._mocks["FEATURE_RETRIEVAL_LATENCY"].labels.assert_called_once_with(store_type="online")

    def test_track_feature_retrieval_offline(self):
        from src.monitoring.metrics import track_feature_retrieval

        track_feature_retrieval("offline", latency=0.5)
        self._mocks["FEATURE_RETRIEVAL_LATENCY"].labels.assert_called_once_with(
            store_type="offline"
        )

    def test_track_data_drift(self):
        from src.monitoring.metrics import track_data_drift

        track_data_drift("rsi_14", drift_score=0.12)
        track_data_drift("macd", drift_score=0.25)
        assert self._mocks["DATA_DRIFT_SCORE"].labels.call_count == 2

    def test_track_data_drift_zero(self):
        from src.monitoring.metrics import track_data_drift

        track_data_drift("sma_20", drift_score=0.0)
        self._mocks["DATA_DRIFT_SCORE"].labels.assert_called_once_with(feature_name="sma_20")

    def test_track_llm_request(self):
        from src.monitoring.metrics import track_llm_request

        track_llm_request("gemini", latency=1.2, input_tokens=150, output_tokens=400)
        self._mocks["LLM_REQUEST_LATENCY"].labels.assert_called_once()
        assert self._mocks["LLM_TOKENS_USED"].labels.call_count == 2

    def test_track_llm_request_small(self):
        from src.monitoring.metrics import track_llm_request

        track_llm_request("ollama/llama3", latency=3.5, input_tokens=50, output_tokens=100)
        self._mocks["LLM_REQUEST_LATENCY"].labels.assert_called_once_with(
            model_name="ollama/llama3"
        )

    def test_track_tool_call(self):
        from src.monitoring.metrics import track_tool_call

        for tool in (
            "predict_stock_direction",
            "get_stock_price_history",
            "calculate_technical_indicators",
            "compare_stocks",
        ):
            track_tool_call(tool)
        assert self._mocks["AGENT_TOOL_CALLS"].labels.call_count == 4

    def test_track_guardrail_violation_types(self):
        from src.monitoring.metrics import track_guardrail_violation

        for vtype in ("prompt_injection", "toxic_content", "pii_detected", "token_limit_exceeded"):
            track_guardrail_violation(vtype)
        assert self._mocks["GUARDRAIL_VIOLATIONS"].labels.call_count == 4

    def test_track_pii_detection_types(self):
        from src.monitoring.metrics import track_pii_detection

        for ptype in ("EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON", "CREDIT_CARD"):
            track_pii_detection(ptype)
        assert self._mocks["PII_DETECTIONS"].labels.call_count == 4


# ──────────────────────────────────────────────────────────────────────────────
# Drift Detection
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def reference_df():
    """Reference dataset with numeric features."""
    rng = np.random.default_rng(42)
    n = 200
    return pd.DataFrame(
        {
            "rsi_14": rng.uniform(20, 80, n),
            "macd": rng.normal(0, 1, n),
            "sma_20": rng.normal(30, 5, n),
            "ema_12": rng.normal(30, 5, n),
            "target": rng.integers(0, 2, n),
        }
    )


@pytest.fixture
def current_df():
    """Current dataset with similar distribution."""
    rng = np.random.default_rng(99)
    n = 80
    return pd.DataFrame(
        {
            "rsi_14": rng.uniform(20, 80, n),
            "macd": rng.normal(0, 1, n),
            "sma_20": rng.normal(30, 5, n),
            "ema_12": rng.normal(30, 5, n),
            "target": rng.integers(0, 2, n),
        }
    )


class TestDriftDetection:
    def test_detect_drift_returns_expected_keys(self, reference_df, current_df, tmp_path):
        from src.monitoring.drift import detect_drift

        result = detect_drift(
            reference_df,
            current_df,
            output_path=str(tmp_path / "drift_report.html"),
        )

        assert "drift_detected" in result
        assert "overall_drift_score" in result
        assert "features_drifted" in result
        assert "drift_scores" in result
        assert "alert_level" in result
        assert "report_path" in result
        assert "timestamp" in result

    def test_detect_drift_html_saved(self, reference_df, current_df, tmp_path):
        from src.monitoring.drift import detect_drift

        out = tmp_path / "report.html"
        detect_drift(reference_df, current_df, output_path=str(out))
        assert out.exists()
        assert out.stat().st_size > 0

    def test_detect_drift_specific_features(self, reference_df, current_df, tmp_path):
        from src.monitoring.drift import detect_drift

        result = detect_drift(
            reference_df,
            current_df,
            feature_columns=["rsi_14", "macd"],
            output_path=str(tmp_path / "r2.html"),
        )
        assert isinstance(result["overall_drift_score"], float)
        assert result["alert_level"] in ("green", "yellow", "red")

    def test_detect_drift_score_range(self, reference_df, current_df, tmp_path):
        from src.monitoring.drift import detect_drift

        result = detect_drift(
            reference_df,
            current_df,
            output_path=str(tmp_path / "r3.html"),
        )
        assert 0.0 <= result["overall_drift_score"] <= 1.0

    def test_detect_drift_no_target_column(self, tmp_path):
        from src.monitoring.drift import detect_drift

        rng = np.random.default_rng(0)
        ref = pd.DataFrame({"rsi_14": rng.uniform(20, 80, 100), "macd": rng.normal(0, 1, 100)})
        cur = pd.DataFrame({"rsi_14": rng.uniform(20, 80, 50), "macd": rng.normal(0, 1, 50)})
        result = detect_drift(ref, cur, output_path=str(tmp_path / "r4.html"))
        assert "drift_detected" in result

    def test_detect_drift_high_drift_returns_result(self, tmp_path):
        """Test that heavily drifted data still returns a complete result dict."""
        from src.monitoring.drift import detect_drift

        rng = np.random.default_rng(42)
        ref = pd.DataFrame(
            {
                "rsi_14": rng.uniform(20, 40, 200),
                "macd": rng.normal(0, 0.1, 200),
                "sma_20": rng.normal(10, 1, 200),
                "ema_12": rng.normal(10, 1, 200),
            }
        )
        rng2 = np.random.default_rng(99)
        cur = pd.DataFrame(
            {
                "rsi_14": rng2.uniform(70, 99, 100),
                "macd": rng2.normal(50, 5, 100),
                "sma_20": rng2.normal(200, 10, 100),
                "ema_12": rng2.normal(200, 10, 100),
            }
        )
        result = detect_drift(ref, cur, output_path=str(tmp_path / "high_drift.html"))
        assert "alert_level" in result
        assert isinstance(result["alert_level"], str)


# ──────────────────────────────────────────────────────────────────────────────
# Baseline Models
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def baseline_df():
    """DataFrame suitable for baseline model training."""
    rng = np.random.default_rng(42)
    n = 300
    close = rng.normal(30, 5, n)
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=n),
            "ticker": "ITUB4.SA",
            "open": rng.normal(30, 5, n),
            "high": rng.normal(32, 5, n),
            "low": rng.normal(28, 5, n),
            "close": close,
            "volume": rng.integers(100_000, 1_000_000, n),
            "sma_5": rng.normal(30, 5, n),
            "sma_10": rng.normal(30, 5, n),
            "sma_20": rng.normal(30, 5, n),
            "sma_50": rng.normal(30, 5, n),
            "ema_12": rng.normal(30, 5, n),
            "ema_26": rng.normal(30, 5, n),
            "rsi_14": rng.uniform(20, 80, n),
            "macd": rng.normal(0, 1, n),
            "macd_signal": rng.normal(0, 0.5, n),
            "macd_histogram": rng.normal(0, 0.5, n),
            "bb_upper": rng.normal(35, 5, n),
            "bb_middle": rng.normal(30, 5, n),
            "bb_lower": rng.normal(25, 5, n),
            "bb_width": rng.uniform(0.05, 0.3, n),
            "atr_14": rng.uniform(0.5, 3.0, n),
            "obv": rng.normal(0, 1_000_000, n),
            "volume_ma_20": rng.integers(100_000, 1_000_000, n).astype(float),
            "price_change": rng.normal(0, 0.02, n),
            "price_change_5d": rng.normal(0, 0.05, n),
            "target": rng.integers(0, 2, n),
        }
    )


class TestBaselineModels:
    def test_train_returns_both_models(self, baseline_df):
        from src.models.baseline import train_baseline_models

        with patch("src.models.baseline.storage") as mock_storage:
            mock_storage.read_parquet.return_value = baseline_df
            result = train_baseline_models()

        assert "logistic_regression" in result
        assert "random_forest" in result

    def test_logistic_regression_metrics(self, baseline_df):
        from src.models.baseline import train_baseline_models

        with patch("src.models.baseline.storage") as mock_storage:
            mock_storage.read_parquet.return_value = baseline_df
            result = train_baseline_models()

        lr = result["logistic_regression"]
        for metric in ("accuracy", "precision", "recall", "f1_score", "roc_auc"):
            assert metric in lr
            assert 0.0 <= lr[metric] <= 1.0

    def test_random_forest_metrics(self, baseline_df):
        from src.models.baseline import train_baseline_models

        with patch("src.models.baseline.storage") as mock_storage:
            mock_storage.read_parquet.return_value = baseline_df
            result = train_baseline_models()

        rf = result["random_forest"]
        for metric in ("accuracy", "precision", "recall", "f1_score", "roc_auc"):
            assert metric in rf
            assert 0.0 <= rf[metric] <= 1.0


# ──────────────────────────────────────────────────────────────────────────────
# Storage Client (local backend)
# ──────────────────────────────────────────────────────────────────────────────


class TestStorageClientLocal:
    """Integration tests using the local filesystem backend."""

    def _make_client(self, tmp_path):
        """Create a StorageClient pointed at tmp_path."""
        from src.config.settings import Settings
        from src.config.storage import StorageClient

        test_settings = Settings(
            storage_backend="local",
            storage_uri=str(tmp_path) + "/",
        )
        with patch("src.config.storage.settings", test_settings):
            client = StorageClient()
        return client

    def test_write_read_parquet(self, tmp_path):
        client = self._make_client(tmp_path)
        df = pd.DataFrame({"a": [1, 2, 3], "b": [1.0, 2.0, 3.0]})
        client.write_parquet(df, "data/test.parquet")
        result = client.read_parquet("data/test.parquet")
        pd.testing.assert_frame_equal(df, result)

    def test_write_read_json(self, tmp_path):
        client = self._make_client(tmp_path)
        obj = {"key": "value", "number": 42, "list": [1, 2, 3]}
        client.write_json(obj, "meta/config.json")
        result = client.read_json("meta/config.json")
        assert result == obj

    def test_write_read_text(self, tmp_path):
        client = self._make_client(tmp_path)
        text = "Hello, world!\nLine 2"
        client.write_text(text, "logs/message.txt")
        result = client.read_text("logs/message.txt")
        assert result == text

    def test_write_read_bytes(self, tmp_path):
        client = self._make_client(tmp_path)
        data = b"\x00\x01\x02\x03binary data"
        client.write_bytes(data, "bin/data.bin")
        result = client.read_bytes("bin/data.bin")
        assert result == data

    def test_exists_true(self, tmp_path):
        client = self._make_client(tmp_path)
        client.write_text("content", "exist_test.txt")
        assert client.exists("exist_test.txt")

    def test_exists_false(self, tmp_path):
        client = self._make_client(tmp_path)
        assert not client.exists("does_not_exist.txt")

    def test_write_read_csv(self, tmp_path):
        client = self._make_client(tmp_path)
        df = pd.DataFrame({"x": [10, 20], "y": ["a", "b"]})
        client.write_csv(df, "data/test.csv")
        result = client.read_csv("data/test.csv")
        assert list(result.columns) == ["x", "y"]
        assert len(result) == 2

    def test_write_read_joblib(self, tmp_path):
        from sklearn.linear_model import LogisticRegression

        client = self._make_client(tmp_path)
        lr = LogisticRegression()
        client.write_joblib(lr, "models/lr.pkl")
        loaded = client.read_joblib("models/lr.pkl")
        assert isinstance(loaded, LogisticRegression)

    def test_makedirs_and_ls(self, tmp_path):
        client = self._make_client(tmp_path)
        client.makedirs("subdir/nested")
        client.write_text("file content", "subdir/nested/file.txt")
        listing = client.ls("subdir/nested")
        assert any("file.txt" in str(p) for p in listing)

    def test_rm_file(self, tmp_path):
        client = self._make_client(tmp_path)
        client.write_text("to delete", "delete_me.txt")
        assert client.exists("delete_me.txt")
        client.rm("delete_me.txt")
        assert not client.exists("delete_me.txt")

    def test_full_path_construction(self, tmp_path):
        client = self._make_client(tmp_path)
        full = client._full_path("some/file.txt")
        assert "some/file.txt" in full

    def test_unsupported_backend_raises(self, tmp_path):
        from src.config.storage import StorageClient

        # Bypass __init__ (which requires valid Settings) to test _get_filesystem directly
        client = StorageClient.__new__(StorageClient)
        client.backend = "invalid_backend"
        client.base_uri = str(tmp_path)
        with pytest.raises(ValueError, match="Unsupported storage backend"):
            client._get_filesystem()
