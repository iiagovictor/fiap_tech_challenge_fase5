"""
Testes de schema com Pandera.
Cobre casos válidos, nulos, valores fora de range e invariantes OHLCV.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pandera as pa
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from schema import (
    RawOHLCVSchema,
    ProcessedOHLCVSchema,
    validate_raw,
    validate_processed,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def valid_raw_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
            "Open":   [185.0, 186.0, 187.5],
            "High":   [188.0, 189.0, 190.0],
            "Low":    [184.0, 185.0, 186.0],
            "Close":  [187.0, 188.0, 189.0],
            "Volume": [50_000_000.0, 48_000_000.0, 52_000_000.0],
            "Ticker": ["AAPL", "AAPL", "AAPL"],
        }
    )


@pytest.fixture
def valid_processed_df(valid_raw_df: pd.DataFrame) -> pd.DataFrame:
    df = valid_raw_df.copy()
    df["Daily_Return"] = df["Close"].pct_change()
    df["Price_Range"] = df["High"] - df["Low"]
    return df


# ── Testes: schema raw válido ──────────────────────────────────────────────────

class TestRawSchemaValid:
    def test_passes_with_valid_data(self, valid_raw_df):
        result = validate_raw(valid_raw_df)
        assert len(result) == len(valid_raw_df)

    def test_allows_extra_columns(self, valid_raw_df):
        df = valid_raw_df.copy()
        df["Dividends"] = 0.0
        result = validate_raw(df)
        assert "Dividends" in result.columns


# ── Testes: nulos ──────────────────────────────────────────────────────────────

class TestNullChecks:
    @pytest.mark.parametrize("col", ["Open", "High", "Low", "Close", "Volume", "Ticker"])
    def test_null_in_required_column_fails(self, valid_raw_df, col):
        df = valid_raw_df.copy()
        df.loc[0, col] = None
        with pytest.raises(pa.errors.SchemaErrors):
            validate_raw(df)


# ── Testes: range de valores ───────────────────────────────────────────────────

class TestRangeChecks:
    @pytest.mark.parametrize("col", ["Open", "High", "Low", "Close"])
    def test_negative_price_fails(self, valid_raw_df, col):
        df = valid_raw_df.copy()
        df.loc[0, col] = -1.0
        with pytest.raises(pa.errors.SchemaErrors):
            validate_raw(df)

    @pytest.mark.parametrize("col", ["Open", "High", "Low", "Close"])
    def test_zero_price_fails(self, valid_raw_df, col):
        df = valid_raw_df.copy()
        df.loc[0, col] = 0.0
        with pytest.raises(pa.errors.SchemaErrors):
            validate_raw(df)

    def test_negative_volume_fails(self, valid_raw_df):
        df = valid_raw_df.copy()
        df.loc[0, "Volume"] = -100.0
        with pytest.raises(pa.errors.SchemaErrors):
            validate_raw(df)

    def test_zero_volume_is_valid(self, valid_raw_df):
        """Volume zero é válido — pode ocorrer em feriados ou halts."""
        df = valid_raw_df.copy()
        df.loc[0, "Volume"] = 0.0
        result = validate_raw(df)
        assert result.loc[0, "Volume"] == 0.0


# ── Testes: invariantes OHLCV ──────────────────────────────────────────────────

class TestOHLCVInvariants:
    def test_high_lt_low_fails(self, valid_raw_df):
        df = valid_raw_df.copy()
        df.loc[0, "High"] = 183.0  # High < Low
        with pytest.raises(pa.errors.SchemaErrors):
            validate_raw(df)

    def test_high_lt_open_fails(self, valid_raw_df):
        df = valid_raw_df.copy()
        df.loc[0, "High"] = 184.5  # High < Open (Open=185)
        with pytest.raises(pa.errors.SchemaErrors):
            validate_raw(df)

    def test_high_lt_close_fails(self, valid_raw_df):
        df = valid_raw_df.copy()
        df.loc[0, "High"] = 186.5  # High < Close (Close=187)
        with pytest.raises(pa.errors.SchemaErrors):
            validate_raw(df)

    def test_low_gt_open_fails(self, valid_raw_df):
        df = valid_raw_df.copy()
        df.loc[0, "Low"] = 186.0  # Low > Open (Open=185)
        with pytest.raises(pa.errors.SchemaErrors):
            validate_raw(df)

    def test_high_equals_low_is_valid(self, valid_raw_df):
        """Candle doji — High == Low — é válido (leilão ou halt)."""
        df = valid_raw_df.copy()
        df.loc[0, ["Open", "High", "Low", "Close"]] = [185.0, 185.0, 185.0, 185.0]
        result = validate_raw(df)
        assert len(result) == len(valid_raw_df)


# ── Testes: schema processed ───────────────────────────────────────────────────

class TestProcessedSchema:
    def test_passes_with_enriched_data(self, valid_processed_df):
        result = validate_processed(valid_processed_df)
        assert "Daily_Return" in result.columns
        assert "Price_Range" in result.columns

    def test_daily_return_nullable(self, valid_processed_df):
        """Primeiro dia de cada ticker tem Daily_Return nulo — deve ser aceito."""
        df = valid_processed_df.copy()
        df.loc[0, "Daily_Return"] = None
        result = validate_processed(df)
        assert pd.isna(result.loc[0, "Daily_Return"])

    def test_negative_price_range_fails(self, valid_processed_df):
        df = valid_processed_df.copy()
        df.loc[0, "Price_Range"] = -1.0
        with pytest.raises(pa.errors.SchemaErrors):
            validate_processed(df)

    def test_missing_daily_return_column_fails(self, valid_raw_df):
        """ProcessedOHLCVSchema exige Daily_Return — sem ela deve falhar."""
        with pytest.raises(pa.errors.SchemaErrors):
            validate_processed(valid_raw_df)