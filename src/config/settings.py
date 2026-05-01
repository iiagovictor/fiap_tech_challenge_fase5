"""
Application settings using Pydantic for cloud-agnostic configuration.
Loads from environment variables with validation and sensible defaults.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Main application settings.
    
    All settings can be overridden via environment variables.
    For local development, create a .env file (see .env.example).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=("settings_",),  # Fix Pydantic warning for model_* fields
    )

    # ============================================================
    # Storage — cloud-agnostic via fsspec
    # ============================================================
    storage_backend: Literal["local", "s3", "gcs", "azure"] = Field(
        default="local",
        description="Storage backend: local | s3 | gcs | azure",
    )
    storage_uri: str = Field(
        default="data/",
        description="Base URI for all artifacts (supports s3://, gs://, az://)",
    )

    # ============================================================
    # MLflow
    # ============================================================
    mlflow_tracking_uri: str = Field(
        default="http://localhost:5001",
        description="MLflow tracking server URI",
    )
    mlflow_experiment_name: str = Field(
        default="stock-lstm-prediction",
        description="MLflow experiment name",
    )
    mlflow_artifact_root: str = Field(
        default="s3://mlflow-artifacts",
        description="Artifact storage root (fsspec-compatible)",
    )

    # ============================================================
    # Feast Feature Store
    # ============================================================
    feast_repo_path: str = Field(
        default="feast/",
        description="Path to Feast repository",
    )
    feast_registry_path: str = Field(
        default="data/feast/registry.db",
        description="Feast registry database path",
    )

    # ============================================================
    # Redis (Online Feature Store)
    # ============================================================
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL for Feast online store",
    )

    # ============================================================
    # ChromaDB (Vector Store for RAG)
    # ============================================================
    chroma_host: str = Field(default="localhost", description="ChromaDB host")
    chroma_port: int = Field(default=8002, description="ChromaDB port")
    chroma_collection: str = Field(
        default="market_knowledge",
        description="ChromaDB collection name for market knowledge",
    )

    # ============================================================
    # LLM Configuration (cloud-agnostic via LiteLLM)
    # ============================================================
    llm_model: str = Field(
        default="ollama/llama3",
        description="LLM model identifier (supports ollama/, bedrock/, azure/, openai/)",
    )
    llm_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for LLM service (for Ollama)",
    )
    llm_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="LLM temperature for generation",
    )
    llm_max_tokens: int = Field(
        default=2048,
        ge=1,
        le=8192,
        description="Maximum tokens for LLM generation",
    )
    
    # API Keys for LLM providers
    google_api_key: str | None = Field(
        default=None,
        description="Google API Key for Gemini models",
    )
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API Key",
    )
    groq_api_key: str | None = Field(
        default=None,
        description="Groq API Key for Llama models",
    )

    # ============================================================
    # Data Ingestion
    # ============================================================
    data_tickers: str = Field(
        default="ITUB4.SA,PETR4.SA,VALE3.SA,BBDC4.SA,BBAS3.SA,^BVSP",
        description="Comma-separated list of tickers to download",
    )
    data_start_date: str = Field(
        default="2020-01-01",
        description="Start date for historical data (YYYY-MM-DD)",
    )
    data_interval: str = Field(
        default="1d",
        description="Data interval: 1d, 1h, etc.",
    )

    # ============================================================
    # Model Hyperparameters
    # ============================================================
    model_lstm_units: int = Field(default=50, ge=16, le=256)
    model_dropout: float = Field(default=0.2, ge=0.0, le=0.8)
    model_epochs: int = Field(default=50, ge=1, le=500)
    model_batch_size: int = Field(default=32, ge=8, le=128)
    model_seq_length: int = Field(
        default=60,
        ge=10,
        le=200,
        description="Sequence length for LSTM",
    )

    # ============================================================
    # AWS (only required for S3 backend or AWS deployment)
    # ============================================================
    aws_region: str = Field(default="us-east-1")
    aws_account_id: str = Field(default="123456789012")
    s3_bucket: str = Field(default="fiap-tc-fase5-data")
    s3_model_prefix: str = Field(default="models/")
    s3_data_prefix: str = Field(default="data/")
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_endpoint_url: str | None = Field(
        default=None,
        description="Custom S3 endpoint (for MinIO, LocalStack, etc.)",
    )

    # ============================================================
    # API Configuration
    # ============================================================
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_workers: int = Field(default=1, ge=1, le=16)
    api_log_level: Literal["debug", "info", "warning", "error"] = Field(default="info")

    # ============================================================
    # Monitoring
    # ============================================================
    prometheus_port: int = Field(default=9090, ge=1, le=65535)
    grafana_port: int = Field(default=3000, ge=1, le=65535)
    grafana_admin_password: str = Field(default="admin")

    # ============================================================
    # Security
    # ============================================================
    enable_guardrails: bool = Field(
        default=True,
        description="Enable input/output guardrails for LLM",
    )
    max_input_tokens: int = Field(
        default=1000,
        ge=10,
        le=10000,
        description="Max tokens per input request",
    )
    max_output_tokens: int = Field(
        default=2000,
        ge=10,
        le=10000,
        description="Max tokens per output response",
    )

    # ============================================================
    # Helper methods
    # ============================================================
    def get_tickers_list(self) -> list[str]:
        """Parse comma-separated tickers into a list."""
        return [t.strip() for t in self.data_tickers.split(",") if t.strip()]

    def get_storage_full_path(self, subpath: str) -> str:
        """
        Build full storage path by concatenating storage_uri + subpath.
        
        Examples:
            - Local: data/ + models/lstm.keras → data/models/lstm.keras
            - S3: s3://bucket/ + models/lstm.keras → s3://bucket/models/lstm.keras
        """
        base = self.storage_uri.rstrip("/")
        sub = subpath.lstrip("/")
        return f"{base}/{sub}"

    def is_cloud_storage(self) -> bool:
        """Check if using cloud storage (not local)."""
        return self.storage_backend in {"s3", "gcs", "azure"}


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to ensure settings are loaded only once per process.
    """
    return Settings()
