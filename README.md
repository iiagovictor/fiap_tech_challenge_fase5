# FIAP Tech Challenge Fase 5 — Plataforma MLOps/LLMOps Cloud-Agnostic

[![CI/CD](https://github.com/your-org/fiap-tc-fase5/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/fiap-tc-fase5/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📋 Visão Geral

Plataforma MLOps/LLMOps **cloud-agnostic** para o Datathon da Fase 5, evoluindo o modelo LSTM da Fase 4 para uma arquitetura empresarial com:

- **Baseline ML**: LSTM para previsão de ações brasileiras (ITUB4, PETR4, VALE3)
- **Feature Store**: Feast (offline + online Redis)
- **Model Registry**: MLflow open-source
- **LLM Agent**: ReAct-style com RAG sobre dados financeiros
- **Observabilidade**: Prometheus + Grafana + Evidently (drift)
- **Deploy**: AWS ECS Fargate + API Gateway (mas agnóstico)

### 🎯 Cloud-Agnostic Design

- **Storage**: `fsspec` (local/S3/GCS/Azure intercambiáveis)
- **ML Tracking**: MLflow open-source (não SageMaker)
- **Feature Store**: Feast (não AWS Feature Store)
- **Container**: ECS Fargate, mas pode rodar em GKE/AKS
- **IaC**: Terraform modular (trocar provider com mínimas mudanças)

---

## 🏛️ Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                     DATA LAYER (Cloud-Agnostic)                  │
├─────────────────────────────────────────────────────────────────┤
│  yfinance → Parquet (S3/GCS/Azure) → Feast → Redis Online Store │
└────────────────┬────────────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────────┐
│              ML TRAINING LAYER (ECS Task / Local)             │
├───────────────────────────────────────────────────────────────┤
│  Features → Train LSTM → MLflow Tracking → Model Registry     │
└────────────────┬──────────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────────┐
│            SERVING LAYER (ECS Fargate + API Gateway)          │
├───────────────────────────────────────────────────────────────┤
│  FastAPI → /predict (LSTM) + /agent (LLM+RAG) + /drift       │
└────────────────┬──────────────────────────────────────────────┘
                 │
┌────────────────▼─────────────────────────────────────────────┐
│          OBSERVABILITY (Prometheus + Grafana + Evidently)     │
└───────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Pré-requisitos

- Python 3.11+
- Docker + Docker Compose
- AWS CLI configurado (para deploy)
- Terraform 1.5+ (opcional, para IaC)
- Google API Key (para LLM Gemini - opcional)

### Setup Local

```bash
# 1. Clonar e configurar ambiente
git clone <repo-url>
cd fiap_tech_challenge_fase5
cp .env.example .env

# 2. Criar ambiente virtual e instalar dependências
python3.12 -m venv .venv
source .venv/bin/activate
make install            # Core (ML + API)
make install-llm        # Adiciona LLM/RAG (opcional)
make install-feast      # Adiciona Feature Store (opcional)

# 3. Subir infraestrutura local (MLflow, Redis, Prometheus, Grafana, ChromaDB)
make setup-infra

# 4. Configurar LLM (opcional)
# Edite .env e adicione:
# LLM_MODEL=gemini/gemini-2.0-flash-exp
# GOOGLE_API_KEY=sua-chave-aqui

# 5. Popular base de conhecimento RAG (opcional)
make seed-rag

# 6. Executar pipeline end-to-end
make data-download      # Baixa dados yfinance
make data-features      # Gera features técnicas
make feast-apply        # Configura Feature Store
make feast-materialize  # Popula Redis
make train              # Treina LSTM + registra no MLflow
make serve              # API em localhost:8000
```

**Serviços Locais:**
- 🔬 MLflow: http://localhost:5001
- 📊 Grafana: http://localhost:3000 (admin/admin)
- 📈 Prometheus: http://localhost:9090
- 🗄️ ChromaDB: http://localhost:8002
- 🚀 API: http://localhost:8000/docs

---

## 📂 Estrutura do Projeto

```
fiap_tech_challenge_fase5/
├── .github/workflows/     # CI/CD (lint, test, build, deploy)
├── src/
│   ├── config/            # Settings + Storage abstraction (fsspec)
│   ├── data/              # Data ingestion (yfinance)
│   ├── features/          # Feature engineering + Feast client
│   ├── models/            # LSTM baseline + training pipeline
│   ├── agent/             # LLM Agent ReAct + RAG + Tools
│   ├── serving/           # FastAPI app + Dockerfile
│   ├── monitoring/        # Drift detection + Prometheus metrics
│   └── security/          # Guardrails + PII detection
├── feast/                 # Feature Store definitions
├── terraform/             # IaC AWS (ECS, ALB, API Gateway, S3)
├── tests/                 # Pytest (coverage ≥60%)
├── docs/                  # Model Card, System Card, OWASP, LGPD
├── docker-compose.yml     # Local infra (MLflow, Redis, Grafana)
├── dvc.yaml               # Data pipeline versionamento
├── pyproject.toml         # Dependências + config tools
└── Makefile               # Comandos utilitários
```

---

## 🔧 Comandos Principais

### Desenvolvimento

```bash
make lint          # Ruff + Mypy
make test          # Pytest com cobertura
make format        # Auto-format código
```

### Pipeline de Dados

```bash
make data-download        # Baixa ITUB4, PETR4, VALE3, etc.
make data-features        # Calcula RSI, MACD, EMAs, etc.
make feast-apply          # Aplica definições Feature Store
make feast-materialize    # Materializa features no Redis
make seed-rag             # Popula ChromaDB com conhecimento (opcional)
```

### Treinamento

```bash
make train         # Treina LSTM, loga no MLflow, registra modelo
```

### Serving

```bash
make serve         # API local (porta 8000)
make serve-docker  # API em container Docker
```

### Deploy AWS

```bash
# Com Terraform
cd terraform/aws
terraform init
terraform plan -var-file=../../config/prod.tfvars
terraform apply

# Ou via GitHub Actions (após push na main)
git push origin main  # CI/CD automático
```

---

## 📊 Endpoints da API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/health` | Health check + status modelo |
| `GET` | `/metrics` | Métricas Prometheus |
| `GET` | `/drift` | Report de drift (Evidently) |
| `POST` | `/predict` | Previsão LSTM (5 dias à frente) |
| `POST` | `/agent` | Agente LLM com RAG sobre mercado |

### Exemplo: Previsão LSTM

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"ticker": "ITUB4.SA"}'
```

### Exemplo: Agente Financeiro

```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Qual a cotação da PETR4.SA?",
    "ticker": "PETR4.SA"
  }'
```

**Nota:** O agente tem fallback automático:
1. Tenta LLM Gemini (ReAct + RAG)
2. Se indisponível, usa `gemini-1.5-flash` (mais rápido)
3. Se falhar, retorna dados diretos do yfinance

#### Ferramentas Disponíveis para o Agente

O agente ReAct tem acesso a:
- 📈 **`predict_stock_direction`** - Predição de valorização usando modelo LSTM ou indicadores técnicos
- 📊 **`get_stock_price_history`** - Histórico de preços via yfinance
- 🔧 **`calculate_technical_indicators`** - RSI, MACD, Médias Móveis, Bollinger Bands
- 🔀 **`compare_stocks`** - Comparação de performance entre ações
- 📚 **RAG Knowledge Base** - Conceitos de análise técnica (ChromaDB)

**Exemplo com predição LSTM:**
```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Qual é a probabilidade do ITUB4.SA valorizar amanhã?",
    "ticker": "ITUB4.SA"
  }'
```

---

## 🌍 Cloud Providers Suportados

### AWS (Configuração Atual)

- **Compute**: ECS Fargate
- **Storage**: S3 para dados/modelos/artifacts
- **Network**: ALB + API Gateway
- **Monitoring**: CloudWatch + Prometheus exporters
- **IaC**: `terraform/aws/`

Para trocar de cloud, basta ajustar variáveis no `.env`:

```bash
# Azure
STORAGE_BACKEND=azure
STORAGE_URI=az://container/path
MLFLOW_ARTIFACT_ROOT=az://mlflow

# GCP
STORAGE_BACKEND=gcs
STORAGE_URI=gs://bucket/path
MLFLOW_ARTIFACT_ROOT=gs://mlflow-artifacts
```

O código core (`src/`) **não muda**.

---

## 📈 Monitoramento e Drift

- **Prometheus**: Coleta métricas customizadas (latência, throughput, erros)
- **Grafana**: Dashboards pré-configurados em `configs/grafana/`
- **Evidently**: Drift detection com PSI > 0.2 → trigger retrain

Acesse métricas em:
```bash
curl http://localhost:8000/metrics      # Formato Prometheus
curl http://localhost:8000/drift        # JSON com drift_share
```

---

## 🧪 Testes

```bash
# Todos os testes
make test

# Apenas API
pytest tests/test_api.py -v

# Com cobertura HTML
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

**Coverage mínimo**: 60% (configurado em `pyproject.toml`)

---

## 🔐 Segurança (OWASP Top 10 LLM)

- ✅ **Prompt Injection**: Input guardrails com regex patterns
- ✅ **PII Leakage**: Presidio para anonimização automática
- ✅ **Insecure Output**: Output sanitization antes de retornar
- ✅ **Model DoS**: Timeouts e rate limiting
- ✅ **Supply Chain**: Dependências locked em `pyproject.toml`

Ver: [`docs/OWASP_MAPPING.md`](docs/OWASP_MAPPING.md)

---

## 📚 Documentação

- [Model Card](docs/MODEL_CARD.md) — Metadados do modelo LSTM
- [System Card](docs/SYSTEM_CARD.md) — Arquitetura da plataforma
- [LGPD Plan](docs/LGPD_PLAN.md) — Conformidade com LGPD
- [OWASP Mapping](docs/OWASP_MAPPING.md) — Ameaças e mitigações
- [Red Team Report](docs/RED_TEAM_REPORT.md) — Testes adversariais

---

## 🤝 Contribuindo

Este é um projeto acadêmico (FIAP Tech Challenge Fase 5). Para contribuir:

1. Fork o repositório
2. Crie uma branch: `git checkout -b feature/nova-funcionalidade`
3. Commit: `git commit -m 'feat: adiciona X'`
4. Push: `git push origin feature/nova-funcionalidade`
5. Abra um Pull Request

---

## 📜 Licença

MIT License - ver [LICENSE](LICENSE) para detalhes.

---

## 👥 Time

Projeto desenvolvido como parte do Datathon FIAP - Fase 05 (LLMs e Agentes).

---

## 🔗 Links Úteis

- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)
- [Feast Documentation](https://docs.feast.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Evidently AI](https://docs.evidentlyai.com/)
- [OWASP Top 10 for LLMs](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
