"""
Data ingestion from Yahoo Finance using yfinance.

Downloads historical stock data for configured tickers and saves to storage.
Handles yfinance MultiIndex columns correctly (fix for tuple columns bug).
"""

import logging
from datetime import datetime

import pandas as pd
import yfinance as yf

from src.config.settings import get_settings
from src.config.storage import get_storage
from src.data.schemas import validate_raw_data

logger = logging.getLogger(__name__)
settings = get_settings()
storage = get_storage()


def download_stock_data(
    tickers: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Download historical stock data from Yahoo Finance.

    Args:
        tickers: List of ticker symbols (e.g., ["ITUB4.SA", "PETR4.SA"])
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format (default: today)
        interval: Data interval (1d, 1h, etc.)

    Returns:
        DataFrame with columns: [date, ticker, open, high, low, close, volume]

    Raises:
        ValueError: If no data is downloaded
    """
    if tickers is None:
        tickers = settings.get_tickers_list()

    if start_date is None:
        start_date = settings.data_start_date

    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"Downloading data for {len(tickers)} tickers from {start_date} to {end_date}")

    # Download data using yfinance
    # Use group_by='column' for easier processing (avoids MultiIndex ticker complexity)
    df = yf.download(
        tickers=tickers,
        start=start_date,
        end=end_date,
        interval=interval,
        progress=False,
        group_by="column",  # Returns columns like ('Open', 'ITUB4.SA')
        auto_adjust=True,
    )

    if df.empty:
        raise ValueError(f"No data downloaded for tickers: {tickers}")

    # ============================================================
    # Process yfinance MultiIndex format
    # ============================================================
    # Reset index to convert Date from index to column
    df = df.reset_index()

    if len(tickers) == 1:
        # Single ticker: simple column names (Open, High, Low, Close, Volume, Date)
        df.columns = [str(c).lower() for c in df.columns]
        df["ticker"] = tickers[0]
    else:
        # Multiple tickers with group_by='column': MultiIndex like ('Open', 'ITUB4.SA')
        # Need to melt from wide to long format
        if isinstance(df.columns, pd.MultiIndex):
            # Melt the DataFrame to long format
            df_melted_list = []

            for ticker in tickers:
                # Extract columns for this ticker
                ticker_data = {}
                ticker_data["date"] = df["Date"] if "Date" in df.columns else df.index

                for col in ["Open", "High", "Low", "Close", "Volume"]:
                    if (col, ticker) in df.columns:
                        ticker_data[col.lower()] = df[(col, ticker)]

                df_ticker_clean = pd.DataFrame(ticker_data)
                df_ticker_clean["ticker"] = ticker
                df_melted_list.append(df_ticker_clean)

            df = pd.concat(df_melted_list, ignore_index=True)
        else:
            # Fallback: simple columns
            df.columns = [str(c).lower() for c in df.columns]
            if "ticker" not in df.columns and len(tickers) == 1:
                df["ticker"] = tickers[0]

    # Standardize column names
    if "Date" in df.columns:
        df.rename(columns={"Date": "date"}, inplace=True)

    # Select and order standard columns
    standard_columns = ["date", "ticker", "open", "high", "low", "close", "volume"]
    available_columns = [c for c in standard_columns if c in df.columns]
    df = df[available_columns].copy()

    # Sort by date and ticker
    df = df.sort_values(["date", "ticker"]).reset_index(drop=True)

    logger.info(f"Downloaded {len(df):,} rows for {df['ticker'].nunique()} tickers")
    logger.info(f"Date range: {df['date'].min()} to {df['date'].max()}")

    # Validate against schema
    try:
        df = validate_raw_data(df)
        logger.info("✅ Data validated against RAW_STOCK_DATA_SCHEMA")
    except Exception as e:
        logger.error(f"Schema validation failed: {e}")
        raise

    return df


def save_raw_data(df: pd.DataFrame, filename: str = "raw_stock_data.parquet") -> str:
    """
    Save raw stock data to storage.

    Args:
        df: DataFrame with stock data
        filename: Output filename (default: raw_stock_data.parquet)

    Returns:
        Full path where data was saved
    """
    output_path = f"raw/{filename}"
    storage.write_parquet(df, output_path)
    logger.info(f"Saved raw data to {output_path} ({len(df):,} rows)")
    return output_path


def load_raw_data(filename: str = "raw_stock_data.parquet") -> pd.DataFrame:
    """
    Load raw stock data from storage.

    Args:
        filename: Input filename

    Returns:
        DataFrame with stock data
    """
    path = f"raw/{filename}"
    if not storage.exists(path):
        raise FileNotFoundError(f"Raw data not found at {path}")

    df = storage.read_parquet(path)
    logger.info(f"Loaded raw data from {path} ({len(df):,} rows)")
    return df


def ingest_pipeline(force_download: bool = False) -> pd.DataFrame:
    """
    Main ingestion pipeline: download data and save to storage.

    Args:
        force_download: If True, always download. If False, load from storage if exists.

    Returns:
        DataFrame with raw stock data
    """
    raw_data_path = "raw/raw_stock_data.parquet"

    # Check if data already exists
    if not force_download and storage.exists(raw_data_path):
        logger.info("Raw data already exists in storage. Loading existing data...")
        logger.info("Use force_download=True to download fresh data.")
        return load_raw_data()

    # Download fresh data
    logger.info("Downloading fresh stock data from Yahoo Finance...")
    df = download_stock_data()

    # Save to storage
    save_raw_data(df)

    return df


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run ingestion pipeline
    data = ingest_pipeline(force_download=True)
    print(f"\n✅ Ingestion complete: {len(data):,} rows")
    print(f"Tickers: {sorted(data['ticker'].unique())}")
    print(f"Date range: {data['date'].min()} to {data['date'].max()}")
