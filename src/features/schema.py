"""
Pandera schema definitions for yfinance OHLCV data.
Garante integridade dos dados antes de qualquer processamento downstream.
"""
from __future__ import annotations

import pandera as pa
from pandera import DataFrameModel, Field
from pandera.typing import Series
import pandas as pd
import yaml
from pathlib import Path

_params_path = Path(__file__).parent.parent.parent / "configs" / "model_config.yaml"


def _load_process_params() -> dict:
    with open(_params_path) as f:
        return yaml.safe_load(f)["process"]


class RawOHLCVSchema(DataFrameModel):
    """
    Schema para os dados brutos vindos do yfinance.
    Valida tipos, ausência de nulos e ranges esperados de mercado.
    """

    Open: Series[float] = Field(
        nullable=False,
        ge=0.01,
        description="Preço de abertura — deve ser positivo",
    )
    High: Series[float] = Field(
        nullable=False,
        ge=0.01,
        description="Máxima do dia — deve ser >= Open",
    )
    Low: Series[float] = Field(
        nullable=False,
        ge=0.01,
        description="Mínima do dia — deve ser > 0",
    )
    Close: Series[float] = Field(
        nullable=False,
        ge=0.01,
        description="Preço de fechamento — deve ser positivo",
    )
    Volume: Series[float] = Field(
        nullable=False,
        ge=0,
        description="Volume negociado — não pode ser negativo",
    )
    Ticker: Series[str] = Field(
        nullable=False,
        description="Símbolo do ativo",
    )

    class Config:
        name = "RawOHLCVSchema"
        strict = False  # permite colunas extras como Dividends, Stock Splits
        coerce = True

    @pa.dataframe_check(name="high_gte_low")
    def check_high_gte_low(cls, df: pd.DataFrame) -> pd.Series:
        """High deve ser sempre >= Low."""
        return df["High"] >= df["Low"]

    @pa.dataframe_check(name="high_gte_open")
    def check_high_gte_open(cls, df: pd.DataFrame) -> pd.Series:
        """High deve ser >= Open."""
        return df["High"] >= df["Open"]

    @pa.dataframe_check(name="high_gte_close")
    def check_high_gte_close(cls, df: pd.DataFrame) -> pd.Series:
        """High deve ser >= Close."""
        return df["High"] >= df["Close"]

    @pa.dataframe_check(name="low_lte_open")
    def check_low_lte_open(cls, df: pd.DataFrame) -> pd.Series:
        """Low deve ser <= Open."""
        return df["Low"] <= df["Open"]


class ProcessedOHLCVSchema(RawOHLCVSchema):
    """
    Schema para os dados processados.
    Adiciona colunas derivadas e restrições mais rígidas pós-limpeza.
    """

    Daily_Return: Series[float] = Field(
        nullable=True,  # NaN no primeiro dia de cada ticker é esperado
        description="Retorno diário percentual",
    )
    Price_Range: Series[float] = Field(
        nullable=False,
        ge=0,
        description="Amplitude intraday (High - Low)",
    )

    class Config:
        name = "ProcessedOHLCVSchema"
        strict = False
        coerce = True


def validate_raw(df: pd.DataFrame) -> pd.DataFrame:
    """Valida DataFrame bruto e retorna o mesmo se aprovado."""
    return RawOHLCVSchema.validate(df, lazy=True)


def validate_processed(df: pd.DataFrame) -> pd.DataFrame:
    """Valida DataFrame processado e retorna o mesmo se aprovado."""
    return ProcessedOHLCVSchema.validate(df, lazy=True)