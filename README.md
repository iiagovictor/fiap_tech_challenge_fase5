# FIAP Tech Challenge — Fase 5: Plataforma MLOps/LLMOps Cloud-Agnostic

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![MLflow](https://img.shields.io/badge/MLflow-2.13-0194E2?logo=mlflow)](https://mlflow.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker)](https://docs.docker.com/compose/)

---

## Sumário

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Configuração do Ambiente (.env)](#configuração-do-ambiente-env)
- [Infraestrutura Local (Docker)](#infraestrutura-local-docker)
- [Pipeline de Dados](#pipeline-de-dados)
- [Feature Store com Feast](#feature-store-com-feast)
- [Treinamento do Modelo](#treinamento-do-modelo)
- [Servindo a API](#servindo-a-api)
- [Agente LLM (ReAct + RAG)](#agente-llm-react--rag)
- [Monitoramento](#monitoramento)
- [Testes](#testes)
- [Avaliação de Qualidade RAG (RAGAS)](#avaliação-de-qualidade-rag-ragas)
- [Pipeline DVC (Versionamento de Dados)](#pipeline-dvc-versionamento-de-dados)
- [Referência da API](#referência-da-api)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Cloud Providers Suportados](#cloud-providers-suportados)
- [Segurança](#segurança)
- [Solução de Problemas](#solução-de-problemas)
- [Documentação Adicional](#documentação-adicional)

---

## Visão Geral

Esta plataforma é uma solução **MLOps/LLMOps cloud-agnostic** desenvolvida como parte do Datathon FIAP — Fase 5. Ela integra um pipeline completo de aprendizado de máquina com um agente de linguagem natural para análise do mercado financeiro brasileiro (B3).

### O que a plataforma faz

| Capability | Descrição |
|---|---|
| **Predição de ações** | Modelo LSTM que classifica se uma ação vai subir ou cair nos próximos 5 dias úteis |
| **Feature Engineering** | Calcula 24 indicadores técnicos (RSI, MACD, Bollinger Bands, ATR, OBV, médias móveis) |
| **Schema Validation** | Pandera valida schemas dos dados em todas as etapas do pipeline (raw, features, treino) |
| **Feature Store** | Feast com offline store (Parquet) e online store (Redis) |
| **Model Registry** | MLflow para rastrear experimentos e versionar modelos em produção |
| **API REST** | FastAPI com endpoints de predição, saúde, métricas e drift |
| **Agente LLM** | Agente ReAct com RAG que responde perguntas sobre ações em linguagem natural |
| **Avaliação RAG** | RAGAS (Faithfulness, Answer Relevancy, Context Precision/Recall) + Golden Set com métricas de similaridade |
| **Monitoramento** | Prometheus + Grafana + Evidently para observabilidade completa |
| **Segurança** | Guardrails contra prompt injection + detecção de PII com Presidio |

### Ativos cobertos

Por padrão, o projeto baixa dados dos seguintes ativos desde 01/01/2020:

- `ITUB4.SA` — Itaú Unibanco
- `PETR4.SA` — Petrobras PN
- `VALE3.SA` — Vale ON
- `BBDC4.SA` — Bradesco PN
- `BBAS3.SA` — Banco do Brasil ON
- `^BVSP` — Índice Bovespa

---

## Arquitetura

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        CAMADA DE DADOS                                   │
│                                                                          │
│  yfinance API ──► Parquet (local/S3/GCS/Azure) ──► Feast Offline Store   │
│                                   │                        │             │
│                                   └────────────────► Redis Online Store  │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼─────────────────────────────────────┐
│                      CAMADA DE TREINAMENTO                               │
│                                                                          │
│  Feature Engineering (24 indicadores) ──► LSTM (TensorFlow/Keras)        │
│                                                 │                        │
│                                          MLflow Tracking                 │
│                                          MLflow Registry                 │
│                                          (MinIO como artefact store)     │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼─────────────────────────────────────┐
│                        CAMADA DE SERVING                                 │
│                                                                          │
│  FastAPI ──► /predict  (LSTM — janela 60 dias)                           │
│          ──► /agent    (LLM ReAct + RAG — ChromaDB)                      │
│          ──► /drift    (Evidently — PSI drift detection)                 │
│          ──► /metrics  (Prometheus scraping)                             │
│          ──► /health   (liveness/readiness probe)                        │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼─────────────────────────────────────┐
│                      CAMADA DE OBSERVABILIDADE                           │
│                                                                          │
│  Prometheus (coleta) ──► Grafana (dashboards) ──► Alertas               │
│  Evidently (drift PSI > 0.2) ──► Trigger de retreinamento               │
└──────────────────────────────────────────────────────────────────────────┘
```

### Serviços de Infraestrutura (Docker)

| Serviço | Porta(s) | Propósito |
|---|---|---|
| `mlflow` | `5001` | Model Registry + Experiment Tracking |
| `minio` | `9000` (API), `9001` (Console) | Object storage S3-compatível (artefatos, dados) |
| `redis` | `6379` | Online Feature Store do Feast |
| `chromadb` | `8002` | Banco vetorial para RAG do agente |
| `prometheus` | `9090` | Coleta de métricas da API |
| `grafana` | `3000` | Dashboards de monitoramento |
| `ollama` | `11434` | LLM local (alternativa cloud-free) |
| `api` | `8000` | FastAPI — endpoint principal |

---

## Pré-requisitos

Antes de começar, certifique-se de ter instalado:

### Obrigatórios

| Ferramenta | Versão mínima | Verificação | Download |
|---|---|---|---|
| Python | 3.11+ | `python3 --version` | [python.org](https://www.python.org/downloads/) |
| Docker | 24+ | `docker --version` | [docker.com](https://docs.docker.com/get-docker/) |
| Docker Compose | 2.20+ | `docker compose version` | Incluído no Docker Desktop |
| Git | 2.30+ | `git --version` | [git-scm.com](https://git-scm.com/) |

### Opcionais (para funcionalidades extras)

| Ferramenta | Para que serve |
|---|---|
| Google API Key | Usar Gemini como LLM do agente (recomendado) |
| OpenAI API Key | Usar GPT-4 como LLM alternativo |
| AWS CLI | Deploy em produção na AWS |
| Terraform 1.5+ | Infraestrutura como código (IaC) |

> **Dica:** Sem chave de API de LLM, o projeto usa o Ollama local com `llama3`. Isso funciona perfeitamente, mas requer ~5 GB de memória RAM para o modelo.

### Verificando os pré-requisitos

```bash
python3 --version        # Python 3.11.x ou superior
docker --version         # Docker version 24.x.x
docker compose version   # Docker Compose version v2.x.x
git --version            # git version 2.x.x
```

---

## Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/fiap_tech_challenge_fase5.git
cd fiap_tech_challenge_fase5
```

### 2. Crie e ative o ambiente virtual Python

```bash
# Criar ambiente virtual
python3 -m venv .venv

# Ativar (macOS/Linux)
source .venv/bin/activate

# Ativar (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Confirme que o ambiente está ativo (deve aparecer (.venv) no prompt)
which python    # deve apontar para .venv/bin/python
```

### 3. Instale as dependências

Instale de acordo com o que você precisa:

```bash
# Instalação mínima — ML + API (sempre necessário)
make install

# Adiciona suporte ao Agente LLM e RAG (ChromaDB, LangChain, LiteLLM)
make install-llm

# Adiciona suporte ao Feature Store Feast + Redis
make install-feast

# Adiciona detecção de drift com Evidently
pip install ".[monitoring]"

# Adiciona detecção de PII com Presidio
pip install ".[security]"

# Instala tudo de uma vez
make install-full

# Instala ferramentas de desenvolvimento (pytest, ruff, mypy, pre-commit)
make dev-install
```

### 4. Verifique a instalação

```bash
python -c "import pandas, numpy, sklearn, tensorflow, mlflow, fastapi; print('OK!')"
```

---

## Configuração do Ambiente (.env)

O projeto usa variáveis de ambiente para toda configuração sensível. Copie o arquivo de exemplo e edite conforme necessário:

```bash
cp .env.example .env
```

### Configurações essenciais (mínimo para rodar localmente)

Abra o arquivo `.env` e verifique/ajuste as seguintes variáveis:

```bash
# ─── Storage ────────────────────────────────────────────────────────────────
STORAGE_BACKEND=local       # local | s3 | gcs | azure
STORAGE_URI=data/           # caminho base para dados e modelos

# ─── MLflow ─────────────────────────────────────────────────────────────────
MLFLOW_TRACKING_URI=http://localhost:5001
MLFLOW_EXPERIMENT_NAME=stock-lstm-prediction
MLFLOW_ARTIFACT_ROOT=s3://mlflow-artifacts

# ─── MinIO (S3 local para artefatos MLflow) ──────────────────────────────────
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin123
MLFLOW_S3_ENDPOINT_URL=http://localhost:9000
AWS_ENDPOINT_URL=http://localhost:9000

# ─── Feature Store ───────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379

# ─── RAG (ChromaDB) ──────────────────────────────────────────────────────────
CHROMA_HOST=localhost
CHROMA_PORT=8002
CHROMA_COLLECTION=market_knowledge

# ─── Dados das Ações ─────────────────────────────────────────────────────────
DATA_TICKERS=ITUB4.SA,PETR4.SA,VALE3.SA,BBDC4.SA,BBAS3.SA,^BVSP
DATA_START_DATE=2020-01-01
DATA_INTERVAL=1d

# ─── Modelo LSTM ─────────────────────────────────────────────────────────────
MODEL_LSTM_UNITS=50
MODEL_DROPOUT=0.2
MODEL_EPOCHS=50
MODEL_BATCH_SIZE=32
MODEL_SEQ_LENGTH=60         # janela de 60 dias úteis de contexto
```

### Configuração do LLM para o Agente

Escolha **uma** das opções abaixo para configurar o modelo de linguagem:

#### Opção A — Google Gemini (recomendado, mais rápido)

Obtenha sua chave gratuitamente em [aistudio.google.com](https://aistudio.google.com/app/apikey).

```bash
LLM_MODEL=gemini/gemini-2.0-flash-exp
GOOGLE_API_KEY=AIza...sua-chave-aqui
```

#### Opção B — OpenAI GPT-4

```bash
LLM_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=sk-...sua-chave-aqui
```

#### Opção C — Groq (ultra-rápido, gratuito com limites)

Obtenha sua chave em [console.groq.com](https://console.groq.com).

```bash
LLM_MODEL=groq/llama3-8b-8192
GROQ_API_KEY=gsk_...sua-chave-aqui
```

#### Opção D — Ollama Local (sem custo, offline)

Não requer chave de API. O modelo é baixado automaticamente pelo Docker.

```bash
LLM_MODEL=ollama/llama3
LLM_BASE_URL=http://localhost:11434
```

> **Nota:** O Ollama requer ~5 GB de RAM e pode ser lento em máquinas sem GPU.

---

## Infraestrutura Local (Docker)

### Subindo todos os serviços

```bash
make setup-infra
```

Este comando executa `docker compose up -d` e aguarda 15 segundos para os serviços inicializarem. Ao final, exibe uma tabela com as URLs de todos os serviços.

### Verificando o status dos containers

```bash
docker compose ps
```

**Saída esperada:**

```
NAME                 STATUS              PORTS
mlflow_server        Up (healthy)        0.0.0.0:5001->5000/tcp
minio_storage        Up (healthy)        0.0.0.0:9000-9001->9000-9001/tcp
redis_feast          Up (healthy)        0.0.0.0:6379->6379/tcp
chromadb_rag         Up                  0.0.0.0:8002->8000/tcp
prometheus_monitor   Up                  0.0.0.0:9090->9090/tcp
grafana_monitor      Up                  0.0.0.0:3000->3000/tcp
ollama_llm           Up                  0.0.0.0:11434->11434/tcp
```

### Acessando os serviços

| Serviço | URL | Credenciais |
|---|---|---|
| **MLflow UI** | http://localhost:5001 | — |
| **MinIO Console** | http://localhost:9001 | `minioadmin` / `minioadmin123` |
| **Grafana** | http://localhost:3000 | `admin` / `admin` |
| **Prometheus** | http://localhost:9090 | — |
| **ChromaDB** | http://localhost:8002 | — |
| **API Docs** | http://localhost:8000/docs | — |

### Parando a infraestrutura

```bash
# Para os containers (mantém volumes)
docker compose down

# Para os containers e remove todos os dados (⚠️ irreversível)
make teardown-infra
```

---

## Pipeline de Dados

### Etapa 1 — Download dos dados históricos

```bash
make data-download
```

Este comando executa `src/data/ingestion.py`, que:
- Conecta ao Yahoo Finance via `yfinance`
- Baixa dados OHLCV (Open, High, Low, Close, Volume) desde `DATA_START_DATE`
- Salva em `data/raw/raw_stock_data.parquet`

**Verificando o resultado:**
```bash
python -c "
import pandas as pd
df = pd.read_parquet('data/raw/raw_stock_data.parquet')
print(df.shape)          # ex: (7000, 30)
print(df.columns.tolist())
print(df.tail())
"
```

### Etapa 2 — Feature Engineering

```bash
make data-features
```

Este comando executa `src/features/feature_engineering.py`, que calcula:

| Categoria | Indicadores |
|---|---|
| Tendência | SMA(20), SMA(50), EMA(12), EMA(26) |
| Momentum | RSI(14), MACD, MACD Signal, MACD Hist |
| Volatilidade | Bollinger Bands (upper/middle/lower), ATR(14) |
| Volume | OBV, Volume SMA(20) |
| Target | `target_5d` — 1 se preço subir em 5 dias, 0 se cair |

**Resultado salvo em:** `data/features/stock_features.parquet`

**Verificando:**
```bash
python -c "
import pandas as pd
df = pd.read_parquet('data/features/stock_features.parquet')
print(f'Shape: {df.shape}')
print(f'Target distribution:\n{df[\"target_5d\"].value_counts(normalize=True)}')
"
```

### Etapa 3 — Validação de Schema com Pandera

Todos os estágios do pipeline incluem **validação de dados com Pandera** para garantir qualidade:

| Etapa | Schema | Validações |
|---|---|---|
| **Raw Data** | `RAW_STOCK_DATA_SCHEMA` | Preços > 0, high ≥ low, sem duplicatas |
| **Features** | `FEATURE_SET_SCHEMA` | Colunas requeridas, RSI ∈ [0,100], tipos de dados |
| **Training Data** | `TRAINING_DATA_SCHEMA` | Target ∈ {0,1}, sem NULLs em features críticas |

**Como funciona:**
- `src/data/ingestion.py` valida raw data após download
- `src/features/feature_engineering.py` valida features antes de salvar
- `src/models/baseline.py` valida dados de treino antes de usar
- `tests/test_features.py` testa schemas com Pandera assertions

**Exemplo de uso direto:**
```python
from src.data.schemas import validate_training_data, validate_features
import pandas as pd

df_raw = pd.read_parquet('data/raw/raw_stock_data.parquet')
df_features = pd.read_parquet('data/features/stock_features.parquet')

# Validar manualmente
validate_features(df_features)      # Lança SchemaError se inválido
validate_training_data(df_features) # Valida também a coluna 'target'
print("✅ Todos os schemas validados!")
```

---

## Feature Store com Feast

O Feast gerencia features offline (Parquet) e online (Redis) para servir predições em produção.

### Etapa 4 — Aplicar definições do Feature Store

```bash
make feast-apply
```

Este comando executa `feast apply` no diretório `feast/`, registrando as definições de:
- **Entity**: `stock_ticker` (identificador único)
- **Feature Views**: indicadores técnicos por ativo
- **Feature Services**: grupos de features para o modelo

**Verificar no Feast UI (opcional):**
```bash
make feast-ui    # Abre UI na porta 8888
```

### Etapa 4 — Materializar features no Redis

```bash
make feast-materialize
```

Sincroniza features do Parquet (offline store) para o Redis (online store), permitindo consultas de baixa latência em produção.

**Verificar materialização:**
```bash
python -c "
from feast import FeatureStore
store = FeatureStore(repo_path='feast/')
# Lista os Feature Views materialized
print(store.list_feature_views())
"
```

---

## Treinamento do Modelo

### Etapa 5 — Treinar e registrar o modelo LSTM

```bash
make train
```

Este comando executa `src/models/train.py` e realiza:

1. **Carrega features** do Parquet com 24 variáveis técnicas
2. **Treina LSTM** (Keras/TensorFlow) com:
   - Janela de 60 dias como contexto
   - 2 camadas LSTM com `MODEL_LSTM_UNITS` unidades cada
   - Dropout de `MODEL_DROPOUT` para regularização
   - Saída Sigmoid (classificação binária: sobe/desce)
3. **Registra no MLflow**: parâmetros, métricas, model artifact e feature names
4. **Promove para Production** no MLflow Model Registry automaticamente

**Acompanhe o treinamento:**
- Terminal: logs de loss/accuracy por época
- MLflow UI: http://localhost:5001 → experimento `stock-lstm-prediction`

**Métricas esperadas:**
```
Epoch 50/50 — loss: 0.68 — accuracy: 0.56 — val_accuracy: 0.55
Test Accuracy: ~0.55–0.60
ROC-AUC: ~0.50–0.55
```

> **Nota sobre performance:** Previsão de mercado financeiro é inerentemente difícil. Um modelo com accuracy de 55–60% já supera o benchmark aleatório (50%) e pode ser lucrativo com a estratégia certa. Consulte [docs/MODEL_CARD.md](docs/MODEL_CARD.md) para mais detalhes e disclaimers.

### Treinando modelos baseline (opcional)

```bash
make train-baseline
```

Treina Logistic Regression e Random Forest para comparação com o LSTM. Todos os experimentos ficam visíveis no MLflow UI.

### Visualizando experimentos no MLflow

1. Acesse http://localhost:5001
2. Clique no experimento `stock-lstm-prediction`
3. Compare runs: parâmetros, métricas e artifacts side by side
4. Acesse `Models > stock-lstm` para ver versões registradas

---

## Servindo a API

### Etapa 6 — Iniciar a API

#### Modo de desenvolvimento (com hot-reload)

```bash
make serve
```

A API será iniciada em http://localhost:8000 com recarregamento automático ao salvar arquivos.

#### Modo alternativo (porta 8001)

```bash
make serve-alt
```

#### Via Docker (equivalente ao ambiente de produção)

```bash
make serve-docker
```

### Verificando que a API está funcionando

```bash
# Health check
curl http://localhost:8000/health

# Resposta esperada:
# {"status":"healthy","timestamp":"2026-05-01T...","model_loaded":true}
```

Se `"model_loaded": false`, o modelo não foi encontrado. Revise a etapa de [Treinamento](#etapa-5--treinar-e-registrar-o-modelo-lstm).

### Documentação interativa da API

Acesse http://localhost:8000/docs para a interface Swagger UI — permite testar todos os endpoints diretamente no browser sem curl.

---

## Agente LLM (ReAct + RAG)

O agente usa o padrão **ReAct** (Reasoning + Acting): a cada passo, o LLM decide qual ferramenta chamar, observa o resultado e repete até chegar em uma resposta.

### Etapa 7 — Populando a base de conhecimento RAG

```bash
make seed-rag
```

Este comando insere documentos sobre análise técnica no ChromaDB (RSI, MACD, Bollinger Bands, etc.), que o agente usa como contexto nas suas respostas.

### Usando o agente

```bash
# Pergunta simples sobre preço
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "Qual a cotação atual da PETR4.SA?"}'

# Análise técnica com indicadores
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "Calcule os indicadores técnicos da VALE3.SA", "ticker": "VALE3.SA"}'

# Predição de direção
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "A ITUB4.SA vai valorizar nos próximos dias?", "ticker": "ITUB4.SA"}'

# Comparação de ações
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare o desempenho de ITUB4.SA e BBDC4.SA no último mês"}'
```

### Resposta típica do agente

```json
{
  "query": "A PETR4.SA vai valorizar nos próximos dias?",
  "response": "Com base na análise do modelo LSTM e indicadores técnicos, a PETR4.SA apresenta probabilidade de 62% de valorização...",
  "sources": ["predict_stock_direction", "calculate_technical_indicators", "RAG: RSI interpretation"],
  "timestamp": "2026-05-01T10:30:00"
}
```

### Ferramentas disponíveis para o agente

| Ferramenta | Parâmetros | O que retorna |
|---|---|---|
| `predict_stock_direction` | `ticker` | Predição LSTM (probabilidade sobe/desce, confiança, recomendação) |
| `get_stock_price_history` | `ticker`, `period` (default `1mo`) | Preço atual, máx/mín, variação %, volume médio |
| `calculate_technical_indicators` | `ticker`, `period` (default `3mo`) | RSI, MACD, SMAs, EMAs, Bollinger Bands com interpretação |
| `compare_stocks` | `tickers` (lista), `period` | Tabela comparativa de performance |

### Lógica de fallback do agente

```
1. POST /predict (modelo LSTM no MLflow)
      ↓ (se não disponível)
2. Indicadores técnicos (RSI, MACD) — lógica de sinais bullish/bearish
      ↓
3. Retorna com baixa confiança e aviso
```

---

## Monitoramento

### Prometheus — Métricas da API

O endpoint `/metrics` expõe métricas no formato Prometheus:

```bash
curl http://localhost:8000/metrics
```

**Métricas disponíveis:**

| Métrica | Tipo | Descrição |
|---|---|---|
| `http_requests_total` | Counter | Total de requisições por método, endpoint e status |
| `http_request_duration_seconds` | Histogram | Latência das requisições |
| `model_predictions_total` | Counter | Total de predições por tipo de modelo |
| `feature_drift_score` | Gauge | Score de drift atual (PSI) |

### Grafana — Dashboards

1. Acesse http://localhost:3000
2. Login: `admin` / `admin` (troque a senha no primeiro acesso)
3. O dashboard **"API Overview"** já está pré-configurado com:
   - Throughput de requisições (req/s)
   - Latência P50/P95/P99
   - Taxa de erros
   - Score de drift em tempo real

### Evidently — Detecção de Drift

```bash
# Obter report de drift via API
curl http://localhost:8000/drift
```

**Resposta:**
```json
{
  "drift_share": 0.08,
  "drifted_features": 2,
  "total_features": 24,
  "threshold": 0.2,
  "status": "ok"
}
```

Se `drift_share > 0.2`, é um sinal para retreinar o modelo:
```bash
make data-download && make data-features && make train
```

---

## Testes

### Executar todos os testes

```bash
make test
```

### Executar com relatório de cobertura HTML

```bash
make test-cov
open htmlcov/index.html    # macOS
```

### Smoke test rápido (apenas health check)

```bash
make test-smoke
```

### Estrutura dos testes

| Arquivo | O que testa |
|---|---|
| `tests/test_api.py` | Endpoints FastAPI (health, predict, agent, drift, metrics) |
| `tests/test_features.py` | Feature engineering + validação de schemas Pandera |
| `tests/test_models.py` | Treinamento e predição do LSTM |
| `tests/test_monitoring.py` | Métricas Prometheus, detecção de drift (Evidently), baseline |
| `tests/test_security.py` | Guardrails contra prompt injection e detecção de PII |
| `tests/test_agent_tools.py` | Ferramentas do agente (`tools.py`) — mock do yfinance e LSTM |
| `tests/test_golden_set.py` | Golden set de avaliação — carga, pontuação e relatório RAGAS |
| `tests/conftest.py` | Fixtures compartilhadas (app client, dados de teste) |

**Coverage mínimo:** 60% (configurado em `pyproject.toml`).

> **Nota:** Os módulos `src/agent/rag_pipeline.py`, `src/agent/react_agent.py` e `src/agent/seed_rag.py` são excluídos da medição de cobertura pois dependem de `chromadb` e `litellm`, não instalados no ambiente de CI.

---

## Avaliação de Qualidade RAG (RAGAS)

O módulo `src/evaluation/` fornece duas camadas de avaliação para o agente RAG:

### Golden Set — avaliação determinística

O Golden Set é um conjunto fixo de pares (pergunta → resposta esperada) usado para medir a qualidade das respostas do agente de forma reproduzível e sem depender de um LLM juiz.

**Formato do arquivo** (`data/golden_set/golden_set.jsonl`):

```jsonl
{"id": "gs-001", "query": "Qual a tendência da ITUB4.SA?", "ticker": "ITUB4.SA", "expected_answer": "A tendência de curto prazo é de alta moderada...", "contexts": ["RSI neutro indica...", "SMA 20 como suporte..."]}
```

**Métricas calculadas:**

| Métrica | Cálculo | Intervalo |
|---|---|---|
| `exact_match` | Comparação literal normalizada | `true` / `false` |
| `token_overlap` | Interseção de tokens / tokens esperados | 0.0 – 1.0 |
| `similarity` | SequenceMatcher (difflib) | 0.0 – 1.0 |
| `score` | `0.5 × exact + 0.3 × overlap + 0.2 × similarity` | 0.0 – 1.0 |

**Uso programático:**

```python
from src.evaluation.golden_set import evaluate_golden_set

# agent_responses = {"gs-001": "resposta do agente", ...}
summary = evaluate_golden_set(agent_responses=agent_responses)
print(f"Avaliadas: {summary['evaluated']}")
print(f"Score médio: {summary['average_score']}")
print(f"Exact matches: {summary['exact_matches']}")
```

### RAGAS — avaliação com LLM juiz

O `src/evaluation/ragas_eval.py` usa a biblioteca [RAGAS](https://docs.ragas.io/) com **Ollama local** como LLM juiz, evitando dependência de APIs pagas.

**Métricas RAGAS disponíveis:**

| Métrica | Descrição |
|---|---|
| **Faithfulness** | A resposta gerada é fiel ao contexto recuperado? |
| **Answer Relevancy** | A resposta é relevante para a pergunta? |
| **Context Precision** | O contexto recuperado é preciso (sem ruído)? |
| **Context Recall** | O contexto recuperado cobre a resposta esperada? |

**Executar avaliação RAGAS** (requer Ollama rodando com `make setup-infra`):

```bash
# Ativar dependências de avaliação
pip install -e ".[llm]"

# Executar avaliação com dataset JSONL
python src/evaluation/ragas_eval.py --input data/golden_set/golden_set.jsonl \
                                    --output reports/ragas_results.csv \
                                    --model llama3 \
                                    --endpoint http://localhost:11434
```

**Exemplo de saída:**

```
📊 RAGAS Evaluation Results
────────────────────────────────────────
  faithfulness          : 0.81
  answer_relevancy      : 0.76
  context_precision     : 0.73
  context_recall        : 0.69
────────────────────────────────────────
Results saved to: reports/ragas_results.csv
```

> **Nota:** Para usar OpenAI ou Gemini como LLM juiz, passe `--model openai/gpt-4o-mini` e configure a chave em `.env`.

---

## Pipeline DVC (Versionamento de Dados)

O DVC garante reprodutibilidade do pipeline e versionamento de dados & modelos.

### Reproduzir o pipeline completo

```bash
make dvc-repro
```

Isso executa as etapas na ordem correta, usando cache quando possível:

```
data_download       →  data/raw/raw_stock_data.parquet
feature_engineering →  data/features/stock_features.parquet
feast_apply         →  data/feast/registry.db
train_model         →  data/models/ + metrics.json
evaluate_drift      →  reports/drift_report.html
```

### Sincronizar dados com o remote (MinIO/S3)

```bash
# Enviar novos dados/modelos para o remote
make dvc-push

# Baixar dados/modelos do remote (ex: novo desenvolvedor)
make dvc-pull
```

---

## Referência da API

### `GET /health`

Retorna o status da API e se o modelo está carregado.

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "healthy",
  "timestamp": "2026-05-01T10:00:00",
  "model_loaded": true
}
```

---

### `POST /predict`

Realiza predição de direção de preço para a próxima semana.

**Request:**
```json
{
  "ticker": "ITUB4.SA"
}
```

**Response:**
```json
{
  "ticker": "ITUB4.SA",
  "prediction": 1,
  "probability": 0.63,
  "timestamp": "2026-05-01T10:00:00",
  "model_version": "2"
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `ticker` | string | Símbolo do ativo (ex: `ITUB4.SA`, `PETR4.SA`) |
| `prediction` | int | `1` = alta esperada, `0` = queda esperada |
| `probability` | float | Probabilidade de alta (0.0 a 1.0) |
| `model_version` | string | Versão do modelo no MLflow Registry |

**Carga de features:** A API tenta buscar features do Redis (Feast online store). Se não disponível, calcula as features diretamente do yfinance.

---

### `POST /agent`

Consulta o agente LLM com RAG para análise financeira em linguagem natural.

**Request:**
```json
{
  "query": "Qual é a tendência da VALE3.SA?",
  "ticker": "VALE3.SA"
}
```

**Response:**
```json
{
  "query": "Qual é a tendência da VALE3.SA?",
  "response": "A VALE3.SA apresenta tendência de alta...",
  "sources": ["get_stock_price_history", "calculate_technical_indicators"],
  "timestamp": "2026-05-01T10:00:00"
}
```

---

### `GET /drift`

Retorna o relatório de data drift.

```bash
curl http://localhost:8000/drift
```

---

### `GET /metrics`

Métricas no formato Prometheus (scrapeáveis pelo Prometheus server).

```bash
curl http://localhost:8000/metrics
```

---

### `GET /features`

Lista as features usadas pelo modelo carregado e disponíveis no dataset.

```bash
curl http://localhost:8000/features
```

---

## Estrutura do Projeto

```
fiap_tech_challenge_fase5/
│
├── .env.example                    # Template de variáveis de ambiente
├── docker-compose.yml              # Infraestrutura local (todos os serviços)
├── dvc.yaml                        # Pipeline de dados versionado
├── Makefile                        # Atalhos para todos os comandos
├── pyproject.toml                  # Dependências e configuração de ferramentas
│
├── configs/                        # Configurações de serviços externos
│   ├── prometheus.yml              # Targets do Prometheus
│   └── grafana/                    # Dashboards e datasources pré-configurados
│
├── data/                           # Dados (gerenciados pelo DVC)
│   ├── raw/                        # Dados OHLCV brutos do yfinance
│   ├── features/                   # Features com indicadores técnicos
│   ├── models/                     # Modelos treinados (.keras)
│   ├── golden_set/                 # Golden Set JSONL para avaliação do agente
│   ├── chromadb/                   # Banco vetorial local (RAG)
│   ├── feast/                      # Registry do Feast
│   └── minio/                      # Artefatos MLflow (objetos simulados)
│
├── docs/                           # Documentação técnica
│   ├── MODEL_CARD.md               # Metadados, métricas e limitações do modelo
│   ├── SYSTEM_CARD.md              # Arquitetura e requisitos de sistema
│   ├── OWASP_MAPPING.md            # Mapeamento de vulnerabilidades LLM
│   ├── LGPD_PLAN.md                # Plano de conformidade com LGPD
│   ├── RED_TEAM_REPORT.md          # Relatório de testes adversariais
│   ├── AGENT_PREDICTION.md         # Documentação do agente com exemplos
│   └── DEBUGGING_AGENT.md          # Guia de debug do agente LLM
│
├── feast/                          # Definições do Feature Store
│   ├── feature_store.yaml          # Configuração (project, registry, online store)
│   └── feature_store_definitions.py # Entities, Feature Views e Feature Services
│
├── notebooks/                       # Análise exploratória
│   └── analise_exploratoria.ipynb
│
├── src/                            # Código-fonte principal
│   ├── config/
│   │   ├── settings.py             # Todas as variáveis de ambiente (Pydantic Settings)
│   │   └── storage.py              # Abstração de storage (fsspec — local/S3/GCS/Azure)
│   ├── data/
│   │   └── ingestion.py            # Download de dados via yfinance
│   ├── features/
│   │   ├── feature_engineering.py  # Cálculo dos 24 indicadores técnicos
│   │   └── feature_store_client.py # Client para Feast (online/offline)
│   ├── models/
│   │   ├── baseline.py             # Logistic Regression + Random Forest
│   │   └── train.py                # Treinamento LSTM + registro MLflow
│   ├── agent/
│   │   ├── react_agent.py          # Loop ReAct (Reasoning + Acting)
│   │   ├── tools.py                # Ferramentas do agente (yfinance, LSTM, indicadores)
│   │   ├── rag_pipeline.py         # Pipeline RAG com ChromaDB
│   │   └── seed_rag.py             # Popula ChromaDB com conhecimento técnico
│   ├── evaluation/
│   │   ├── golden_set.py           # Golden Set — avaliação determinística (exact match, overlap, similarity)
│   │   └── ragas_eval.py           # Avaliação RAGAS com Ollama (faithfulness, relevancy, precision, recall)
│   ├── monitoring/
│   │   ├── metrics.py              # Registro de métricas Prometheus
│   │   └── drift.py                # Détecção de drift com Evidently
│   ├── security/
│   │   ├── guardrails.py           # Validação de input/output do LLM
│   │   └── pii_detection.py        # Anonimização de PII com Presidio
│   └── serving/
│       ├── app.py                  # FastAPI — todos os endpoints
│       └── Dockerfile              # Container da API
│
└── tests/                          # Suite de testes
    ├── conftest.py                 # Fixtures compartilhadas
    ├── test_api.py                 # Testes de API
    ├── test_features.py            # Testes de feature engineering + Pandera schemas
    ├── test_models.py              # Testes de modelo LSTM e baselines
    ├── test_monitoring.py          # Testes de métricas e drift
    ├── test_security.py            # Testes de guardrails e PII
    ├── test_agent_tools.py         # Testes de ferramentas do agente
    └── test_golden_set.py          # Testes de avaliação Golden Set / RAGAS
```

---

## Cloud Providers Suportados

O projeto é cloud-agnostic por design. Para mudar o cloud provider, basta ajustar variáveis de ambiente — o código não muda.

### Como funciona a abstração

- **Storage**: `fsspec` detecta automaticamente o protocolo: `s3://`, `gs://`, `az://` ou caminho local
- **Compute**: Qualquer plataforma que rode containers Docker
- **Online Store**: Redis (gerenciado ou self-hosted)

### Configurações por provider

#### AWS (padrão)
```bash
STORAGE_BACKEND=s3
STORAGE_URI=s3://seu-bucket/data/
MLFLOW_ARTIFACT_ROOT=s3://mlflow-artifacts
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

#### Google Cloud (GCP)
```bash
STORAGE_BACKEND=gcs
STORAGE_URI=gs://seu-bucket/data/
MLFLOW_ARTIFACT_ROOT=gs://mlflow-artifacts
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

#### Azure
```bash
STORAGE_BACKEND=azure
STORAGE_URI=az://seu-container/data/
MLFLOW_ARTIFACT_ROOT=az://mlflow
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
```

#### Local (sem cloud)
```bash
STORAGE_BACKEND=local
STORAGE_URI=data/
MLFLOW_ARTIFACT_ROOT=s3://mlflow-artifacts    # MinIO local via Docker
AWS_ENDPOINT_URL=http://localhost:9000
```

---

## Segurança

O projeto implementa contramendidas para as principais vulnerabilidades OWASP Top 10 para LLMs:

| Risco | Implementação | Status |
|---|---|---|
| **LLM01 — Prompt Injection** | `src/security/guardrails.py` — regex para detectar padrões de injection | Mitigado |
| **LLM02 — Output Handling** | Sanitização e truncamento de outputs antes de retornar ao cliente | Mitigado |
| **LLM03 — Training Poisoning** | Dados de treino versionados com DVC, fonte confiável (yfinance) | Mitigado |
| **LLM04 — DoS por tokens** | Limite de `MAX_INPUT_TOKENS=1000` por requisição | Mitigado |
| **LLM06 — PII** | `src/security/pii_detection.py` — Microsoft Presidio anonimiza PII | Mitigado |

### Guardrails — Como funciona

Toda query enviada ao agente passa por validação antes de chegar ao LLM:

```python
# src/security/guardrails.py
validate_input(text)    # Detecta: injection, conteúdo tóxico, PII, token limit
validate_output(text)   # Trunca se > max_output_tokens, anonimiza PII residual
```

**Patterns detectados como prompt injection:**
- `ignore previous instructions`
- `you are now`
- `system: <comando>`
- `reset your instructions`
- `disregard all previous`

Ver relatório completo: [docs/OWASP_MAPPING.md](docs/OWASP_MAPPING.md) e [docs/RED_TEAM_REPORT.md](docs/RED_TEAM_REPORT.md).

---

## Solução de Problemas

### A API não inicia — `model_loaded: false`

**Cause:** Nenhum modelo foi treinado ou o MLflow não está rodando.

```bash
# Verifique se o MLflow está acessível
curl http://localhost:5001/health

# Se não estiver, suba a infra
make setup-infra

# Treine o modelo
make train

# Reinicie a API
make serve
```

---

### Erro ao treinar — `Connection refused` para o MLflow

**Cause:** O container do MLflow não está rodando.

```bash
docker compose ps | grep mlflow
# Se não aparecer "Up", suba novamente:
docker compose up -d mlflow minio
```

---

### Agente não responde — `LLM timeout` ou `503`

**Cause:** API key inválida ou LLM sobrecarregado.

```bash
# Verifique .env
cat .env | grep -E "LLM_MODEL|GOOGLE_API_KEY|OPENAI_API_KEY"

# Teste o LLM diretamente
python -c "
import litellm, os
from dotenv import load_dotenv
load_dotenv()
r = litellm.completion(model=os.getenv('LLM_MODEL'), messages=[{'role':'user','content':'hi'}])
print(r.choices[0].message.content)
"
```

Se usar Ollama, verifique se o modelo foi baixado:
```bash
docker exec ollama_llm ollama list
# Se vazio: docker exec ollama_llm ollama pull llama3
```

---

### Feast materialização falha — Redis recusando conexão

```bash
# Verifique Redis
docker compose ps | grep redis
redis-cli -h localhost -p 6379 ping    # deve retornar PONG

# Se necessário, reinicie
docker compose restart redis_feast
```

---

### Erro de importação — módulo não encontrado

```bash
# Verifique se o venv está ativo
which python    # deve apontar para .venv/bin/python

# Reinstale as dependências
pip install -e ".[llm,feast-support,monitoring,security]"
```

---

### ChromaDB retorna coleção vazia no agente

```bash
# Repopule a base de conhecimento RAG
make seed-rag

# Verifique o conteúdo
python -c "
import chromadb
client = chromadb.HttpClient(host='localhost', port=8002)
col = client.get_collection('market_knowledge')
print(col.count())    # deve ser > 0
"
```

---

### Teste de cobertura abaixo de 60%

```bash
# Rode apenas os testes de API (mais cobertos)
pytest tests/test_api.py tests/test_features.py -v --cov=src --cov-report=term-missing
```

---

## Documentação Adicional

| Documento | Conteúdo |
|---|---|
| [docs/MODEL_CARD.md](docs/MODEL_CARD.md) | Arquitetura do LSTM, métricas, dados usados, limitações e disclaimer financeiro |
| [docs/SYSTEM_CARD.md](docs/SYSTEM_CARD.md) | Componentes do sistema, fluxo de dados, requisitos de hardware, latências alvo |
| [docs/OWASP_MAPPING.md](docs/OWASP_MAPPING.md) | Mapeamento das 10 ameaças OWASP LLM com status de mitigação |
| [docs/LGPD_PLAN.md](docs/LGPD_PLAN.md) | Conformidade com LGPD: base legal, política de retenção, direitos dos titulares |
| [docs/RED_TEAM_REPORT.md](docs/RED_TEAM_REPORT.md) | Relatório de 8h de red team (OWASP LLM + MITRE ATLAS), 5 findings |
| [docs/AGENT_PREDICTION.md](docs/AGENT_PREDICTION.md) | Exemplos detalhados de uso do agente com respostas completas |
| [docs/DEBUGGING_AGENT.md](docs/DEBUGGING_AGENT.md) | Guia de debug do agente — como identificar alucinações vs. respostas corretas |
| [SCHEMA_VALIDATION_SETUP.md](SCHEMA_VALIDATION_SETUP.md) | Guia de configuração e uso do Pandera para validação de schemas no pipeline |

---

## Referências e Links Úteis

- [MLflow Documentation](https://mlflow.org/docs/latest/)
- [Feast Documentation](https://docs.feast.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LiteLLM — 100+ LLM providers](https://docs.litellm.ai/)
- [Evidently AI — Drift Detection](https://docs.evidentlyai.com/)
- [RAGAS — RAG Evaluation Framework](https://docs.ragas.io/)
- [Pandera — Data Validation](https://pandera.readthedocs.io/)
- [OWASP Top 10 for LLMs](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Presidio — PII Detection](https://microsoft.github.io/presidio/)

---

## Licença

MIT License — consulte [LICENSE](LICENSE) para detalhes.

---

> **Disclaimer:** Este projeto é um exercício acadêmico. As predições geradas pelo modelo **não constituem recomendação de investimento**. Decisões financeiras devem ser tomadas com orientação profissional qualificada.
