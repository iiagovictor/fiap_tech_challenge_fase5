"""Tests for feature engineering."""

import pandas as pd
import pytest

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
    assert (atr >= 0).all()


def test_calculate_obv(sample_stock_data):
    """Test OBV calculation."""
    df = sample_stock_data
    obv = calculate_obv(df["close"], df["volume"])

    assert len(obv) == len(df)


def test_add_technical_indicators(sample_stock_data):
    """Test adding all technical indicators."""
    df_features = add_technical_indicators(sample_stock_data)

    # Check new columns were added
    assert "sma_5" in df_features.columns
    assert "rsi_14" in df_features.columns
    assert "macd" in df_features.columns
    assert "bb_upper" in df_features.columns

    # Check no NaN in recent data (last 50 days should have all indicators)
    assert df_features.iloc[-50:].notna().all().all()


def test_create_target_variable(sample_stock_data):
    """Test target variable creation."""
    df_features = add_technical_indicators(sample_stock_data)
    df_with_target = create_target_variable(df_features, horizon=5)

    # Check target column exists
    assert "target" in df_with_target.columns

    # Check target is binary
    assert df_with_target["target"].isin([0, 1]).all()

    # Check target has reasonable class balance (should be around 50%)
    target_mean = df_with_target["target"].mean()
    assert 0.3 < target_mean < 0.7  # Allow some imbalance
