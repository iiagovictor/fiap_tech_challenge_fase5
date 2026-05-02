"""
Baseline models for comparison (Logistic Regression, Random Forest).

Used for benchmarking against LSTM model.
"""

import logging

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from src.config.storage import get_storage
from src.data.schemas import validate_training_data

logger = logging.getLogger(__name__)
storage = get_storage()


def train_baseline_models(features_path: str = "features/stock_features.parquet") -> dict:
    """
    Train baseline models (LR, RF) for comparison.

    Returns:
        Dictionary with metrics for each baseline model
    """
    logger.info("Training baseline models...")

    # Load data
    df = storage.read_parquet(features_path)

    # Validate data against schema
    try:
        df = validate_training_data(df)
        logger.info("✅ Training data validated against TRAINING_DATA_SCHEMA")
    except Exception as e:
        logger.error(f"Schema validation failed: {e}")
        raise

    # Select numeric features
    exclude_cols = ["date", "ticker", "target"]
    numeric_dtypes = [np.float64, np.float32, np.int64]
    feature_cols = [
        c for c in df.columns if c not in exclude_cols and df[c].dtype in numeric_dtypes
    ]

    x = df[feature_cols].values
    y = df["target"].values

    # Split data
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=42, stratify=y
    )

    # Scale features
    scaler = StandardScaler()
    x_train_scaled = scaler.fit_transform(x_train)
    x_test_scaled = scaler.transform(x_test)

    results = {}

    # Logistic Regression
    logger.info("Training Logistic Regression...")
    lr = LogisticRegression(max_iter=1000, random_state=42)
    lr.fit(x_train_scaled, y_train)
    y_pred_lr = lr.predict(x_test_scaled)
    y_proba_lr = lr.predict_proba(x_test_scaled)[:, 1]

    results["logistic_regression"] = {
        "accuracy": accuracy_score(y_test, y_pred_lr),
        "precision": precision_score(y_test, y_pred_lr, zero_division=0),
        "recall": recall_score(y_test, y_pred_lr, zero_division=0),
        "f1_score": f1_score(y_test, y_pred_lr, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_proba_lr),
    }

    # Random Forest
    logger.info("Training Random Forest...")
    rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    rf.fit(x_train_scaled, y_train)
    y_pred_rf = rf.predict(x_test_scaled)
    y_proba_rf = rf.predict_proba(x_test_scaled)[:, 1]

    results["random_forest"] = {
        "accuracy": accuracy_score(y_test, y_pred_rf),
        "precision": precision_score(y_test, y_pred_rf, zero_division=0),
        "recall": recall_score(y_test, y_pred_rf, zero_division=0),
        "f1_score": f1_score(y_test, y_pred_rf, zero_division=0),
        "roc_auc": roc_auc_score(y_test, y_proba_rf),
    }

    # Log results
    for model_name, metrics in results.items():
        logger.info(f"\n{model_name.upper()} Results:")
        for metric, value in metrics.items():
            logger.info(f"  {metric}: {value:.4f}")

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    results = train_baseline_models()
    print("\n✅ Baseline models trained successfully")
