"""
Feature drift detection using Evidently.

Monitors data drift between reference (training) and current (production) datasets.
Generates HTML reports and numeric drift scores.
"""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from evidently import ColumnMapping
from evidently.metric_preset import DataDriftPreset
from evidently.report import Report

from src.config.storage import get_storage

logger = logging.getLogger(__name__)
storage = get_storage()


def detect_drift(
    reference_data: pd.DataFrame,
    current_data: pd.DataFrame,
    feature_columns: list[str] | None = None,
    output_path: str = "reports/drift_report.html",
) -> dict:
    """
    Detect data drift between reference and current datasets.

    Args:
        reference_data: Training/reference dataset
        current_data: Current/production dataset
        feature_columns: List of feature columns to monitor (default: all numeric)
        output_path: Path to save HTML report

    Returns:
        Dictionary with drift metrics and alerts
    """
    logger.info("Running drift detection...")

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
    report = Report(metrics=[DataDriftPreset()])

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

    try:
        metrics = report_dict.get("metrics", [])
        for metric in metrics:
            if metric.get("metric") == "DatasetDriftMetric":
                result = metric.get("result", {})
                drift_detected = result.get("dataset_drift", False)
                drift_by_columns = result.get("drift_by_columns", {})

                for col, col_drift in drift_by_columns.items():
                    drift_score = col_drift.get("drift_score", 0)
                    drift_scores[col] = drift_score
                    if col_drift.get("drift_detected", False):
                        drifted_features.append(col)

    except Exception as e:
        logger.warning(f"Failed to parse drift metrics: {e}")

    # Overall drift score (average of all feature drift scores)
    overall_drift_score = sum(drift_scores.values()) / len(drift_scores) if drift_scores else 0.0

    # Determine alert level
    if overall_drift_score < 0.05:
        alert_level = "green"
    elif overall_drift_score < 0.15:
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
