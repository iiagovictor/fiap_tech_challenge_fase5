"""Tests for src/agent/tools.py — financial analysis tools for the LLM agent."""

from unittest.mock import MagicMock, patch

import pandas as pd

from src.agent.tools import (
    TOOLS,
    _generate_recommendation,
    _interpret_indicators,
    calculate_technical_indicators,
    compare_stocks,
    get_stock_price_history,
    predict_stock_direction,
)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _make_hist_df(n: int = 60, close_start: float = 30.0) -> pd.DataFrame:
    """Return a minimal yfinance-style DataFrame."""
    import numpy as np

    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    close = close_start + np.random.default_rng(0).normal(0, 0.5, n).cumsum()
    return pd.DataFrame(
        {
            "Open": close - 0.1,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": [1_000_000] * n,
        },
        index=dates,
    )


# ──────────────────────────────────────────────────────────────────────────────
# _interpret_indicators  (pure function — no network)
# ──────────────────────────────────────────────────────────────────────────────


class TestInterpretIndicators:
    def test_overbought_bullish(self):
        result = _interpret_indicators(rsi=75.0, price=35.0, sma_20=30.0, sma_50=28.0)
        assert "overbought" in result
        assert "bullish" in result

    def test_oversold_bearish(self):
        result = _interpret_indicators(rsi=25.0, price=25.0, sma_20=30.0, sma_50=32.0)
        assert "oversold" in result
        assert "bearish" in result

    def test_neutral_rsi_mixed_trend(self):
        result = _interpret_indicators(rsi=50.0, price=30.0, sma_20=31.0, sma_50=29.0)
        assert "neutral RSI" in result
        assert "mixed trend" in result

    def test_neutral_rsi_above_50_bullish_trend(self):
        result = _interpret_indicators(rsi=55.0, price=35.0, sma_20=32.0, sma_50=30.0)
        assert "bullish trend" in result

    def test_returns_string(self):
        result = _interpret_indicators(50.0, 30.0, 30.0, 30.0)
        assert isinstance(result, str)
        assert len(result) > 0


# ──────────────────────────────────────────────────────────────────────────────
# _generate_recommendation  (pure function — no network)
# ──────────────────────────────────────────────────────────────────────────────


class TestGenerateRecommendation:
    def test_strong_buy(self):
        result = _generate_recommendation(prediction=1, probability=0.8)
        assert "COMPRA FORTE" in result

    def test_strong_sell(self):
        result = _generate_recommendation(prediction=0, probability=0.8)
        assert "VENDA FORTE" in result

    def test_moderate_buy(self):
        result = _generate_recommendation(prediction=1, probability=0.65)
        assert "COMPRA" in result

    def test_moderate_sell(self):
        result = _generate_recommendation(prediction=0, probability=0.65)
        assert "VENDA" in result

    def test_neutral(self):
        result = _generate_recommendation(prediction=1, probability=0.52)
        assert "NEUTRO" in result

    def test_returns_non_empty_string(self):
        for pred in (0, 1):
            for prob in (0.2, 0.5, 0.65, 0.8):
                assert isinstance(_generate_recommendation(pred, prob), str)


# ──────────────────────────────────────────────────────────────────────────────
# get_stock_price_history  (yfinance mocked)
# ──────────────────────────────────────────────────────────────────────────────


class TestGetStockPriceHistory:
    def _mock_ticker(self, hist_df):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist_df
        return mock_ticker

    def test_returns_expected_keys(self):
        hist = _make_hist_df(30)
        with patch("src.agent.tools.yf.Ticker", return_value=self._mock_ticker(hist)):
            result = get_stock_price_history("ITUB4.SA", period="1mo")

        for key in (
            "ticker",
            "period",
            "current_price",
            "start_price",
            "high_price",
            "low_price",
            "price_change",
            "price_change_pct",
            "avg_volume",
            "data_points",
        ):
            assert key in result, f"Missing key: {key}"

    def test_ticker_and_period_propagated(self):
        hist = _make_hist_df(10)
        with patch("src.agent.tools.yf.Ticker", return_value=self._mock_ticker(hist)):
            result = get_stock_price_history("PETR4.SA", period="5d")

        assert result["ticker"] == "PETR4.SA"
        assert result["period"] == "5d"

    def test_empty_hist_returns_error(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        with patch("src.agent.tools.yf.Ticker", return_value=mock_ticker):
            result = get_stock_price_history("INVALID.SA")

        assert "error" in result

    def test_exception_returns_error(self):
        with patch("src.agent.tools.yf.Ticker", side_effect=RuntimeError("network fail")):
            result = get_stock_price_history("ITUB4.SA")

        assert "error" in result

    def test_data_points_matches_hist_length(self):
        hist = _make_hist_df(20)
        with patch("src.agent.tools.yf.Ticker", return_value=self._mock_ticker(hist)):
            result = get_stock_price_history("VALE3.SA", period="1mo")

        assert result["data_points"] == 20


# ──────────────────────────────────────────────────────────────────────────────
# calculate_technical_indicators  (yfinance mocked)
# ──────────────────────────────────────────────────────────────────────────────


class TestCalculateTechnicalIndicators:
    def _mock_ticker(self, hist_df):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = hist_df
        return mock_ticker

    def test_returns_expected_keys(self):
        hist = _make_hist_df(60)
        with patch("src.agent.tools.yf.Ticker", return_value=self._mock_ticker(hist)):
            result = calculate_technical_indicators("ITUB4.SA", period="3mo")

        for key in (
            "ticker",
            "current_price",
            "rsi_14",
            "sma_20",
            "sma_50",
            "ema_12",
            "ema_26",
            "macd",
            "bb_upper",
            "bb_middle",
            "bb_lower",
            "signal",
        ):
            assert key in result, f"Missing key: {key}"

    def test_insufficient_data_returns_error(self):
        hist = _make_hist_df(10)  # < 50 required
        with patch("src.agent.tools.yf.Ticker", return_value=self._mock_ticker(hist)):
            result = calculate_technical_indicators("ITUB4.SA")

        assert "error" in result

    def test_empty_data_returns_error(self):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        with patch("src.agent.tools.yf.Ticker", return_value=mock_ticker):
            result = calculate_technical_indicators("INVALID.SA")

        assert "error" in result

    def test_exception_returns_error(self):
        with patch("src.agent.tools.yf.Ticker", side_effect=RuntimeError("fail")):
            result = calculate_technical_indicators("ITUB4.SA")

        assert "error" in result

    def test_signal_is_string(self):
        hist = _make_hist_df(60)
        with patch("src.agent.tools.yf.Ticker", return_value=self._mock_ticker(hist)):
            result = calculate_technical_indicators("ITUB4.SA")

        assert isinstance(result.get("signal"), str)


# ──────────────────────────────────────────────────────────────────────────────
# compare_stocks  (yfinance mocked)
# ──────────────────────────────────────────────────────────────────────────────


class TestCompareStocks:
    def _mock_price_data(self, ticker: str, pct: float) -> dict:
        return {
            "ticker": ticker,
            "period": "1mo",
            "current_price": 30.0,
            "start_price": 30.0 / (1 + pct / 100),
            "high_price": 32.0,
            "low_price": 28.0,
            "price_change": 30.0 * pct / 100,
            "price_change_pct": pct,
            "avg_volume": 1_000_000,
            "data_points": 20,
        }

    def test_compare_two_stocks(self):
        def fake_history(ticker, period="1mo"):
            pct = 5.0 if ticker == "ITUB4.SA" else -2.0
            return self._mock_price_data(ticker, pct)

        with patch("src.agent.tools.get_stock_price_history", side_effect=fake_history):
            result = compare_stocks(["ITUB4.SA", "PETR4.SA"])

        assert result["stocks_compared"] == 2
        assert result["best_performer"] == "ITUB4.SA"
        assert result["worst_performer"] == "PETR4.SA"

    def test_all_invalid_returns_error(self):
        with patch("src.agent.tools.get_stock_price_history", return_value={"error": "no data"}):
            result = compare_stocks(["INVALID1.SA", "INVALID2.SA"])

        assert "error" in result

    def test_result_contains_required_keys(self):
        def fake_history(ticker, period="1mo"):
            return self._mock_price_data(ticker, 1.0)

        with patch("src.agent.tools.get_stock_price_history", side_effect=fake_history):
            result = compare_stocks(["ITUB4.SA", "VALE3.SA", "PETR4.SA"])

        assert "period" in result
        assert "stocks_compared" in result
        assert result["stocks_compared"] == 3


# ──────────────────────────────────────────────────────────────────────────────
# predict_stock_direction  (API unavailable → falls back to technical indicators)
# ──────────────────────────────────────────────────────────────────────────────


def _no_api():
    """Force the httpx API call to fail so the technical-indicator fallback runs."""
    return patch("httpx.post", side_effect=ConnectionError("no server"))


class TestPredictStockDirection:
    def _mock_indicators(self, rsi=55.0, price=35.0, sma20=32.0, sma50=30.0):
        return {
            "ticker": "ITUB4.SA",
            "current_price": price,
            "rsi_14": rsi,
            "sma_20": sma20,
            "sma_50": sma50,
        }

    def test_fallback_returns_expected_keys(self):
        with (
            _no_api(),
            patch(
                "src.agent.tools.calculate_technical_indicators",
                return_value=self._mock_indicators(),
            ),
        ):
            result = predict_stock_direction("ITUB4.SA")

        for key in (
            "ticker",
            "prediction",
            "probability_up",
            "probability_down",
            "confidence",
            "model",
            "recommendation",
        ):
            assert key in result, f"Missing key: {key}"

    def test_oversold_predicts_up(self):
        with (
            _no_api(),
            patch(
                "src.agent.tools.calculate_technical_indicators",
                return_value=self._mock_indicators(rsi=20.0, price=35.0, sma20=32.0, sma50=30.0),
            ),
        ):
            result = predict_stock_direction("ITUB4.SA")

        assert result.get("prediction") == "valorização"

    def test_overbought_bearish_predicts_down(self):
        with (
            _no_api(),
            patch(
                "src.agent.tools.calculate_technical_indicators",
                return_value=self._mock_indicators(rsi=80.0, price=25.0, sma20=30.0, sma50=32.0),
            ),
        ):
            result = predict_stock_direction("ITUB4.SA")

        assert result.get("prediction") == "desvalorização"

    def test_indicators_error_propagated(self):
        with (
            _no_api(),
            patch(
                "src.agent.tools.calculate_technical_indicators", return_value={"error": "no data"}
            ),
        ):
            result = predict_stock_direction("INVALID.SA")

        assert "error" in result

    def test_probability_up_and_down_sum_to_100(self):
        with (
            _no_api(),
            patch(
                "src.agent.tools.calculate_technical_indicators",
                return_value=self._mock_indicators(),
            ),
        ):
            result = predict_stock_direction("ITUB4.SA")

        assert abs(result["probability_up"] + result["probability_down"] - 100.0) < 0.01


# ──────────────────────────────────────────────────────────────────────────────
# TOOLS metadata list
# ──────────────────────────────────────────────────────────────────────────────


class TestToolsMetadata:
    def test_tools_is_list(self):
        assert isinstance(TOOLS, list)
        assert len(TOOLS) == 4

    def test_each_tool_has_required_keys(self):
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert "function" in tool
            assert callable(tool["function"])

    def test_tool_names(self):
        names = [t["name"] for t in TOOLS]
        assert "get_stock_price_history" in names
        assert "calculate_technical_indicators" in names
        assert "predict_stock_direction" in names
        assert "compare_stocks" in names
