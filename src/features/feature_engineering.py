"""
Feature engineering for stock price prediction.

Generates technical indicators (RSI, MACD, Bollinger Bands, EMAs, ATR, OBV)
and creates target variable (price direction) for model training.
"""

import logging

import numpy as np
import pandas as pd

from src.config.storage import get_storage
from src.data.schemas import validate_features, validate_training_data

logger = logging.getLogger(__name__)
storage = get_storage()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Returns:
        macd, signal_line, histogram
    """
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()

    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line

    return macd, signal_line, histogram


def calculate_bollinger_bands(
    series: pd.Series, period: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands.

    Returns:
        upper_band, middle_band, lower_band
    """
    middle = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()

    upper = middle + (std * num_std)
    lower = middle - (std * num_std)

    return upper, middle, lower


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Average True Range (ATR)."""
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())

    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()

    return atr


def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Calculate On-Balance Volume (OBV)."""
    obv = np.sign(close.diff()).fillna(0).mul(volume).cumsum()
    return obv


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add technical indicators to stock data.

    Args:
        df: DataFrame with columns [date, ticker, open, high, low, close, volume]

    Returns:
        DataFrame with added technical indicator columns
    """
    logger.info("Calculating technical indicators...")

    # Sort by ticker and date to ensure correct calculations
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    # Group by ticker and calculate indicators
    result_dfs = []
    for ticker, group in df.groupby("ticker"):
        logger.debug(f"Processing ticker: {ticker}")

        # Make a copy to avoid SettingWithCopyWarning
        group = group.copy()

        # Simple Moving Averages
        group["sma_5"] = group["close"].rolling(window=5).mean()
        group["sma_10"] = group["close"].rolling(window=10).mean()
        group["sma_20"] = group["close"].rolling(window=20).mean()
        group["sma_50"] = group["close"].rolling(window=50).mean()

        # Exponential Moving Averages
        group["ema_12"] = group["close"].ewm(span=12, adjust=False).mean()
        group["ema_26"] = group["close"].ewm(span=26, adjust=False).mean()

        # RSI
        group["rsi_14"] = calculate_rsi(group["close"], period=14)

        # MACD
        macd, signal, histogram = calculate_macd(group["close"])
        group["macd"] = macd
        group["macd_signal"] = signal
        group["macd_histogram"] = histogram

        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(group["close"])
        group["bb_upper"] = bb_upper
        group["bb_middle"] = bb_middle
        group["bb_lower"] = bb_lower
        group["bb_width"] = (bb_upper - bb_lower) / bb_middle

        # ATR (Average True Range)
        group["atr_14"] = calculate_atr(group["high"], group["low"], group["close"], period=14)

        # OBV (On-Balance Volume)
        group["obv"] = calculate_obv(group["close"], group["volume"])

        # Volume moving average
        group["volume_ma_20"] = group["volume"].rolling(window=20).mean()

        # Price changes
        group["price_change"] = group["close"].pct_change()
        group["price_change_5d"] = group["close"].pct_change(periods=5)

        result_dfs.append(group)

    # Concatenate all ticker groups
    df_features = pd.concat(result_dfs, ignore_index=True)

    logger.info(f"Added {len(df_features.columns) - len(df.columns)} technical indicators")

    # Validate against schema
    try:
        df_features = validate_features(df_features)
        logger.info("✅ Features validated against FEATURE_SET_SCHEMA")
    except Exception as e:
        logger.error(f"Schema validation failed: {e}")
        raise

    return df_features


def create_target_variable(df: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    """
    Create target variable: binary direction of price movement after N days.

    Args:
        df: DataFrame with stock data and features
        horizon: Number of days to look ahead (default: 5)

    Returns:
        DataFrame with added 'target' column (1 = up, 0 = down)
    """
    logger.info(f"Creating target variable with {horizon}-day horizon...")

    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)

    result_dfs = []
    for _ticker, group in df.groupby("ticker"):
        group = group.copy()

        # Future close price after N days
        group["close_future"] = group["close"].shift(-horizon)

        # Target: 1 if price goes up, 0 if goes down
        group["target"] = (group["close_future"] > group["close"]).astype(int)

        result_dfs.append(group)

    df_target = pd.concat(result_dfs, ignore_index=True)

    # Remove rows where we can't calculate target (last N days)
    df_target = df_target.dropna(subset=["target"])

    logger.info(f"Target variable created. Rows with target: {len(df_target):,}")
    logger.info(f"Class distribution: {df_target['target'].value_counts(normalize=True).to_dict()}")

    # Validate against schema
    try:
        df_target = validate_training_data(df_target)
        logger.info("✅ Training data validated against TRAINING_DATA_SCHEMA")
    except Exception as e:
        logger.error(f"Schema validation failed: {e}")
        raise

    return df_target


def feature_engineering_pipeline(
    input_path: str = "raw/raw_stock_data.parquet",
    output_path: str = "features/stock_features.parquet",
    target_horizon: int = 5,
) -> pd.DataFrame:
    """
    Main feature engineering pipeline.

    Args:
        input_path: Path to raw stock data
        output_path: Path to save engineered features
        target_horizon: Days ahead for target variable

    Returns:
        DataFrame with features and target
    """
    # Load raw data
    logger.info(f"Loading raw data from {input_path}...")
    df = storage.read_parquet(input_path)
    logger.info(f"Loaded {len(df):,} rows")

    # Add technical indicators
    df_features = add_technical_indicators(df)

    # Create target variable
    df_final = create_target_variable(df_features, horizon=target_horizon)

    # Drop temporary columns
    df_final = df_final.drop(columns=["close_future"], errors="ignore")

    # Remove rows with NaN (from rolling calculations)
    rows_before = len(df_final)
    df_final = df_final.dropna()
    rows_after = len(df_final)
    logger.info(f"Dropped {rows_before - rows_after} rows with NaN values")

    # Save to storage
    logger.info(f"Saving features to {output_path}...")
    storage.write_parquet(df_final, output_path)
    logger.info(f"Saved {len(df_final):,} rows with {len(df_final.columns)} columns")

    return df_final


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run feature engineering pipeline
    features = feature_engineering_pipeline()
    print(f"\n✅ Feature engineering complete: {len(features):,} rows")
    print(f"Features: {len(features.columns)} columns")
    print(f"\nColumn names:\n{list(features.columns)}")
