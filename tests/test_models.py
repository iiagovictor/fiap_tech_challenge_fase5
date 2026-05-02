"""Tests for model training and prediction."""

import numpy as np
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
