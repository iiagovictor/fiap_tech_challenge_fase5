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
# Global state
# ============================================================
model = None
scaler = None
feature_names = None


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
app = FastAPI(
    title="Stock LSTM Prediction API",
    description="MLOps platform for stock price direction prediction with LLM agent",
    version="1.0.0",
    lifespan=lifespan,
)

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

    status: str
    timestamp: str
    model_loaded: bool


class PredictionRequest(BaseModel):
    ticker: str = Field(..., description="Stock ticker (e.g., ITUB4.SA)")
    timestamp: datetime | None = Field(
        None,
        description="Timestamp for feature retrieval (default: now)",
    )


class PredictionResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    ticker: str
    prediction: int = Field(..., description="Predicted direction: 1 (up), 0 (down)")
    probability: float = Field(..., description="Probability of upward movement")
    timestamp: str
    model_version: str | None = None


class AgentRequest(BaseModel):
    query: str = Field(..., description="Natural language query about stocks")
    ticker: str | None = Field(None, description="Optional ticker for context")


class AgentResponse(BaseModel):
    query: str
    response: str
    sources: list[str] = Field(default_factory=list)
    timestamp: str


class FeaturesResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_features: list[str] = Field(..., description="Features used by the loaded model")
    dataset_features: list[str] | None = Field(
        None, description="Features available in the dataset"
    )
    total_model_features: int
    total_dataset_features: int | None = None
    timestamp: str


# ============================================================
# Endpoints
# ============================================================
@app.get("/", response_model=dict)
async def root() -> dict:
    """Root endpoint."""
    return {
        "message": "Stock LSTM Prediction API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "features": "/features",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy" if model is not None else "degraded",
        timestamp=datetime.now().isoformat(),
        model_loaded=model is not None,
    )


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> bytes:
    """Prometheus metrics endpoint."""
    return generate_latest()


@app.get("/features", response_model=FeaturesResponse)
async def get_features() -> FeaturesResponse:
    """
    Get information about available features.

    Returns:
    - Features used by the loaded model
    - Features available in the dataset (if accessible)
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


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest) -> PredictionResponse:
    """
    Predict stock price direction using LSTM model.

    Returns prediction (1 = up, 0 = down) and probability.
    Uses Feast if available, otherwise falls back to local features.
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


@app.post("/agent", response_model=AgentResponse)
async def agent_query(request: AgentRequest) -> AgentResponse:
    """
    Query the LLM agent with financial tools and RAG.

    The agent can:
    - Answer questions about stocks using RAG
    - Execute financial analysis tools
    - Provide market insights
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


@app.get("/drift")
async def drift_report() -> dict:
    """
    Get latest drift detection report.

    Returns drift metrics and alerts.
    """
    try:
        # TODO: Implement actual drift detection
        # For now, return mock response
        return {
            "timestamp": datetime.now().isoformat(),
            "drift_detected": False,
            "drift_score": 0.03,
            "features_drifted": [],
            "alert_level": "green",
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
