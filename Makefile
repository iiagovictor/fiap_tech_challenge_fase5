.PHONY: help install dev-install setup-infra teardown-infra \
        data-download data-features feast-apply feast-materialize \
        train serve serve-alt stop-serve serve-docker test test-cov lint format \
        dvc-init dvc-push dvc-pull clean deploy-aws seed-rag

# Detectar OS e configurar caminhos apropriados
ifeq ($(OS),Windows_NT)
    PYTHON := $(CURDIR)\.venv\Scripts\python.exe
else
    PYTHON := $(CURDIR)/.venv/bin/python
endif
COMPOSE := docker compose
PROJECT := fiap-tc-fase5
AWS_REGION := us-east-1
ECR_REPO := $(PROJECT)

# ─── Help ─────────────────────────────────────────────────────────────────────
help:  ## Mostra este help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Installation ─────────────────────────────────────────────────────────────
install:  ## Instala dependências CORE (ML + API, sem LLM)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .

install-full:  ## Instala TODAS as dependências (LLM + Feast + Security)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[llm,feast-support,monitoring,security,pipeline,cloud]"

install-llm:  ## Instala apenas dependências LLM/RAG (LiteLLM + ChromaDB)
	$(PYTHON) -m pip install -e ".[llm]"

install-feast:  ## Instala Feature Store (Feast + Redis)
	$(PYTHON) -m pip install -e ".[feast-support]"

dev-install:  ## Instala dependências de desenvolvimento
	$(PYTHON) -m pip install -e ".[dev]"
	.venv/bin/pre-commit install

# ─── Local Infrastructure (Docker) ───────────────────────────────────────────
setup-infra:  ## Sobe MLflow, Redis, Prometheus, Grafana
	$(COMPOSE) up -d
	@echo "⏳ Aguardando serviços iniciarem..."
	@sleep 15
	@echo "──────────────────────────────────────────"
	@echo "  ✅ Infraestrutura pronta!"
	@echo "  🔬 MLflow:     http://localhost:5001"
	@echo "  📦 MinIO:      http://localhost:9001  (minioadmin / minioadmin123)"
	@echo "  📊 Grafana:    http://localhost:3000  (admin / admin)"
	@echo "  📈 Prometheus: http://localhost:9090"
	@echo "  🗄️  ChromaDB:   http://localhost:8002"
	@echo "──────────────────────────────────────────"

teardown-infra:  ## Para e remove todos os containers
	$(COMPOSE) down -v

# ─── Data Pipeline ────────────────────────────────────────────────────────────
data-download:  ## Baixa dados do yfinance (ITUB4, PETR4, VALE3, etc.)
	$(PYTHON) -m src.data.ingestion

data-features:  ## Gera features técnicas (RSI, MACD, EMAs, Bollinger)
	$(PYTHON) -m src.features.feature_engineering

# ─── Feature Store (Feast) ────────────────────────────────────────────────────
feast-apply:  ## Aplica definições do Feature Store
	@mkdir -p feast/data/feast
	cd feast && ../.venv/bin/feast apply

feast-materialize:  ## Materializa features no Redis (online store)
	@echo "⚠️  Certifique-se que o Redis está rodando (make setup-infra)"
	@mkdir -p feast/data/feast
	cd feast && ../.venv/bin/feast materialize-incremental $$(date -u +%Y-%m-%dT%H:%M:%S)

feast-ui:  ## Abre Feast Web UI (porta 8888)
	cd feast && ../.venv/bin/feast ui

# ─── RAG Knowledge Base ───────────────────────────────────────────────────────
seed-rag:  ## Popula ChromaDB com conhecimento inicial (análise técnica)
	@echo "🌱 Seeding RAG knowledge base..."
	$(PYTHON) -m src.agent.seed_rag

# ─── Training ─────────────────────────────────────────────────────────────────
train:  ## Treina modelo LSTM e registra no MLflow
	@set -a && source .env && set +a && $(PYTHON) -m src.models.train

train-baseline:  ## Treina apenas baselines (LogReg + RF) sem LSTM
	@set -a && source .env && set +a && $(PYTHON) -m src.models.baseline

# ─── Serving ──────────────────────────────────────────────────────────────────
serve:  ## Inicia API FastAPI local (porta 8000)
	$(PYTHON) -m uvicorn src.serving.app:app --host 0.0.0.0 --port 8000 --reload

serve-alt:  ## Inicia API em porta alternativa (8001)
	$(PYTHON) -m uvicorn src.serving.app:app --host 0.0.0.0 --port 8001 --reload

stop-serve:  ## Para o servidor na porta 8000
	@echo "🛑 Parando servidor na porta 8000..."
	@lsof -ti:8000 | xargs kill -9 2>/dev/null || echo "✅ Nenhum processo na porta 8000"

serve-docker:  ## Inicia API em container Docker
	docker build -t $(PROJECT)-serving -f src/serving/Dockerfile .
	docker run -p 8000:8000 --env-file .env $(PROJECT)-serving

# ─── Tests ────────────────────────────────────────────────────────────────────
test:  ## Executa testes unitários
	$(PYTHON) -m pytest tests/ -v

test-cov:  ## Executa testes com relatório de cobertura HTML
	$(PYTHON) -m pytest tests/ -v --cov=src --cov-report=html --cov-fail-under=60
	@echo "📊 Relatório de cobertura: htmlcov/index.html"

test-smoke:  ## Smoke test rápido (apenas health check)
	$(PYTHON) -m pytest tests/test_api.py::test_health -v

# ─── Code Quality ─────────────────────────────────────────────────────────────
lint:  ## Executa ruff e mypy
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m mypy src/ --ignore-missing-imports

format:  ## Formata código com ruff
	$(PYTHON) -m ruff format src/ tests/
	$(PYTHON) -m ruff check --fix src/ tests/

# ─── DVC ──────────────────────────────────────────────────────────────────────
dvc-init:  ## Inicializa DVC (primeira vez)
	dvc init
	@echo "⚙️  Configure remote: dvc remote add -d storage s3://your-bucket/dvc"

dvc-push:  ## Envia dados/modelos versionados para remote
	dvc push

dvc-pull:  ## Baixa dados/modelos versionados do remote
	dvc pull

dvc-repro:  ## Reproduz pipeline DVC end-to-end
	dvc repro

# ─── AWS Deployment ───────────────────────────────────────────────────────────
deploy-aws:  ## Deploy completo na AWS via Terraform
	@echo "🚀 Iniciando deploy na AWS..."
	cd terraform/aws && terraform init
	cd terraform/aws && terraform apply -var-file=../../config/prod.tfvars -auto-approve
	@echo "✅ Deploy concluído!"

docker-build-push:  ## Build e push da imagem Docker para ECR
	@echo "🐳 Building Docker image..."
	docker build -t $(ECR_REPO):latest -f src/serving/Dockerfile .
	@echo "🔐 Autenticando no ECR..."
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin $$(aws sts get-caller-identity --query Account --output text).dkr.ecr.$(AWS_REGION).amazonaws.com
	@echo "📤 Pushing para ECR..."
	docker tag $(ECR_REPO):latest $$(aws sts get-caller-identity --query Account --output text).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO):latest
	docker push $$(aws sts get-caller-identity --query Account --output text).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO):latest
	@echo "✅ Imagem disponível no ECR!"

# ─── Cleanup ──────────────────────────────────────────────────────────────────
clean:  ## Remove arquivos temporários e caches
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".mypy_cache" -delete
	find . -type d -name "htmlcov" -delete
	find . -type d -name ".ruff_cache" -delete
	rm -rf dist/ build/ *.egg-info/
	rm -rf .coverage coverage.xml

clean-data:  ## Remove dados baixados (use com cuidado!)
	rm -rf data/raw/* data/processed/*
	@echo "⚠️  Dados removidos. Execute 'make data-download' para refazer."
