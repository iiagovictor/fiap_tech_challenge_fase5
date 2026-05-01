"""Pytest configuration and shared fixtures."""

import os
from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.config.settings import Settings


@pytest.fixture(scope="session")
def test_settings():
    """Create test settings with local storage."""
    return Settings(
        storage_backend="local",
        storage_uri="data/test/",
        mlflow_tracking_uri="sqlite:///test_mlflow.db",
        redis_url="redis://localhost:6379",
        llm_model="ollama/llama3",
        llm_base_url="http://localhost:11434",
    )


@pytest.fixture
def sample_stock_data():
    """Create sample stock data for testing."""
    dates = pd.date_range(start="2024-01-01", end="2024-01-31", freq="D")
    tickers = ["ITUB4.SA", "PETR4.SA"]

    data = []
    for ticker in tickers:
        for date in dates:
            data.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "open": 30.0 + (len(data) * 0.1),
                    "high": 31.0 + (len(data) * 0.1),
                    "low": 29.0 + (len(data) * 0.1),
                    "close": 30.5 + (len(data) * 0.1),
                    "volume": 1000000 + (len(data) * 1000),
                }
            )

    return pd.DataFrame(data)


@pytest.fixture
def sample_features():
    """Create sample feature data for testing."""
    dates = pd.date_range(start="2024-01-01", end="2024-01-31", freq="D")

    data = []
    for i, date in enumerate(dates):
        data.append(
            {
                "date": date,
                "ticker": "ITUB4.SA",
                "close": 30.0 + i * 0.1,
                "sma_5": 30.0 + i * 0.1,
                "sma_20": 30.0 + i * 0.1,
                "rsi_14": 50.0,
                "macd": 0.1,
                "target": i % 2,  # Alternating 0 and 1
            }
        )

    return pd.DataFrame(data)


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Clean up test data after each test."""
    yield
    # Add cleanup logic if needed
    pass


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return {
        "role": "assistant",
        "content": "Based on technical analysis, ITUB4.SA shows bullish momentum with RSI at 65 and MACD crossing above signal line.",
    }
