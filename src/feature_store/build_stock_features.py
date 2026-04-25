from pathlib import Path
import pandas as pd
import yfinance as yf


FEATURE_STORE_PATH = Path("data/feature_store/stock_features.parquet")


def criar_features_acoes(ticker: str, period: str = "5y") -> pd.DataFrame:
    df = yf.Ticker(ticker).history(period=period).reset_index()

    if df.empty:
        raise ValueError(f"Nenhum dado encontrado para o ticker: {ticker}")

    df = df.rename(columns={
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    })

    df["ticker"] = ticker
    df["date"] = pd.to_datetime(df["date"]).dt.date

    df["return_1d"] = df["close"].pct_change(1)
    df["return_7d"] = df["close"].pct_change(7)
    df["ma_7"] = df["close"].rolling(7).mean()
    df["ma_21"] = df["close"].rolling(21).mean()
    df["volatility_7"] = df["return_1d"].rolling(7).std()

    df = df.dropna()

    return df[
        [
            "ticker",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "return_1d",
            "return_7d",
            "ma_7",
            "ma_21",
            "volatility_7",
        ]
    ]


def salvar_feature_store(tickers: list[str], period: str = "5y") -> None:
    FEATURE_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)

    dfs = []

    for ticker in tickers:
        print(f"Criando features para {ticker}...")
        df_ticker = criar_features_acoes(ticker, period)
        dfs.append(df_ticker)

    df_final = pd.concat(dfs, ignore_index=True)

    df_final.to_parquet(FEATURE_STORE_PATH, index=False)

    print(f"Feature store salvo em: {FEATURE_STORE_PATH}")
    print(f"Total de linhas: {len(df_final)}")


if __name__ == "__main__":
    salvar_feature_store(tickers=["ITUB4.SA"])