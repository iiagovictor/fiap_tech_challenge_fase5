"""Tests for model training and prediction."""

import numpy as np
import pytest
from sklearn.preprocessing import StandardScaler

from src.models.train import build_lstm_model, evaluate_model, prepare_lstm_sequences, train_model


def test_prepare_lstm_sequences(sample_features):
    """Test LSTM sequence preparation."""
    sequences, y, scaler, feature_names = prepare_lstm_sequences(sample_features, seq_length=5)

    # Check shapes
    assert len(sequences.shape) == 3  # (samples, seq_length, features)
    assert sequences.shape[1] == 5  # seq_length
    assert len(y) == len(sequences)

    # Check scaler
    assert isinstance(scaler, StandardScaler)

    # Check feature names
    assert len(feature_names) > 0
    assert "close" in feature_names


def test_build_lstm_model():
    """Test LSTM model architecture."""
    model = build_lstm_model(input_shape=(60, 20), lstm_units=32, dropout=0.2)

    # Check model structure
    assert model is not None
    assert len(model.layers) > 0

    # Check input/output shapes
    assert model.input_shape == (None, 60, 20)
    assert model.output_shape == (None, 1)

    # Check it's compiled
    assert model.optimizer is not None
    assert model.loss is not None


def test_model_prediction_shape(sample_features):
    """Test model prediction output shape."""
    # Build model
    model = build_lstm_model(input_shape=(5, 4), lstm_units=16, dropout=0.2)

    # Create dummy input
    dummy_input = np.random.randn(10, 5, 4)

    # Predict
    predictions = model.predict(dummy_input)

    # Check shape
    assert predictions.shape == (10, 1)
    assert (predictions >= 0).all()  # Sigmoid output
    assert (predictions <= 1).all()


def test_evaluate_model():
    """Test evaluate_model returns correct metric keys and valid ranges."""
    model = build_lstm_model(input_shape=(5, 4), lstm_units=16, dropout=0.2)
    x_test = np.random.randn(20, 5, 4).astype(np.float32)
    y_test = np.array([0] * 10 + [1] * 10)

    metrics = evaluate_model(model, x_test, y_test)

    assert "accuracy" in metrics
    assert "precision" in metrics
    assert "recall" in metrics
    assert "f1_score" in metrics
    assert "roc_auc" in metrics
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert 0.0 <= metrics["roc_auc"] <= 1.0


def test_train_model_one_epoch():
    """Test train_model runs for one epoch and returns model + history."""
    x_train = np.random.randn(30, 5, 4).astype(np.float32)
    y_train = np.array([0] * 15 + [1] * 15)
    x_val = np.random.randn(10, 5, 4).astype(np.float32)
    y_val = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 1])

    trained_model, history = train_model(
        x_train,
        y_train,
        x_val,
        y_val,
        lstm_units=16,
        dropout=0.2,
        epochs=1,
        batch_size=10,
    )

    assert trained_model is not None
    assert "loss" in history
    assert len(history["loss"]) == 1


# ---------------------------------------------------------------------------
# MLP PyTorch baseline tests (skipped when torch is not installed)
# ---------------------------------------------------------------------------

torch = pytest.importorskip("torch", reason="PyTorch not installed — skipping MLP tests")


def test_mlp_classifier_forward_pass():
    """MLPClassifier.predict_proba returns values in [0, 1]."""
    from src.models.mlp_torch import MLPClassifier

    x = np.random.randn(20, 8).astype(np.float32)
    clf = MLPClassifier(input_dim=8, hidden_dims=[16, 8], dropout=0.0)
    proba = clf.predict_proba(x)

    assert proba.shape == (20,)
    assert (proba >= 0).all()
    assert (proba <= 1).all()


def test_mlp_classifier_fit_one_epoch():
    """MLPClassifier.fit runs for one epoch and records loss."""
    from src.models.mlp_torch import MLPClassifier

    x = np.random.randn(40, 8).astype(np.float32)
    y = np.array([0] * 20 + [1] * 20, dtype=np.float32)

    clf = MLPClassifier(input_dim=8, hidden_dims=[16, 8], dropout=0.0)
    clf.fit(x, y, epochs=1, batch_size=16, verbose=False)

    assert len(clf.history["loss"]) == 1


def test_mlp_classifier_evaluate_metrics():
    """MLPClassifier.evaluate returns expected metric keys and valid ranges."""
    from src.models.mlp_torch import MLPClassifier

    x_train = np.random.randn(40, 8).astype(np.float32)
    y_train = np.array([0] * 20 + [1] * 20, dtype=np.float32)
    x_test = np.random.randn(10, 8).astype(np.float32)
    y_test = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])

    clf = MLPClassifier(input_dim=8, hidden_dims=[16, 8], dropout=0.0)
    clf.fit(x_train, y_train, epochs=2, batch_size=16, verbose=False)
    metrics = clf.evaluate(x_test, y_test)

    for key in ["accuracy", "precision", "recall", "f1_score", "roc_auc"]:
        assert key in metrics
        assert 0.0 <= metrics[key] <= 1.0


def test_mlp_no_torch_raises():
    """MLPClassifier raises ImportError if torch is missing (simulated)."""
    import importlib
    import sys
    from unittest.mock import patch

    with (
        patch.dict(sys.modules, {"torch": None, "torch.nn": None, "torch.optim": None}),
        pytest.raises(ImportError, match="PyTorch is required"),
    ):
        from src.models import mlp_torch  # noqa: F401

        importlib.reload(mlp_torch)
        mlp_torch.MLPClassifier(input_dim=4)
