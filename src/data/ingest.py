"""
Stage 1 — Fetch
Baixa dados OHLCV do yfinance para os tickers definidos em params.yaml
e persiste como CSV versionado pelo DVC.

Suporta dois modos:
1. Histórico: Busca período definido em model_config.yaml (start_date, end_date)
2. Incremental: Busca apenas últimos N dias e faz merge com dados existentes
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml
import yfinance as yf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fetch")

PARAMS_PATH = Path(__file__).parent.parent.parent / "configs" / "model_config.yaml"
RAW_OUTPUT = Path(__file__).parent.parent.parent / "data" / "raw" / "ohlcv_raw.csv"

def load_params() -> dict:
    with open(PARAMS_PATH) as f:
        return yaml.safe_load(f)["fetch"]


def fetch_tickers(
    tickers: list[str],
    start_date: str,
    end_date: str,
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Baixa OHLCV para todos os tickers e empilha num único DataFrame.
    A coluna 'Ticker' identifica cada ativo.
    """
    frames: list[pd.DataFrame] = []

    for ticker in tickers:
        log.info("Downloading %s [%s → %s]", ticker, start_date, end_date)
        raw = yf.download(
            ticker,
            start=start_date,
            end=end_date,
            interval=interval,
            auto_adjust=True,
            progress=False,
        )

        if raw.empty:
            log.warning("No data returned for %s — skipping", ticker)
            continue

        # yfinance pode retornar MultiIndex de colunas em versões recentes
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)

        raw = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
        raw["Ticker"] = ticker
        raw.index.name = "Date"
        frames.append(raw)

    if not frames:
        raise RuntimeError("Nenhum dado foi baixado. Verifique os tickers e o período.")

    df = pd.concat(frames)
    df = df.reset_index()
    log.info("Total rows fetched: %d", len(df))
    return df


def fetch_daily_incremental(
    tickers: list[str],
    days_back: int = 7,
    interval: str = "1d",
) -> pd.DataFrame:
    """
    Busca dados dos últimos N dias para todos os tickers.
    Ideal para atualização diária incremental.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    log.info("Fetching daily data [%s → %s] (%d days back)", start_str, end_str, days_back)
    return fetch_tickers(tickers, start_str, end_str, interval)


def merge_with_existing(new_df: pd.DataFrame, existing_csv: Path) -> pd.DataFrame:
    """
    Faz merge dos novos dados com dados existentes, removendo duplicatas.
    Mantém os dados mais recentes em caso de conflito.
    """
    if not existing_csv.exists():
        log.info("No existing data — using only new data")
        return new_df
    
    existing_df = pd.read_csv(existing_csv)
    existing_df["Date"] = pd.to_datetime(existing_df["Date"])
    new_df["Date"] = pd.to_datetime(new_df["Date"])
    
    log.info("Existing data: %d rows | New data: %d rows", len(existing_df), len(new_df))
    
    # Concatena e remove duplicatas, mantendo os novos valores
    merged = pd.concat([existing_df, new_df], ignore_index=True)
    merged = merged.sort_values(["Ticker", "Date"], ignore_index=True)
    merged = merged.drop_duplicates(subset=["Date", "Ticker"], keep="last")
    
    log.info("After merge: %d rows", len(merged))
    return merged


def main(mode: str = "historical", days_back: int = 7) -> None:
    """
    Executa a ingestão de dados.
    
    Args:
        mode: 'historical' (padrão) ou 'incremental'
        days_back: Número de dias para buscar no modo incremental (padrão: 7)
    """
    params = load_params()
    
    if mode == "incremental":
        log.info("Running in INCREMENTAL mode (last %d days)", days_back)
        df = fetch_daily_incremental(
            tickers=params["tickers"],
            days_back=days_back,
            interval=params["interval"],
        )
        df = merge_with_existing(df, RAW_OUTPUT)
    else:
        log.info("Running in HISTORICAL mode")
        df = fetch_tickers(
            tickers=params["tickers"],
            start_date=params["start_date"],
            end_date=params["end_date"],
            interval=params["interval"],
        )
    
    RAW_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW_OUTPUT, index=False)
    log.info("Raw data saved → %s (%d rows)", RAW_OUTPUT, len(df))


if __name__ == "__main__":
    # Detecta argumento de modo
    mode = sys.argv[1] if len(sys.argv) > 1 else "historical"
    days_back = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    main(mode=mode, days_back=days_back)