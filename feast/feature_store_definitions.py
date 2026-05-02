"""
Feast Feature Store definitions for stock prediction features.

Defines entities, feature views, and feature services for online/offline serving.
"""

from datetime import timedelta
from pathlib import Path

from feast import Entity, FeatureService, FeatureView, Field, FileSource, ValueType
from feast.types import Float32, Int64

# Paths computed relative to this file so the registry works on any machine
_FEAST_DIR = Path(__file__).parent
_PROJECT_ROOT = _FEAST_DIR.parent
_FEATURES_PATH = str(_PROJECT_ROOT / "data" / "features" / "stock_features.parquet")

# ============================================================
# Entity: Stock Ticker
# ============================================================
stock = Entity(
    name="ticker",
    value_type=ValueType.STRING,
    description="Stock ticker symbol (e.g., ITUB4.SA)",
)

# ============================================================
# Offline Source: Parquet files from storage
# ============================================================
stock_features_source = FileSource(
    path=_FEATURES_PATH,
    timestamp_field="date",
)

# ============================================================
# Feature View: Technical Indicators
# ============================================================
stock_technical_features = FeatureView(
    name="stock_technical_features",
    entities=[stock],
    ttl=timedelta(days=1),
    schema=[
        Field(name="open", dtype=Float32),
        Field(name="high", dtype=Float32),
        Field(name="low", dtype=Float32),
        Field(name="close", dtype=Float32),
        Field(name="volume", dtype=Float32),
        Field(name="sma_5", dtype=Float32),
        Field(name="sma_10", dtype=Float32),
        Field(name="sma_20", dtype=Float32),
        Field(name="sma_50", dtype=Float32),
        Field(name="ema_12", dtype=Float32),
        Field(name="ema_26", dtype=Float32),
        Field(name="rsi_14", dtype=Float32),
        Field(name="macd", dtype=Float32),
        Field(name="macd_signal", dtype=Float32),
        Field(name="macd_histogram", dtype=Float32),
        Field(name="bb_upper", dtype=Float32),
        Field(name="bb_middle", dtype=Float32),
        Field(name="bb_lower", dtype=Float32),
        Field(name="bb_width", dtype=Float32),
        Field(name="atr_14", dtype=Float32),
        Field(name="obv", dtype=Float32),
        Field(name="volume_ma_20", dtype=Float32),
        Field(name="price_change", dtype=Float32),
        Field(name="price_change_5d", dtype=Float32),
        Field(name="target", dtype=Int64),
    ],
    online=True,
    source=stock_features_source,
    tags={"team": "data-science", "project": "fiap-tech-challenge-fase5"},
)

# ============================================================
# Feature Service: All features for model prediction
# ============================================================
stock_prediction_service = FeatureService(
    name="stock_prediction_service",
    features=[stock_technical_features],
    tags={"use_case": "lstm_prediction"},
)
