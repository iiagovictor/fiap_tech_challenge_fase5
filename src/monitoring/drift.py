"""
Feature drift detection using Evidently.

Monitors data drift between reference (training) and current (production) datasets.
Generates HTML reports and numeric drift scores.

Thresholds are loaded from ``configs/monitoring_config.yaml`` when present,
otherwise the hard-coded defaults below are used.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from evidently import ColumnMapping
from evidently.metric_preset import DataDriftPreset
from evidently.report import Report

from src.config.storage import get_storage

logger = logging.getLogger(__name__)
storage = get_storage()

# ── Monitoring config loader ──────────────────────────────────────────────────
_DEFAULT_DRIFT_CONFIG: dict[str, Any] = {
    "green_threshold": 0.20,
    "yellow_threshold": 0.50,
    "stattest_threshold": 0.05,
    "report_output_path": "reports/drift_report.html",
}


def _load_drift_config() -> dict[str, Any]:
    """Load drift thresholds from configs/monitoring_config.yaml if available."""
    config_path = Path(__file__).resolve().parents[2] / "configs" / "monitoring_config.yaml"
    if not config_path.exists():
        return _DEFAULT_DRIFT_CONFIG.copy()
    try:
        import yaml  # optional dep — falls back to defaults if missing

        with config_path.open(encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        drift_cfg = raw.get("drift", {})
        merged = {**_DEFAULT_DRIFT_CONFIG, **drift_cfg}
        logger.debug("Drift config loaded from %s: %s", config_path, merged)
        return merged
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load monitoring_config.yaml (%s) — using defaults", exc)
        return _DEFAULT_DRIFT_CONFIG.copy()


def detect_drift(
    reference_data: pd.DataFrame,
    current_data: pd.DataFrame,
    feature_columns: list[str] | None = None,
    output_path: str | None = None,
) -> dict:
    """
    Detect data drift between reference and current datasets.

    Args:
        reference_data: Training/reference dataset
        current_data: Current/production dataset
        feature_columns: List of feature columns to monitor (default: all numeric)
        output_path: Path to save HTML report (overrides monitoring_config.yaml value)

    Returns:
        Dictionary with drift metrics and alerts
    """
    drift_cfg = _load_drift_config()
    green_threshold = drift_cfg["green_threshold"]
    yellow_threshold = drift_cfg["yellow_threshold"]
    stattest_threshold = drift_cfg["stattest_threshold"]
    if output_path is None:
        output_path = drift_cfg["report_output_path"]

    logger.info(
        "Running drift detection (green<%.2f, yellow<%.2f)...", green_threshold, yellow_threshold
    )

    # Select feature columns
    if feature_columns is None:
        exclude_cols = ["date", "ticker", "target"]
        feature_columns = [
            c
            for c in reference_data.columns
            if c not in exclude_cols and reference_data[c].dtype in ["float64", "float32", "int64"]
        ]

    logger.info(f"Monitoring drift for {len(feature_columns)} features")

    # Create column mapping
    column_mapping = ColumnMapping()
    column_mapping.numerical_features = feature_columns
    if "target" in reference_data.columns:
        column_mapping.target = "target"

    # Create Evidently report
    report = Report(metrics=[DataDriftPreset(stattest_threshold=stattest_threshold)])

    # Generate report
    report.run(
        reference_data=reference_data[
            feature_columns + (["target"] if "target" in reference_data.columns else [])
        ],
        current_data=current_data[
            feature_columns + (["target"] if "target" in current_data.columns else [])
        ],
        column_mapping=column_mapping,
    )

    # Save HTML report
    report_html = report.get_html()
    output_full_path = Path(output_path)
    output_full_path.parent.mkdir(parents=True, exist_ok=True)
    output_full_path.write_text(report_html)
    logger.info(f"Drift report saved to {output_path}")

    # Extract metrics
    report_dict = report.as_dict()

    # Parse drift results
    drift_detected = False
    drifted_features = []
    drift_scores = {}
    overall_drift_score = 0.0

    try:
        metrics = report_dict.get("metrics", [])
        for metric in metrics:
            # Overall dataset-level stats come from DatasetDriftMetric
            if metric.get("metric") == "DatasetDriftMetric":
                result = metric.get("result", {})
                drift_detected = result.get("dataset_drift", False)
                overall_drift_score = result.get("share_of_drifted_columns", 0.0)

            # Per-column data comes from DataDriftTable
            if metric.get("metric") == "DataDriftTable":
                result = metric.get("result", {})
                drift_by_columns = result.get("drift_by_columns", {})
                for col, col_drift in drift_by_columns.items():
                    drift_scores[col] = col_drift.get("drift_score", 0)
                    if col_drift.get("drift_detected", False):
                        drifted_features.append(col)

    except Exception as e:
        logger.warning(f"Failed to parse drift metrics: {e}")

    # Determine alert level using configurable thresholds
    if overall_drift_score < green_threshold:
        alert_level = "green"
    elif overall_drift_score < yellow_threshold:
        alert_level = "yellow"
    else:
        alert_level = "red"

    result = {
        "timestamp": datetime.now().isoformat(),
        "drift_detected": drift_detected,
        "overall_drift_score": overall_drift_score,
        "features_drifted": drifted_features,
        "drift_scores": drift_scores,
        "alert_level": alert_level,
        "report_path": str(output_path),
    }

    logger.info("Drift Detection Results:")
    logger.info(f"  Overall Score: {overall_drift_score:.4f}")
    logger.info(f"  Alert Level: {alert_level}")
    logger.info(f"  Drifted Features: {len(drifted_features)}")

    return result


def drift_monitoring_pipeline(
    reference_path: str = "features/stock_features.parquet",
    current_path: str = "features/stock_features_current.parquet",
    output_path: str = "reports/drift_report.html",
) -> dict:
    """
    Main drift monitoring pipeline.

    Compares reference (training) data with current (production) data.

    Args:
        reference_path: Path to reference dataset
        current_path: Path to current dataset
        output_path: Path for drift report

    Returns:
        Drift metrics dictionary
    """
    # Load datasets
    logger.info(f"Loading reference data from {reference_path}")
    reference_data = storage.read_parquet(reference_path)
    logger.info(f"Reference data: {len(reference_data)} rows")

    # For demonstration, split reference data into two periods
    # In production, current_data would come from live production data
    if not storage.exists(current_path):
        logger.warning(f"Current data not found at {current_path}")
        logger.info("Using last 30% of reference data as 'current' for demo")

        split_idx = int(len(reference_data) * 0.7)
        reference_subset = reference_data.iloc[:split_idx]
        current_data = reference_data.iloc[split_idx:]
    else:
        logger.info(f"Loading current data from {current_path}")
        current_data = storage.read_parquet(current_path)
        reference_subset = reference_data

    logger.info(f"Current data: {len(current_data)} rows")

    # Run drift detection
    result = detect_drift(reference_subset, current_data, output_path=output_path)

    # Save metrics to JSON
    metrics_path = output_path.replace(".html", ".json")
    storage.write_json(result, metrics_path)
    logger.info(f"Drift metrics saved to {metrics_path}")

    return result


if __name__ == "__main__":
    import sys

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run drift monitoring
    result = drift_monitoring_pipeline()

    print("\n" + "=" * 60)
    print("📊 DRIFT DETECTION COMPLETE")
    print("=" * 60)
    print(f"Overall Drift Score: {result['overall_drift_score']:.4f}")
    print(f"Alert Level: {result['alert_level']}")
    print(f"Drifted Features: {len(result['features_drifted'])}")
    if result["features_drifted"]:
        print(f"  {', '.join(result['features_drifted'][:5])}")
    print(f"\nReport: {result['report_path']}")
    print("=" * 60)

    # Exit with code 1 if high drift detected
    if result["alert_level"] == "red":
        sys.exit(1)
