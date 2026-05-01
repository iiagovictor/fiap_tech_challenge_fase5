"""
Custom Prometheus metrics for model monitoring.

Tracks:
- Model performance metrics (accuracy, latency)
- Feature statistics
- Prediction distributions
- System health
"""

import logging
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, Summary

logger = logging.getLogger(__name__)

# ============================================================
# Model Performance Metrics
# ============================================================
MODEL_PREDICTION_LATENCY = Histogram(
    "model_prediction_latency_seconds",
    "Time spent generating predictions",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
)

MODEL_PREDICTIONS_TOTAL = Counter(
    "model_predictions_total",
    "Total number of predictions made",
    ["model_name", "model_version"],
)

MODEL_PREDICTION_ERRORS = Counter(
    "model_prediction_errors_total",
    "Total prediction errors",
    ["model_name", "error_type"],
)

# ============================================================
# Feature Store Metrics
# ============================================================
FEATURE_RETRIEVAL_LATENCY = Histogram(
    "feature_retrieval_latency_seconds",
    "Time spent retrieving features",
    ["store_type"],  # online, offline
)

FEATURE_MISSING_VALUES = Gauge(
    "feature_missing_values_total",
    "Number of missing values in features",
    ["feature_name"],
)

# ============================================================
# Data Quality Metrics
# ============================================================
DATA_DRIFT_SCORE = Gauge(
    "data_drift_score",
    "Data drift score from Evidently",
    ["feature_name"],
)

PREDICTION_CONFIDENCE = Histogram(
    "prediction_confidence_score",
    "Distribution of prediction confidence scores",
    buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99],
)

# ============================================================
# LLM Agent Metrics
# ============================================================
LLM_REQUEST_LATENCY = Histogram(
    "llm_request_latency_seconds",
    "Time spent on LLM requests",
    ["model_name"],
)

LLM_TOKENS_USED = Counter(
    "llm_tokens_used_total",
    "Total tokens consumed",
    ["model_name", "token_type"],  # input, output
)

AGENT_TOOL_CALLS = Counter(
    "agent_tool_calls_total",
    "Number of tool calls by agent",
    ["tool_name"],
)

# ============================================================
# Guardrails Metrics
# ============================================================
GUARDRAIL_VIOLATIONS = Counter(
    "guardrail_violations_total",
    "Number of guardrail violations",
    ["violation_type"],  # pii_detected, toxic_content, etc.
)

PII_DETECTIONS = Counter(
    "pii_detections_total",
    "Number of PII detections",
    ["pii_type"],  # email, phone, ssn, etc.
)

# ============================================================
# Helper Functions
# ============================================================
def track_prediction(
    model_name: str,
    model_version: str,
    latency: float,
    confidence: float,
    error: str | None = None,
) -> None:
    """Track a prediction with associated metrics."""
    MODEL_PREDICTIONS_TOTAL.labels(
        model_name=model_name,
        model_version=model_version,
    ).inc()

    MODEL_PREDICTION_LATENCY.observe(latency)
    PREDICTION_CONFIDENCE.observe(confidence)

    if error:
        MODEL_PREDICTION_ERRORS.labels(
            model_name=model_name,
            error_type=error,
        ).inc()


def track_feature_retrieval(store_type: str, latency: float) -> None:
    """Track feature retrieval metrics."""
    FEATURE_RETRIEVAL_LATENCY.labels(store_type=store_type).observe(latency)


def track_data_drift(feature_name: str, drift_score: float) -> None:
    """Update drift score for a feature."""
    DATA_DRIFT_SCORE.labels(feature_name=feature_name).set(drift_score)


def track_llm_request(
    model_name: str,
    latency: float,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Track LLM request metrics."""
    LLM_REQUEST_LATENCY.labels(model_name=model_name).observe(latency)
    LLM_TOKENS_USED.labels(model_name=model_name, token_type="input").inc(input_tokens)
    LLM_TOKENS_USED.labels(model_name=model_name, token_type="output").inc(output_tokens)


def track_tool_call(tool_name: str) -> None:
    """Track agent tool usage."""
    AGENT_TOOL_CALLS.labels(tool_name=tool_name).inc()


def track_guardrail_violation(violation_type: str) -> None:
    """Track guardrail violations."""
    GUARDRAIL_VIOLATIONS.labels(violation_type=violation_type).inc()


def track_pii_detection(pii_type: str) -> None:
    """Track PII detections."""
    PII_DETECTIONS.labels(pii_type=pii_type).inc()


if __name__ == "__main__":
    # Test metrics
    print("✅ Prometheus metrics module initialized")
    print("\nAvailable metrics:")
    print("  - model_prediction_latency_seconds")
    print("  - model_predictions_total")
    print("  - feature_retrieval_latency_seconds")
    print("  - data_drift_score")
    print("  - llm_request_latency_seconds")
    print("  - guardrail_violations_total")
