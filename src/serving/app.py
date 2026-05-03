"""
FastAPI application for serving LSTM predictions and LLM agent.

Provides endpoints for:
- /health: Health check
- /features: List available features (model + dataset)
- /predict: LSTM stock price direction prediction
- /agent: LLM agent with financial tools and RAG
- /metrics: Prometheus metrics
- /drift: Drift detection report
"""

import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime

import mlflow
import mlflow.keras
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.config.settings import get_settings
from src.config.storage import get_storage
from src.features.feature_store_client import get_feast_client

logger = logging.getLogger(__name__)
settings = get_settings()
storage = get_storage()

# ============================================================
# Prometheus Metrics
# ============================================================
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)
PREDICTION_COUNT = Counter(
    "api_predictions_total",
    "Total model predictions via API",
    ["model_type"],
)
DRIFT_SCORE = Gauge(
    "feature_drift_score",
    "Feature drift score",
)

# ============================================================
# Rate Limiter (slowapi)
# ============================================================
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# ============================================================
# Global state
# ============================================================
model = None
scaler = None
feature_names = None


def _run_drift_monitoring_pipeline() -> dict:
    """Load and execute drift monitoring pipeline lazily to avoid import-time dependency issues."""
    try:
        from src.monitoring.drift import drift_monitoring_pipeline
    except ModuleNotFoundError as e:
        logger.error("Drift monitoring dependency missing: %s", e)
        raise HTTPException(
            status_code=500,
            detail=(
                "Drift monitoring dependencies are not installed. "
                "Install the optional dependency 'monitoring' or configure Evidently."
            ),
        ) from e

    return drift_monitoring_pipeline()


def load_model_from_mlflow() -> None:
    """
    Load model from MLflow Model Registry with fallback strategy:
    1. Try Production stage
    2. Try Staging stage
    3. Try latest version (any stage)
    4. Fallback to local storage (for dev without MLflow)
    """
    global model, scaler, feature_names

    logger.info("🔍 Loading model from MLflow Model Registry...")
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)

    model_name = "stock_lstm_predictor"
    stages_to_try = ["Production", "Staging", "None"]

    for stage in stages_to_try:
        try:
            if stage == "None":
                # Try to load latest version regardless of stage
                logger.info("Attempting to load latest version (any stage)...")
                from mlflow.tracking import MlflowClient

                client = MlflowClient()

                # Get latest version
                versions = client.search_model_versions(f"name='{model_name}'")
                if not versions:
                    raise Exception(f"No versions found for model '{model_name}'")

                # Sort by version number descending
                latest_version = sorted(versions, key=lambda x: int(x.version), reverse=True)[0]
                model_uri = f"models:/{model_name}/{latest_version.version}"
                logger.info(
                    f"Loading latest version {latest_version.version}"
                    f" (stage: {latest_version.current_stage})"
                )
            else:
                model_uri = f"models:/{model_name}/{stage}"
                logger.info(f"Attempting to load model from stage: {stage}")

            # Load model
            model = mlflow.keras.load_model(model_uri)

            # Try to load scaler and feature_names from MLflow artifacts
            try:
                from mlflow.tracking import MlflowClient

                client = MlflowClient()

                if stage == "None":
                    run_id = latest_version.run_id
                else:
                    # Get run_id from the model version
                    version_info = client.get_latest_versions(model_name, stages=[stage])[0]
                    run_id = version_info.run_id

                # Try to download scaler from artifacts
                try:
                    local_scaler_path = client.download_artifacts(run_id, "scaler.pkl")
                    import joblib

                    scaler = joblib.load(local_scaler_path)
                    logger.info("✅ Loaded scaler from MLflow artifacts")
                except Exception:
                    logger.warning(
                        "⚠️  Scaler not found in MLflow artifacts, loading from storage..."
                    )
                    scaler = storage.read_joblib(f"models/scaler_{run_id}.pkl")

                # Try to load feature_names
                try:
                    import json

                    local_features_path = client.download_artifacts(run_id, "feature_names.json")
                    with open(local_features_path) as f:
                        feature_data = json.load(f)
                        feature_names = feature_data.get("feature_names", [])
                    logger.info(f"✅ Loaded {len(feature_names)} feature names")
                except Exception:
                    logger.warning("⚠️  Feature names not found in MLflow artifacts")
                    feature_names = []

            except Exception as e:
                logger.warning(f"Failed to load artifacts from MLflow: {e}")
                logger.info("Using model without scaler/feature_names")

            logger.info(f"✅ Model loaded successfully from MLflow (stage: {stage})")
            return

        except Exception as e:
            logger.debug(f"Failed to load from stage '{stage}': {e}")
            continue

    # All MLflow attempts failed, try local storage fallback
    logger.warning("❌ Failed to load from MLflow, trying local storage fallback...")
    try:
        # Try to find most recent model file by timestamp
        import glob
        import os

        # Get full path for glob pattern
        models_pattern = str(storage._full_path("models/lstm_model_*.keras"))
        logger.info(f"Searching for models with pattern: {models_pattern}")
        model_files = glob.glob(models_pattern)
        logger.info(f"Found {len(model_files)} model files: {model_files}")

        if model_files:
            # Get most recent file
            latest_model_file = max(model_files, key=lambda x: os.path.getctime(x))
            logger.info(f"Loading most recent model: {latest_model_file}")

            # Extract run_id from filename
            run_id = (
                os.path.basename(latest_model_file).replace("lstm_model_", "").replace(".keras", "")
            )
            logger.info(f"Extracted run_id: {run_id}")

            # Load model using storage client
            logger.info("Loading model via storage client...")
            model = storage.read_keras_model(f"models/lstm_model_{run_id}.keras")
            logger.info("✅ Model loaded successfully")

            # Try to find matching scaler
            try:
                logger.info(f"Loading scaler: models/scaler_{run_id}.pkl")
                scaler = storage.read_joblib(f"models/scaler_{run_id}.pkl")
                logger.info("✅ Loaded model and scaler from local storage")
            except Exception as scaler_err:
                logger.warning(f"⚠️  Scaler not found for this model: {scaler_err}")
        else:
            raise FileNotFoundError("No model files found in local storage")

    except Exception as e:
        logger.error(f"❌ Failed to load model from storage: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception details: {str(e)}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        logger.error("⚠️  No model loaded - /predict endpoint will fail")
        model = None
        scaler = None
        feature_names = []


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown."""
    # Startup
    logger.info("Starting FastAPI application...")
    load_model_from_mlflow()
    yield
    # Shutdown
    logger.info("Shutting down FastAPI application...")


# ============================================================
# FastAPI Application
# ============================================================
_DESCRIPTION = """
## Plataforma MLOps/LLMOps — FIAP Tech Challenge Fase 5

API REST para predição de direção de preço de ações da B3 com agente LLM.

### Funcionalidades

| Endpoint | Método | Descrição |
|---|---|---|
| `/health` | GET | Status da API e do modelo |
| `/features` | GET | Features usadas pelo modelo carregado |
| `/predict` | POST | Predição LSTM de alta/baixa (próximos 5 dias) |
| `/agent` | POST | Agente LLM ReAct com RAG financeiro |
| `/drift` | GET | Relatório de data drift (Evidently) |
| `/metrics` | GET | Métricas Prometheus |

### Modelo LSTM

O modelo é uma rede LSTM treinada com **24 indicadores técnicos** calculados a partir de
dados OHLCV do Yahoo Finance (yfinance):

- **Tendência**: SMA 5/10/20/50, EMA 12/26
- **Momentum**: RSI(14), MACD, MACD Signal, MACD Histogram
- **Volatilidade**: Bollinger Bands (superior/média/inferior/largura), ATR(14)
- **Volume**: OBV, Volume SMA(20)
- **Retorno**: `price_change` (1d), `price_change_5d` (5d)

**Target**: `1` se o preço de fechamento sobe em 5 dias úteis, `0` se cai.

### Agente LLM

O agente segue o padrão **ReAct** (Reasoning + Acting). A cada passo decide qual ferramenta
chamar, observa o resultado e repete até formular uma resposta.

Ferramentas disponíveis:
- `get_stock_price_history` — histórico de preços e variação percentual
- `calculate_technical_indicators` — RSI, MACD, médias móveis com interpretação
- `predict_stock_direction` — predição LSTM com recomendação
- `compare_stocks` — tabela comparativa de performance entre ativos

### Segurança

Todas as queries ao agente passam por guardrails que detectam prompt injection e PII.

### Ativos suportados por padrão

`ITUB4.SA` · `PETR4.SA` · `VALE3.SA` · `BBDC4.SA` · `BBAS3.SA` · `^BVSP`
"""

_TAGS_METADATA = [
    {
        "name": "Observability",
        "description": "Health check, métricas Prometheus e status do modelo.",
    },
    {
        "name": "Prediction",
        "description": (
            "Predição de direção de preço com modelo LSTM. "
            "Usa Feast Online Store (Redis) com fallback automático para features locais."
        ),
    },
    {
        "name": "Agent",
        "description": (
            "Agente LLM ReAct com RAG. Responde perguntas em linguagem natural "
            "sobre ações da B3 usando ferramentas de análise técnica."
        ),
    },
    {
        "name": "Features",
        "description": "Informações sobre features disponíveis no modelo e no dataset.",
    },
    {
        "name": "Monitoring",
        "description": "Data drift detection com Evidently e métricas de monitoramento.",
    },
]

app = FastAPI(
    title="Stock LSTM Prediction API",
    description=_DESCRIPTION,
    version="1.0.0",
    openapi_tags=_TAGS_METADATA,
    contact={
        "name": "FIAP Tech Challenge Fase 5",
        "url": "https://github.com/iiagovictor/fiap_tech_challenge_fase5",
    },
    license_info={"name": "MIT", "identifier": "MIT"},
    lifespan=lifespan,
)

# Rate-limiter wiring
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware for request tracking
@app.middleware("http")
async def track_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Track request metrics."""
    start_time = time.perf_counter()

    response = await call_next(request)

    duration = time.perf_counter() - start_time
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).inc()
    REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(duration)

    return response


# ============================================================
# Pydantic Models
# ============================================================
class HealthResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    status: str = Field(
        ...,
        description="`healthy` se o modelo está carregado, `degraded` caso contrário.",
        examples=["healthy"],
    )
    timestamp: str = Field(
        ...,
        description="Horário da resposta em ISO 8601.",
        examples=["2026-05-03T10:00:00"],
    )
    model_loaded: bool = Field(
        ...,
        description="`true` se o modelo LSTM está em memória e pronto para predizer.",
        examples=[True],
    )


class PredictionRequest(BaseModel):
    ticker: str = Field(
        ...,
        description=(
            "Ticker do ativo no formato Yahoo Finance. "
            "Exemplos: `ITUB4.SA`, `PETR4.SA`, `VALE3.SA`, `^BVSP`."
        ),
        examples=["ITUB4.SA"],
    )
    timestamp: datetime | None = Field(
        None,
        description=(
            "Momento de referência para recuperar as features (padrão: agora). "
            "Útil para backtesting. Formato ISO 8601."
        ),
        examples=[None],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"ticker": "ITUB4.SA"},
                {"ticker": "PETR4.SA", "timestamp": "2026-04-01T09:00:00"},
            ]
        }
    }


class PredictionResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    ticker: str = Field(..., description="Ticker consultado.", examples=["ITUB4.SA"])
    prediction: int = Field(
        ...,
        description="Direção prevista: `1` = alta nos próximos 5 dias, `0` = baixa.",
        examples=[1],
    )
    probability: float = Field(
        ...,
        description=(
            "Probabilidade de alta prevista pelo modelo (0.0 a 1.0). "
            "Valores próximos a 0.5 indicam incerteza."
        ),
        examples=[0.67],
    )
    timestamp: str = Field(
        ...,
        description="Horário da predição em ISO 8601.",
        examples=["2026-05-03T10:00:00"],
    )
    model_version: str | None = Field(
        None,
        description="Versão ou stage do modelo no MLflow Registry.",
        examples=["lstm_v1"],
    )


class AgentRequest(BaseModel):
    query: str = Field(
        ...,
        description="Pergunta em linguagem natural sobre ações da B3.",
        examples=["Qual a tendência da VALE3.SA nos próximos dias?"],
    )
    ticker: str | None = Field(
        None,
        description="Ticker opcional para contextualizar a pergunta.",
        examples=["VALE3.SA"],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "Qual a tendência da VALE3.SA?", "ticker": "VALE3.SA"},
                {"query": "Compare o desempenho de ITUB4.SA e BBDC4.SA no último mês"},
                {"query": "A PETR4.SA vai valorizar nos próximos dias?", "ticker": "PETR4.SA"},
                {"query": "Calcule os indicadores técnicos da BBAS3.SA", "ticker": "BBAS3.SA"},
                {"query": "Quais tickers estão disponíveis?"},
            ]
        }
    }


class AgentResponse(BaseModel):
    query: str = Field(..., description="Pergunta original recebida.")
    response: str = Field(..., description="Resposta gerada pelo agente LLM.")
    sources: list[str] = Field(
        default_factory=list,
        description="Ferramentas e fontes usadas pelo agente para formular a resposta.",
        examples=[
            [
                "get_stock_price_history(ticker=VALE3.SA)",
                "calculate_technical_indicators(ticker=VALE3.SA)",
            ]
        ],
    )
    timestamp: str = Field(
        ...,
        description="Horário da resposta em ISO 8601.",
        examples=["2026-05-03T10:00:00"],
    )


class FeaturesResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_features: list[str] = Field(
        ...,
        description="Lista de features usadas pelo modelo LSTM carregado.",
        examples=[["rsi_14", "macd", "macd_signal", "sma_20", "ema_12"]],
    )
    dataset_features: list[str] | None = Field(
        None,
        description=(
            "Features disponíveis no dataset (Parquet). "
            "`null` se o arquivo não estiver acessível."
        ),
    )
    total_model_features: int = Field(
        ...,
        description="Total de features do modelo.",
        examples=[24],
    )
    total_dataset_features: int | None = Field(
        None,
        description="Total de features no dataset. `null` se não acessível.",
        examples=[24],
    )
    timestamp: str = Field(
        ...,
        description="Horário da resposta em ISO 8601.",
        examples=["2026-05-03T10:00:00"],
    )


# ============================================================
# Endpoints
# ============================================================
@app.get("/", response_model=dict, include_in_schema=False)
async def root() -> dict:
    """Root endpoint."""
    return {
        "message": "Stock LSTM Prediction API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "features": "/features",
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Observability"],
    summary="Health check da API",
    responses={
        200: {
            "description": "API operacional (modelo pode estar ou não carregado).",
            "content": {
                "application/json": {
                    "examples": {
                        "healthy": {
                            "summary": "Modelo carregado",
                            "value": {
                                "status": "healthy",
                                "timestamp": "2026-05-03T10:00:00",
                                "model_loaded": True,
                            },
                        },
                        "degraded": {
                            "summary": "Sem modelo carregado",
                            "value": {
                                "status": "degraded",
                                "timestamp": "2026-05-03T10:00:00",
                                "model_loaded": False,
                            },
                        },
                    }
                }
            },
        }
    },
)
async def health_check() -> HealthResponse:
    """
    Verifica o status da API e se o modelo LSTM está carregado em memória.

    - **`healthy`**: modelo carregado e pronto para predições.
    - **`degraded`**: API no ar mas modelo não carregado — `/predict` retornará `503`.

    Se o estado for `degraded`, execute `make train` e reinicie a API.
    """
    return HealthResponse(
        status="healthy" if model is not None else "degraded",
        timestamp=datetime.now().isoformat(),
        model_loaded=model is not None,
    )


@app.get(
    "/metrics",
    response_class=PlainTextResponse,
    tags=["Observability"],
    summary="Métricas Prometheus",
    responses={
        200: {
            "description": "Métricas no formato Prometheus text exposition.",
            "content": {"text/plain": {}},
        }
    },
)
async def metrics() -> bytes:
    """
    Retorna métricas da API no formato Prometheus text exposition.

    **Métricas disponíveis:**

    | Métrica | Tipo | Labels | Descrição |
    |---|---|---|---|
    | `http_requests_total` | Counter | `method`, `endpoint`, `status` | Total de requisições HTTP |
    | `http_request_duration_seconds` | Histogram | `method`, `endpoint` | Latência por endpoint |
    | `api_predictions_total` | Counter | `model_type` | Total de predições via `/predict` |
    | `feature_drift_score` | Gauge | — | Último score de drift (PSI) do `/drift` |

    Configure o Prometheus para fazer scrape adicionando ao `prometheus.yml`:
    ```yaml
    scrape_configs:
      - job_name: 'stock-api'
        static_configs:
          - targets: ['api:8000']
    ```
    """
    return generate_latest()


@app.get(
    "/features",
    response_model=FeaturesResponse,
    tags=["Features"],
    summary="Features do modelo e do dataset",
)
async def get_features() -> FeaturesResponse:
    """
    Retorna informações sobre as features disponíveis no modelo carregado e no dataset.

    - **`model_features`**: colunas exatas usadas pelo modelo LSTM registrado no MLflow.
      São as features que devem estar presentes nos dados de entrada do `/predict`.
    - **`dataset_features`**: colunas disponíveis em `data/features/stock_features.parquet`.
      Inclui colunas de metadados (`ticker`, `Date`) que são excluídas antes da predição.

    Se `model_features` estiver vazio, o modelo foi salvo sem metadados.
    Execute `make train` para regenerar com os metadados corretos.
    """
    # Get model features
    model_features_list = feature_names if feature_names else []

    # Try to read dataset features from stored parquet file
    dataset_features_list = None
    try:
        if storage.exists("features/stock_features.parquet"):
            df = storage.read_parquet("features/stock_features.parquet")
            # Exclude non-feature columns like ticker, timestamp, target
            exclude_cols = ["ticker", "timestamp", "Date", "target", "target_next_day"]
            dataset_features_list = [col for col in df.columns if col not in exclude_cols]
            logger.info(f"Read {len(dataset_features_list)} features from dataset")
    except Exception as e:
        logger.warning(f"Could not read dataset features: {e}")

    return FeaturesResponse(
        model_features=model_features_list,
        dataset_features=dataset_features_list,
        total_model_features=len(model_features_list),
        total_dataset_features=len(dataset_features_list) if dataset_features_list else None,
        timestamp=datetime.now().isoformat(),
    )


@app.post(
    "/predict",
    response_model=PredictionResponse,
    tags=["Prediction"],
    summary="Predição de direção de preço (LSTM)",
    responses={
        200: {
            "description": "Predição gerada com sucesso.",
            "content": {
                "application/json": {
                    "example": {
                        "ticker": "ITUB4.SA",
                        "prediction": 1,
                        "probability": 0.67,
                        "timestamp": "2026-05-03T10:00:00",
                        "model_version": "lstm_v1",
                    }
                }
            },
        },
        404: {"description": "Ticker não encontrado no dataset de features."},
        503: {"description": "Modelo não carregado ou features indisponíveis."},
        500: {"description": "Erro interno durante a predição."},
    },
)
@limiter.limit("30/minute")
async def predict(http_request: Request, request: PredictionRequest) -> PredictionResponse:
    """
    Realiza predição de direção de preço para os próximos 5 dias úteis usando o modelo LSTM.

    **Fluxo de features (em ordem de prioridade):**
    1. **Feast Online Store (Redis)** — baixa latência, requer `make feast-materialize`.
    2. **Parquet local** (`data/features/stock_features.parquet`) — fallback automático.
    3. Se nenhuma fonte estiver disponível, retorna `503`.

    **Interpretação do resultado:**

    | `prediction` | `probability` | Sinal |
    |---|---|---|
    | `1` | `> 0.6` | Alta esperada — sinal de **compra** |
    | `0` | `< 0.4` | Queda esperada — sinal de **venda** |
    | `1` ou `0` | `0.4 – 0.6` | Incerteza alta — sinal **neutro** |

    > **Disclaimer:** As predições não constituem recomendação de investimento.
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        timestamp = request.timestamp or datetime.now()
        logger.info(f"Prediction request for {request.ticker} at {timestamp}")

        # Try Feast first, fallback to local features
        features_df = None

        try:
            feast_client = get_feast_client()
            features_df = feast_client.get_online_features(
                ticker=request.ticker, timestamp=timestamp
            )
            logger.info("✅ Retrieved features from Feast")
        except Exception as feast_error:
            logger.warning(f"Feast unavailable: {feast_error}. Using local features...")

            # Fallback: Load features from local parquet file
            try:
                if storage.exists("features/stock_features.parquet"):
                    df = storage.read_parquet("features/stock_features.parquet")

                    # Filter by ticker and get most recent data
                    ticker_df = df[df["ticker"] == request.ticker].copy()
                    if len(ticker_df) == 0:
                        detail = f"No features found for ticker {request.ticker}"
                        raise HTTPException(status_code=404, detail=detail)

                    # Sort by date and get last row
                    if "Date" in ticker_df.columns:
                        ticker_df = ticker_df.sort_values("Date")
                    features_df = ticker_df.tail(1)
                    logger.info(f"✅ Loaded features from local storage for {request.ticker}")
                else:
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "No features available (Feast not configured"
                            " and local features not found)"
                        ),
                    )
            except HTTPException:
                raise
            except Exception as local_error:
                logger.error(f"Failed to load local features: {local_error}")
                raise HTTPException(
                    status_code=500, detail=f"Could not retrieve features: {str(local_error)}"
                ) from local_error

        # Prepare features for model
        # Select only numeric columns and exclude target/metadata columns
        exclude_cols = ["ticker", "timestamp", "Date", "target", "target_next_day"]

        # Get numeric columns only
        numeric_df = features_df.select_dtypes(include=[np.number])

        # Further exclude any remaining non-feature columns
        feature_cols = [col for col in numeric_df.columns if col not in exclude_cols]

        if len(feature_cols) == 0:
            raise HTTPException(status_code=500, detail="No numeric features found in dataset")

        features_arr = numeric_df[feature_cols].values
        logger.info(f"Using {len(feature_cols)} features for prediction")

        # Scale features if scaler is available
        if scaler is not None:
            try:
                features_arr = scaler.transform(features_arr)
            except Exception as scale_error:
                logger.warning(f"Scaler transform failed: {scale_error}. Using unscaled features.")

        # Reshape for LSTM (samples, timesteps, features)
        # For single prediction, timesteps=1
        features_arr = features_arr.reshape(1, 1, features_arr.shape[1])

        # Make prediction
        prediction_proba = model.predict(features_arr, verbose=0)[0][0]
        prediction_class = int(prediction_proba > 0.5)

        logger.info(
            f"Prediction for {request.ticker}: {prediction_class} (prob={prediction_proba:.4f})"
        )

        PREDICTION_COUNT.labels(model_type="lstm").inc()

        return PredictionResponse(
            ticker=request.ticker,
            prediction=prediction_class,
            probability=float(prediction_proba),
            timestamp=datetime.now().isoformat(),
            model_version="lstm_v1",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prediction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}") from e


@app.post(
    "/agent",
    response_model=AgentResponse,
    tags=["Agent"],
    summary="Consulta ao agente LLM financeiro (ReAct + RAG)",
    responses={
        200: {
            "description": "Resposta gerada pelo agente.",
            "content": {
                "application/json": {
                    "examples": {
                        "com_ferramentas": {
                            "summary": "Agente usou ferramentas",
                            "value": {
                                "query": "Qual a tendência da VALE3.SA?",
                                "response": (
                                    "A VALE3.SA apresenta RSI de 58 (neutro-positivo) e MACD "
                                    "acima da linha de sinal, sugerindo tendência de alta moderada."
                                ),
                                "sources": [
                                    "get_stock_price_history(ticker=VALE3.SA)",
                                    "calculate_technical_indicators(ticker=VALE3.SA)",
                                ],
                                "timestamp": "2026-05-03T10:00:00",
                            },
                        },
                        "fallback": {
                            "summary": "Fallback direto (LLM indisponível)",
                            "value": {
                                "query": "Compare ITUB4 e BBDC4",
                                "response": "Comparação: ITUB4.SA +2.3%, BBDC4.SA +1.1%",
                                "sources": ["Yahoo Finance", "Comparative Analysis"],
                                "timestamp": "2026-05-03T10:00:00",
                            },
                        },
                    }
                }
            },
        },
        500: {"description": "Erro interno no agente."},
    },
)
@limiter.limit("10/minute")
async def agent_query(http_request: Request, request: AgentRequest) -> AgentResponse:
    """
    Consulta o agente LLM com ferramentas de análise financeira e RAG (ChromaDB).

    O agente segue o padrão **ReAct** (Reasoning + Acting): a cada passo decide qual
    ferramenta chamar, observa o resultado e itera até formular uma resposta fundamentada.

    **Ferramentas disponíveis:**

    | Ferramenta | Parâmetros | Retorna |
    |---|---|---|
    | `get_stock_price_history` | `ticker`, `period` | Preço atual, máx/mín, variação %, volume |
    | `calculate_technical_indicators` | `ticker`, `period` | RSI, MACD, SMAs, EMAs, Bollinger |
    | `predict_stock_direction` | `ticker` | Predição LSTM + recomendação |
    | `compare_stocks` | `tickers` (lista), `period` | Tabela comparativa de performance |

    **Lógica de fallback (em ordem):**
    ```
    1. Agente ReAct com LLM configurado (.env)
          ↓ (LLM indisponível ou timeout)
    2. Execução direta das ferramentas por keyword matching
          ↓
    3. Dados brutos do yfinance + aviso de baixa confiênça
    ```

    **Guardrails:** toda query é validada contra padrões de prompt injection antes
    de chegar ao LLM (`src/security/guardrails.py`).

    **Exemplos de perguntas suportadas:**
    - `"Qual a cotação atual da PETR4.SA?"`
    - `"Calcule os indicadores técnicos da VALE3.SA"`
    - `"Compare ITUB4.SA e BBDC4.SA no último mês"`
    - `"A BBAS3.SA vai valorizar nos próximos dias?"`
    - `"Quais tickers estão disponíveis?"`
    """
    try:
        logger.info(f"Agent query: {request.query}")

        # Try to use real agent, fallback to simple tool execution if LLM not available
        try:
            from src.agent.react_agent import get_agent

            agent = get_agent()
            result = agent.query(request.query)

            # Check if agent failed (max iterations or error)
            if result.get("error") or "wasn't able to complete" in result.get("answer", ""):
                logger.warning("LLM agent failed, falling back to direct tools...")
                raise ValueError("LLM agent incomplete")

            # Extract sources from tool calls
            sources = []
            if result.get("tool_calls") and len(result["tool_calls"]) > 0:
                # Agent used tools - list which ones
                tool_names = [
                    f"{call['tool']}(ticker={call['params'].get('ticker', 'N/A')})"
                    for call in result["tool_calls"]
                ]
                sources = tool_names
                tool_display = ", ".join(t.split("(")[0] for t in tool_names)
                logger.info(f"✅ Agent used {len(tool_names)} tool(s): {tool_display}")
            else:
                # Agent didn't use tools - just LLM
                sources = ["LLM Agent (no tools used)"]
                logger.warning("⚠️ Agent provided answer without using tools - may be hallucinated!")

            return AgentResponse(
                query=request.query,
                response=result["answer"],
                sources=sources,
                timestamp=datetime.now().isoformat(),
            )

        except (ImportError, ValueError, Exception) as ie:
            logger.warning(f"LLM agent unavailable or failed: {ie}")
            logger.info("Falling back to direct tool execution...")

            # Fallback: Try to use tools directly based on query type
            from src.agent.tools import (
                calculate_technical_indicators,
                compare_stocks,
                get_stock_price_history,
            )

            query_lower = request.query.lower()

            # Check query type
            if any(
                word in query_lower for word in ["disponível", "tickers", "lista", "quais ações"]
            ):
                # Question about available tickers
                response_text = f"""📋 Tickers disponíveis para consulta:

{settings.data_tickers}

Você pode consultar qualquer um desses ativos usando o endpoint /agent com o parâmetro "ticker".

Exemplo: "Qual a cotação da PETR4.SA?" ou "Análise técnica da VALE3.SA"
"""
                return AgentResponse(
                    query=request.query,
                    response=response_text.strip(),
                    sources=["Configuration", "System"],
                    timestamp=datetime.now().isoformat(),
                )

            elif any(word in query_lower for word in ["comparar", "melhor", "pior desempenho"]):
                # Question about comparison
                tickers = settings.data_tickers.split(",")[:5]  # Limit to 5 for performance
                comparison = compare_stocks(tickers, period="1mo")

                if "error" in comparison:
                    response_text = f"Erro ao comparar ações: {comparison['error']}"
                else:
                    response_text = f"""📊 Comparação de Ações (último mês):

🏆 Melhor Desempenho: {comparison['best_performer']}
📉 Pior Desempenho: {comparison['worst_performer']}

Detalhes:
"""
                    for stock in comparison["results"][:3]:
                        pct = stock["price_change_pct"]
                        price = stock["current_price"]
                        response_text += f"\n• {stock['ticker']}: {pct:+.2f}% (R$ {price})"

                return AgentResponse(
                    query=request.query,
                    response=response_text.strip(),
                    sources=["Yahoo Finance", "Comparative Analysis"],
                    timestamp=datetime.now().isoformat(),
                )

            else:
                # Default: Stock analysis for specific ticker
                ticker = request.ticker or "ITUB4.SA"

                # Extract ticker from query if present
                import re

                ticker_pattern = r"([A-Z]{4}\d{1,2}\.SA|\^BVSP)"
                matches = re.findall(ticker_pattern, request.query.upper())
                if matches:
                    ticker = matches[0]

                # Get price and technical data
                price_data = get_stock_price_history(ticker, period="1mo")
                tech_data = calculate_technical_indicators(ticker, period="3mo")

                if "error" in price_data:
                    raise HTTPException(status_code=404, detail=price_data["error"]) from None

                # Format response
                response_text = f"""Análise de {ticker}:

📊 Cotação Atual: R$ {price_data['current_price']}
📈 Variação (1 mês): {price_data['price_change_pct']:+.2f}%
💰 Preço: R$ {price_data['low_price']} - R$ {price_data['high_price']}

Indicadores Técnicos:
• RSI (14): {tech_data.get('rsi_14', 'N/A')} - {tech_data.get('signal', 'N/A')}
• MACD: {tech_data.get('macd', 'N/A')}
• SMA20: R$ {tech_data.get('sma_20', 'N/A')}
• SMA50: R$ {tech_data.get('sma_50', 'N/A')}
"""

                return AgentResponse(
                    query=request.query,
                    response=response_text.strip(),
                    sources=["Yahoo Finance", "Technical Analysis"],
                    timestamp=datetime.now().isoformat(),
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent query failed: {str(e)}") from e


@app.get(
    "/drift",
    tags=["Monitoring"],
    summary="Relatório de drift de features (Evidently PSI)",
    responses={
        200: {
            "description": "Relatório de drift gerado com sucesso.",
            "content": {
                "application/json": {
                    "examples": {
                        "sem_drift": {
                            "summary": "Sem drift detectado",
                            "value": {
                                "drift_detected": False,
                                "drift_score": 0.05,
                                "overall_drift_score": 0.05,
                                "features_drifted": [],
                                "alert_level": "green",
                                "report_path": "data/drift_report.html",
                            },
                        },
                        "com_drift": {
                            "summary": "Drift detectado em features",
                            "value": {
                                "drift_detected": True,
                                "drift_score": 0.28,
                                "overall_drift_score": 0.28,
                                "features_drifted": ["rsi", "macd_signal"],
                                "alert_level": "red",
                                "report_path": "data/drift_report.html",
                            },
                        },
                    }
                }
            },
        },
        500: {"description": "Erro ao executar pipeline de drift."},
    },
)
async def drift_report() -> dict:
    """
    Executa o pipeline de detecção de drift e retorna o relatório mais recente.

    Utiliza o **Evidently AI** com a métrica **PSI (Population Stability Index)**
    para comparar a distribuição atual das features com a baseline de treino.

    **Níveis de alerta:**

    | `alert_level` | `drift_score` | Significado |
    |---|---|---|
    | `green` | `< 0.1` | Distribuição estável |
    | `yellow` | `0.1 – 0.2` | Drift moderado — monitorar |
    | `red` | `> 0.2` | Drift significativo — retraining recomendado |

    **Features monitoradas:** `close`, `rsi`, `macd`, `macd_signal`, `bollinger_upper`,
    `bollinger_lower`, `sma_20`, `sma_50`.

    O relatório HTML completo é salvo em `report_path` dentro do container.
    """
    try:
        result = _run_drift_monitoring_pipeline()
        return {
            "timestamp": result.get("timestamp", datetime.now().isoformat()),
            "drift_detected": result.get("drift_detected", False),
            "drift_score": result.get("overall_drift_score", 0.0),
            "overall_drift_score": result.get("overall_drift_score", 0.0),
            "features_drifted": result.get("features_drifted", []),
            "alert_level": result.get("alert_level", "green"),
            "report_path": result.get("report_path"),
        }

    except Exception as e:
        logger.error(f"Drift report error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Drift report failed: {str(e)}") from e


if __name__ == "__main__":
    import uvicorn

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run server
    uvicorn.run(
        "src.serving.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.api_log_level,
    )
