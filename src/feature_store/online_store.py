import pandas as pd
from src.feature_store.offline_store import buscar_janela_modelo


def buscar_features_para_predicao(
    ticker: str,
    tamanho_janela: int = 60,
    coluna_alvo: str = "close",
) -> list[float]:
    df_janela = buscar_janela_modelo(
        ticker=ticker,
        tamanho_janela=tamanho_janela,
    )

    if coluna_alvo not in df_janela.columns:
        raise ValueError(f"Coluna {coluna_alvo} não encontrada no feature store.")

    valores = df_janela[coluna_alvo].astype(float).tolist()

    return valores


def buscar_features_multivariadas(
    ticker: str,
    tamanho_janela: int = 60,
) -> pd.DataFrame:
    colunas_modelo = [
        "close",
        "return_1d",
        "return_7d",
        "ma_7",
        "ma_21",
        "volatility_7",
    ]

    df_janela = buscar_janela_modelo(
        ticker=ticker,
        tamanho_janela=tamanho_janela,
    )

    return df_janela[colunas_modelo].astype(float)