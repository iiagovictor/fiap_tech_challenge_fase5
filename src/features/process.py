"""
Stage 2 — Process
Valida o schema dos dados brutos com Pandera, limpa e enriquece
o dataset, valida o schema processado e persiste como Parquet.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd
import pandera as pa
import yaml

# Adiciona o diretório atual ao path para permitir imports diretos
sys.path.insert(0, str(Path(__file__).parent))

from schema import validate_raw, validate_processed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("process")

PARAMS_PATH = Path(__file__).parent.parent.parent / "configs" / "model_config.yaml"
RAW_INPUT = Path(__file__).parent.parent.parent / "data" / "raw" / "ohlcv_raw.csv"
PROCESSED_OUTPUT = Path(__file__).parent.parent.parent / "data" / "processed" / "ohlcv_processed.parquet"


def load_params() -> dict:
    with open(PARAMS_PATH) as f:
        return yaml.safe_load(f)["process"]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicatas, garante tipos e ordena por Date e Ticker."""
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.drop_duplicates(subset=["Date", "Ticker"])
    df = df.sort_values(["Ticker", "Date"]).reset_index(drop=True)

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    n_null = df[["Open", "High", "Low", "Close", "Volume"]].isnull().sum().sum()
    if n_null > 0:
        log.warning("Dropping %d rows with null price/volume after coercion", n_null)
        df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"])

    return df


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona colunas derivadas: retorno diário e range intraday."""
    df = df.copy()
    df["Daily_Return"] = df.groupby("Ticker")["Close"].pct_change()
    df["Price_Range"] = df["High"] - df["Low"]
    return df


def main() -> None:
    params = load_params()

    log.info("Reading raw data from %s", RAW_INPUT)
    df = pd.read_csv(RAW_INPUT)
    log.info("Rows loaded: %d", len(df))

    # ── Validação 1: schema dos dados brutos ───────────────────────────────
    log.info("Validating raw schema with Pandera...")
    try:
        df = validate_raw(df)
        log.info("Raw schema OK")
    except pa.errors.SchemaErrors as exc:
        log.error("Raw schema validation FAILED:\n%s", exc.failure_cases)
        sys.exit(1)

    # ── Limpeza ────────────────────────────────────────────────────────────
    df = clean(df)
    log.info("After cleaning: %d rows", len(df))

    # ── Enriquecimento ─────────────────────────────────────────────────────
    df = enrich(df)

    # ── Validação 2: schema dos dados processados ──────────────────────────
    log.info("Validating processed schema with Pandera...")
    try:
        df = validate_processed(df)
        log.info("Processed schema OK")
    except pa.errors.SchemaErrors as exc:
        log.error("Processed schema validation FAILED:\n%s", exc.failure_cases)
        sys.exit(1)

    # ── Persistência ───────────────────────────────────────────────────────
    PROCESSED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED_OUTPUT, index=False)
    log.info("Processed data saved → %s (%d rows)", PROCESSED_OUTPUT, len(df))


if __name__ == "__main__":
    main()