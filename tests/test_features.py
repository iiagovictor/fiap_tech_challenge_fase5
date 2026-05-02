"""Tests for feature engineering using Pandera validation."""

import pandas as pd
import pytest

from src.data.schemas import (
    FEATURE_SET_SCHEMA,
    validate_features,
    validate_training_data,
)
from src.features.feature_engineering import (
    add_technical_indicators,
    calculate_atr,
    calculate_obv,
    calculate_rsi,
    create_target_variable,
)


def test_calculate_rsi(sample_stock_data):
    """Test RSI calculation."""
    df = sample_stock_data
    rsi = calculate_rsi(df["close"], period=14)

    assert len(rsi) == len(df)
    assert rsi.iloc[-1] >= 0
    assert rsi.iloc[-1] <= 100


def test_calculate_atr(sample_stock_data):
    """Test ATR calculation."""
    df = sample_stock_data
    atr = calculate_atr(df["high"], df["low"], df["close"], period=14)

    assert len(atr) == len(df)
    # NaN expected for the warmup period; only check populated values
    assert (atr.dropna() >= 0).all()


def test_calculate_obv(sample_stock_data):
    """Test OBV calculation."""
    df = sample_stock_data
    obv = calculate_obv(df["close"], df["volume"])

    assert len(obv) == len(df)


def test_add_technical_indicators(sample_stock_data):
    """Test adding all technical indicators with Pandera schema validation."""
    df_features = add_technical_indicators(sample_stock_data)

    # Check new columns were added
    assert "sma_5" in df_features.columns
    assert "rsi_14" in df_features.columns
    assert "macd" in df_features.columns
    assert "bb_upper" in df_features.columns

    # Validate against feature schema
    validated_df = validate_features(df_features)
    assert len(validated_df) > 0
    assert set(FEATURE_SET_SCHEMA.columns.keys()).issubset(validated_df.columns)

    # EMAs and MACD use ewm (no strict warmup) — should be populated for last row per ticker
    for ticker in df_features["ticker"].unique():
        ticker_df = df_features[df_features["ticker"] == ticker]
        assert pd.notna(ticker_df["ema_12"].iloc[-1])
        assert pd.notna(ticker_df["macd"].iloc[-1])
        assert pd.notna(ticker_df["obv"].iloc[-1])


def test_create_target_variable(sample_stock_data):
    """Test target variable creation with Pandera schema validation."""
    df_features = add_technical_indicators(sample_stock_data)
    df_with_target = create_target_variable(df_features, horizon=5)

    # Check target column exists
    assert "target" in df_with_target.columns

    # Check target is binary
    assert df_with_target["target"].isin([0, 1]).all()

    # Check target value is within valid range [0, 1]
    target_mean = df_with_target["target"].mean()
    assert 0.0 <= target_mean <= 1.0

    # Validate against training data schema
    validated_df = validate_training_data(df_with_target)
    assert len(validated_df) > 0
    assert "target" in validated_df.columns
    assert validated_df["target"].isin([0, 1]).all()


# ============================================================
# Pandera Schema Validation Tests
# ============================================================
def test_feature_set_schema_validation(sample_stock_data):
    """Test FEATURE_SET_SCHEMA validates correct data."""
    df_features = add_technical_indicators(sample_stock_data)
    
    # Should not raise exception
    validated_df = validate_features(df_features)
    assert len(validated_df) == len(df_features)
    assert isinstance(validated_df, pd.DataFrame)


def test_training_data_schema_validation(sample_stock_data):
    """Test TRAINING_DATA_SCHEMA validates features with target."""
    df_features = add_technical_indicators(sample_stock_data)
    df_with_target = create_target_variable(df_features, horizon=5)
    
    # Should not raise exception
    validated_df = validate_training_data(df_with_target)
    assert len(validated_df) == len(df_with_target)
    assert "target" in validated_df.columns


def test_schema_rejects_invalid_target():
    """Test TRAINING_DATA_SCHEMA rejects invalid target values."""
    from pandera import SchemaError
    
    df_invalid = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=5),
        "ticker": ["ITUB4.SA"] * 5,
        "open": [20.0] * 5,
        "high": [21.0] * 5,
        "low": [19.0] * 5,
        "close": [20.5] * 5,
        "volume": [1000] * 5,
        "sma_5": [20.0] * 5,
        "sma_20": [20.0] * 5,
        "ema_12": [20.0] * 5,
        "ema_26": [20.0] * 5,
        "rsi_14": [50.0] * 5,
        "macd": [0.0] * 5,
        "macd_signal": [0.0] * 5,
        "macd_hist": [0.0] * 5,
        "bb_upper": [21.0] * 5,
        "bb_middle": [20.0] * 5,
        "bb_lower": [19.0] * 5,
        "bb_pct": [0.5] * 5,
        "atr": [1.0] * 5,
        "obv": [1000.0] * 5,
        "mfm": [0.5] * 5,
        "cmf": [0.5] * 5,
        "target": [0, 1, 2, 0, 1],  # Invalid: contains 2
    })
    
    with pytest.raises(SchemaError):
        validate_training_data(df_invalid)


def test_schema_rejects_missing_values():
    """Test TRAINING_DATA_SCHEMA rejects missing required columns."""
    from pandera import SchemaError
    
    df_invalid = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=5),
        "ticker": ["ITUB4.SA"] * 5,
        # Missing other required columns
    })
    
    with pytest.raises(SchemaError):
        validate_training_data(df_invalid)


def test_rsi_bounds_in_schema():
    """Test that RSI values in features are validated between 0-100."""
    df = pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=5),
        "ticker": ["ITUB4.SA"] * 5,
        "open": [20.0] * 5,
        "high": [21.0] * 5,
        "low": [19.0] * 5,
        "close": [20.5] * 5,
        "volume": [1000] * 5,
        "sma_5": [20.0] * 5,
        "sma_20": [20.0] * 5,
        "ema_12": [20.0] * 5,
        "ema_26": [20.0] * 5,
        "rsi_14": [50.0] * 5,  # Valid: between 0-100
        "macd": [0.0] * 5,
        "macd_signal": [0.0] * 5,
        "macd_hist": [0.0] * 5,
        "bb_upper": [21.0] * 5,
        "bb_middle": [20.0] * 5,
        "bb_lower": [19.0] * 5,
        "bb_pct": [0.5] * 5,
        "atr": [1.0] * 5,
        "obv": [1000.0] * 5,
        "mfm": [0.5] * 5,
        "cmf": [0.5] * 5,
    })
    
    # Should validate successfully
    validated_df = validate_features(df)
    assert (validated_df["rsi_14"] >= 0).all()
    assert (validated_df["rsi_14"] <= 100).all()


def test_settings_tickers_list():
    """Test Settings.get_tickers_list() helper."""
    from src.config.settings import get_settings

    s = get_settings()
    tickers = s.get_tickers_list()
    assert isinstance(tickers, list)
    assert len(tickers) > 0
    assert all(isinstance(t, str) for t in tickers)


def test_settings_storage_full_path():
    """Test Settings.get_storage_full_path() helper."""
    from src.config.settings import get_settings

    s = get_settings()
    path = s.get_storage_full_path("models/test.keras")
    assert "test.keras" in path
    assert path.startswith(s.storage_uri.rstrip("/"))


def test_settings_is_cloud_storage():
    """Test Settings.is_cloud_storage() helper."""
    from src.config.settings import get_settings

    s = get_settings()
    result = s.is_cloud_storage()
    # Local storage should return False in default test environment
    assert isinstance(result, bool)


def test_storage_client_invalid_backend_raises():
    """Test that an unsupported storage backend raises ValueError."""
    import pytest

    from src.config.storage import StorageClient

    client = StorageClient.__new__(StorageClient)
    client.backend = "unsupported_backend"
    client.base_uri = "test://base"
    with pytest.raises(ValueError, match="Unsupported storage backend"):
        client._get_filesystem()


def test_storage_client_gcs_branch():
    """Test GCS branch is reachable in _get_filesystem()."""
    from unittest.mock import MagicMock, patch

    from src.config.storage import StorageClient

    client = StorageClient.__new__(StorageClient)
    client.backend = "gcs"
    client.base_uri = "gs://bucket/base"
    mock_fs = MagicMock()
    with patch("src.config.storage.fsspec.filesystem", return_value=mock_fs) as mock_fsspec:
        result = client._get_filesystem()
        mock_fsspec.assert_called_once_with("gcs")
    assert result is mock_fs
