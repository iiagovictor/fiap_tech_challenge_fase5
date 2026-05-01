"""
LSTM model training with MLflow tracking.

Adapted from Fase 4 baseline, using cloud-agnostic storage and MLflow registry.
Implements champion-challenger pattern with model promotion.
"""

import logging
from datetime import datetime
from pathlib import Path

import mlflow
import mlflow.keras
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from tensorflow import keras
from tensorflow.keras import layers

from src.config.settings import get_settings
from src.config.storage import get_storage

logger = logging.getLogger(__name__)
settings = get_settings()
storage = get_storage()


def load_training_data(features_path: str = "features/stock_features.parquet") -> pd.DataFrame:
    """Load feature data from storage."""
    logger.info(f"Loading training data from {features_path}")
    df = storage.read_parquet(features_path)
    logger.info(f"Loaded {len(df):,} rows with {len(df.columns)} columns")
    return df


def prepare_lstm_sequences(
    df: pd.DataFrame,
    seq_length: int = 60,
    feature_columns: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, StandardScaler, list[str]]:
    """
    Prepare sequences for LSTM training.
    
    Args:
        df: DataFrame with features and target
        seq_length: Sequence length for LSTM
        feature_columns: List of feature columns to use (default: all numeric except target)
    
    Returns:
        X: Sequences array of shape (n_samples, seq_length, n_features)
        y: Target array
        scaler: Fitted StandardScaler
        feature_names: List of feature names used
    """
    # Sort by ticker and date
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    # Select feature columns
    if feature_columns is None:
        # Use all numeric columns except target and identifiers
        exclude_cols = ["date", "ticker", "target"]
        feature_columns = [c for c in df.columns if c not in exclude_cols and df[c].dtype in [np.float64, np.float32, np.int64]]

    logger.info(f"Using {len(feature_columns)} features for LSTM")

    # Scale features
    scaler = StandardScaler()
    df_scaled = df.copy()
    df_scaled[feature_columns] = scaler.fit_transform(df[feature_columns])

    # Create sequences per ticker
    X_list = []
    y_list = []

    for ticker in df["ticker"].unique():
        ticker_data = df_scaled[df_scaled["ticker"] == ticker].reset_index(drop=True)

        # Extract features and target
        features = ticker_data[feature_columns].values
        targets = ticker_data["target"].values

        # Create sequences
        for i in range(len(features) - seq_length):
            X_list.append(features[i : i + seq_length])
            y_list.append(targets[i + seq_length])

    X = np.array(X_list)
    y = np.array(y_list)

    logger.info(f"Created {len(X):,} sequences of shape {X.shape}")
    logger.info(f"Class distribution: {np.bincount(y)}")

    return X, y, scaler, feature_columns


def build_lstm_model(
    input_shape: tuple[int, int],
    lstm_units: int = 50,
    dropout: float = 0.2,
) -> keras.Model:
    """
    Build LSTM model architecture (adapted from Fase 4).
    
    Args:
        input_shape: (seq_length, n_features)
        lstm_units: Number of LSTM units
        dropout: Dropout rate
    
    Returns:
        Compiled Keras model
    """
    model = keras.Sequential(
        [
            layers.Input(shape=input_shape),
            layers.LSTM(lstm_units, return_sequences=True),
            layers.Dropout(dropout),
            layers.LSTM(lstm_units // 2, return_sequences=False),
            layers.Dropout(dropout),
            layers.Dense(32, activation="relu"),
            layers.Dropout(dropout),
            layers.Dense(1, activation="sigmoid"),
        ]
    )

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss="binary_crossentropy",
        metrics=["accuracy", keras.metrics.AUC(name="auc")],
    )

    logger.info(f"Built LSTM model with {model.count_params():,} parameters")
    return model


def train_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    lstm_units: int = 50,
    dropout: float = 0.2,
    epochs: int = 50,
    batch_size: int = 32,
) -> tuple[keras.Model, dict]:
    """
    Train LSTM model with early stopping.
    
    Returns:
        model: Trained Keras model
        history: Training history dict
    """
    # Build model
    input_shape = (X_train.shape[1], X_train.shape[2])
    model = build_lstm_model(input_shape, lstm_units, dropout)

    # Callbacks
    early_stopping = keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=10,
        restore_best_weights=True,
        verbose=1,
    )

    reduce_lr = keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.5,
        patience=5,
        min_lr=1e-6,
        verbose=1,
    )

    # Train
    logger.info(f"Training model for up to {epochs} epochs...")
    history = model.fit(
        X_train,
        y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=[early_stopping, reduce_lr],
        verbose=1,
    )

    logger.info("✅ Training complete")
    return model, history.history


def evaluate_model(model: keras.Model, X_test: np.ndarray, y_test: np.ndarray) -> dict:
    """
    Evaluate model and return metrics.
    
    Returns:
        Dictionary with accuracy, precision, recall, f1, auc
    """
    logger.info("Evaluating model on test set...")

    # Predictions
    y_pred_proba = model.predict(X_test).flatten()
    y_pred = (y_pred_proba >= 0.5).astype(int)

    # Calculate metrics
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_pred_proba)),
    }

    logger.info("Test Metrics:")
    for metric, value in metrics.items():
        logger.info(f"  {metric}: {value:.4f}")

    return metrics


def training_pipeline(
    experiment_name: str | None = None,
    run_name: str | None = None,
    promote_to_production: bool = False,
) -> dict:
    """
    Main training pipeline with MLflow tracking.
    
    Args:
        experiment_name: MLflow experiment name
        run_name: MLflow run name
        promote_to_production: If True, promote model to Production stage
    
    Returns:
        Dictionary with metrics and model info
    """
    # Set MLflow tracking URI
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

    # Create or set experiment
    if experiment_name is None:
        experiment_name = settings.mlflow_experiment_name

    mlflow.set_experiment(experiment_name)

    with mlflow.start_run(run_name=run_name) as run:
        # Log parameters
        mlflow.log_param("model_type", "LSTM")
        mlflow.log_param("lstm_units", settings.model_lstm_units)
        mlflow.log_param("dropout", settings.model_dropout)
        mlflow.log_param("epochs", settings.model_epochs)
        mlflow.log_param("batch_size", settings.model_batch_size)
        mlflow.log_param("seq_length", settings.model_seq_length)

        # Load data
        df = load_training_data()

        # Prepare sequences
        X, y, scaler, feature_names = prepare_lstm_sequences(
            df, seq_length=settings.model_seq_length
        )

        # Split data
        X_temp, X_test, y_temp, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        X_train, X_val, y_train, y_val = train_test_split(
            X_temp, y_temp, test_size=0.2, random_state=42, stratify=y_temp
        )

        logger.info(f"Train: {len(X_train):,} | Val: {len(X_val):,} | Test: {len(X_test):,}")

        # Train model
        model, history = train_model(
            X_train,
            y_train,
            X_val,
            y_val,
            lstm_units=settings.model_lstm_units,
            dropout=settings.model_dropout,
            epochs=settings.model_epochs,
            batch_size=settings.model_batch_size,
        )

        # Evaluate
        test_metrics = evaluate_model(model, X_test, y_test)

        # Log metrics
        for metric, value in test_metrics.items():
            mlflow.log_metric(f"test_{metric}", value)

        # Log training history
        for epoch, loss in enumerate(history["loss"]):
            mlflow.log_metric("train_loss", loss, step=epoch)
        for epoch, val_loss in enumerate(history["val_loss"]):
            mlflow.log_metric("val_loss", val_loss, step=epoch)

        # Save artifacts
        # 1. Save model to storage (with run_id and "latest" alias)
        model_path = f"models/lstm_model_{run.info.run_id}.keras"
        storage.write_keras_model(model, model_path)
        logger.info(f"Saved model to {model_path}")
        
        # Also save as "latest" for easy loading by API
        model_latest_path = "models/lstm_model_latest.keras"
        storage.write_keras_model(model, model_latest_path)
        logger.info(f"Saved model to {model_latest_path}")

        # 2. Save scaler to storage (with run_id and "latest" alias)
        scaler_path = f"models/scaler_{run.info.run_id}.pkl"
        storage.write_joblib(scaler, scaler_path)
        logger.info(f"Saved scaler to {scaler_path}")
        
        # Also save as "latest"
        scaler_latest_path = "models/scaler_latest.pkl"
        storage.write_joblib(scaler, scaler_latest_path)
        logger.info(f"Saved scaler to {scaler_latest_path}")

        # 3. Log model to MLflow
        mlflow.keras.log_model(
            model,
            artifact_path="model",
            registered_model_name="stock_lstm_predictor",
        )

        # 4. Log additional artifacts
        mlflow.log_dict({"feature_names": feature_names}, "feature_names.json")
        mlflow.log_dict(test_metrics, "test_metrics.json")

        # Set tags for governance
        mlflow.set_tags(
            {
                "stage": "production" if promote_to_production else "staging",
                "framework": "tensorflow",
                "model_type": "lstm",
                "use_case": "stock_price_direction",
                "data_version": datetime.now().strftime("%Y-%m-%d"),
            }
        )

        logger.info(f"✅ MLflow run complete: {run.info.run_id}")

        return {
            "run_id": run.info.run_id,
            "metrics": test_metrics,
            "model_path": model_path,
            "scaler_path": scaler_path,
        }


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run training pipeline
    result = training_pipeline(
        run_name=f"lstm_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        promote_to_production=False,
    )

    print("\n" + "=" * 60)
    print("✅ TRAINING COMPLETE")
    print("=" * 60)
    print(f"Run ID: {result['run_id']}")
    print(f"Model Path: {result['model_path']}")
    print("\nTest Metrics:")
    for metric, value in result["metrics"].items():
        print(f"  {metric}: {value:.4f}")
    print("=" * 60)
