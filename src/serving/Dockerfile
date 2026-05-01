# Multi-stage build for production
FROM python:3.12-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements for installation (need README.md for hatchling)
COPY pyproject.toml README.md /tmp/
WORKDIR /tmp

# Install dependencies (core only to speed up build)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    pandas numpy pyarrow yfinance ta \
    fsspec s3fs \
    scikit-learn tensorflow mlflow \
    fastapi uvicorn pydantic pydantic-settings \
    prometheus-client structlog tenacity rich joblib boto3 python-dotenv

# ============================================================
# Final stage
# ============================================================
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "src.serving.app:app", "--host", "0.0.0.0", "--port", "8000"]
