"""
Data validation schemas using Pandera.

Defines DataFrameSchema for raw stock data, feature sets, and training datasets.
"""

import pandas as pd
import pandera as pa
from pandera import Column, DataFrameSchema

# ============================================================
# Raw Stock Data Schema
# ============================================================
RAW_STOCK_DATA_SCHEMA = DataFrameSchema(
    columns={
        "date": Column(pa.DateTime, nullable=False),
        "ticker": Column(pa.String, nullable=False),
        "open": Column(pa.Float64, nullable=False),
        "high": Column(pa.Float64, nullable=False),
        "low": Column(pa.Float64, nullable=False),
        "close": Column(pa.Float64, nullable=False),
        "volume": Column(pa.Int64, nullable=False),
    },
    strict=False,
    coerce=True,
)


# ============================================================
# Feature Set Schema (after feature engineering)
# ============================================================
FEATURE_SET_SCHEMA = DataFrameSchema(
    columns={
        "date": Column(pa.DateTime, nullable=False),
        "ticker": Column(pa.String, nullable=False),
        "open": Column(pa.Float64, nullable=False),
        "high": Column(pa.Float64, nullable=False),
        "low": Column(pa.Float64, nullable=False),
        "close": Column(pa.Float64, nullable=False),
        "volume": Column(pa.Int64, nullable=False),
        # Technical indicators (may have NaN in warmup period)
        "sma_5": Column(pa.Float64, nullable=True),
        "sma_10": Column(pa.Float64, nullable=True),
        "sma_20": Column(pa.Float64, nullable=True),
        "sma_50": Column(pa.Float64, nullable=True),
        "ema_12": Column(pa.Float64, nullable=True),
        "ema_26": Column(pa.Float64, nullable=True),
        "rsi_14": Column(pa.Float64, nullable=True),
        "macd": Column(pa.Float64, nullable=True),
        "macd_signal": Column(pa.Float64, nullable=True),
        "macd_histogram": Column(pa.Float64, nullable=True),
        "bb_upper": Column(pa.Float64, nullable=True),
        "bb_middle": Column(pa.Float64, nullable=True),
        "bb_lower": Column(pa.Float64, nullable=True),
        "bb_width": Column(pa.Float64, nullable=True),
        "atr_14": Column(pa.Float64, nullable=True),
        "obv": Column(pa.Float64, nullable=True),
        "volume_ma_20": Column(pa.Float64, nullable=True),
        "price_change": Column(pa.Float64, nullable=True),
        "price_change_5d": Column(pa.Float64, nullable=True),
    },
    strict=False,
    coerce=True,
)


# ============================================================
# Training Dataset Schema (features + target)
# ============================================================
TRAINING_DATA_SCHEMA = DataFrameSchema(
    columns={
        **FEATURE_SET_SCHEMA.columns,
        "target": Column(pa.Int64, nullable=False),
    },
    strict=False,
    coerce=True,
)


# ============================================================
# Test Set Schema (training data without target, for predictions)
# ============================================================
TEST_FEATURES_SCHEMA = DataFrameSchema(
    columns={
        col: FEATURE_SET_SCHEMA.columns[col]
        for col in FEATURE_SET_SCHEMA.columns
        if col not in ["date", "ticker"]
    },
    strict=False,
    coerce=True,
)


def validate_raw_data(df: pd.DataFrame) -> pd.DataFrame:
    """Validate raw stock data against schema."""
    return RAW_STOCK_DATA_SCHEMA.validate(df)


def validate_features(df: pd.DataFrame) -> pd.DataFrame:
    """Validate feature set against schema."""
    return FEATURE_SET_SCHEMA.validate(df)


def validate_training_data(df: pd.DataFrame) -> pd.DataFrame:
    """Validate training dataset against schema."""
    return TRAINING_DATA_SCHEMA.validate(df)


def validate_test_features(df) -> pd.DataFrame:
    """Validate test features against schema."""
    return TEST_FEATURES_SCHEMA.validate(df)
