from pathlib import Path
import pandas as pd


FEATURE_STORE_PATH = Path("data/feature_store/stock_features.parquet")


def carregar_feature_store() -> pd.DataFrame:
    if not FEATURE_STORE_PATH.exists():
        raise FileNotFoundError(
            f"Feature store não encontrado em: {FEATURE_STORE_PATH}. "
            "Execute primeiro o arquivo build_stock_features.py"
        )

    return pd.read_parquet(FEATURE_STORE_PATH)


def buscar_features_ticker(ticker: str) -> pd.DataFrame:
    df = carregar_feature_store()

    df_ticker = df[df["ticker"] == ticker].copy()

    if df_ticker.empty:
        raise ValueError(f"Nenhuma feature encontrada para o ticker: {ticker}")

    df_ticker = df_ticker.sort_values("date")

    return df_ticker


def buscar_janela_modelo(ticker: str, tamanho_janela: int = 60) -> pd.DataFrame:
    df_ticker = buscar_features_ticker(ticker)

    if len(df_ticker) < tamanho_janela:
        raise ValueError(
            f"O ticker {ticker} possui apenas {len(df_ticker)} registros. "
            f"O modelo precisa de pelo menos {tamanho_janela}."
        )

    return df_ticker.tail(tamanho_janela)