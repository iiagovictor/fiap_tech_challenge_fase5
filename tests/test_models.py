"""Tests for model training and prediction."""

import numpy as np
from sklearn.preprocessing import StandardScaler

from src.models.train import build_lstm_model, prepare_lstm_sequences


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
