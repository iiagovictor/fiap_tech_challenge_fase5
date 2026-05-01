# 🚀 Como Executar o Projeto

Guia completo para rodar o **fiap_tech_challenge_fase5** do zero.

---

## 📋 Pré-requisitos

### 1. **Instalar Docker Desktop** (obrigatório)

```bash
# macOS - baixe do site oficial:
# https://www.docker.com/products/docker-desktop

# Ou via Homebrew:
brew install --cask docker
```

**IMPORTANTE**: Após instalar, **abra o Docker Desktop** e aguarde até aparecer "Docker is running" na barra de menu.

### 2. **Verificar Python 3.12+**

```bash
python --version
# Deve mostrar: Python 3.12.13
```

---

## ⚡ Início Rápido

### **Passo 1: Instalar Dependências Python**

```bash
# Ativar ambiente virtual (já existente)
source .venv/bin/activate

# Instalar dependências core (ML + API)
make install

# OU: Instalar tudo (pode demorar 5-10 min)
make install-full
```

### **Passo 2: Verificar Instalação**

```bash
python -c "import pandas, numpy, sklearn, tensorflow, mlflow, fastapi; print('✅ Core OK')"
```

### **Passo 3: Iniciar Infraestrutura Docker**

```bash
# Subir todos os serviços (MLflow, Redis, Prometheus, Grafana, etc.)
make setup-infra
```

Isso irá subir:
- 🔬 **MLflow** → http://localhost:5001
- 📦 **MinIO** → http://localhost:9001 (minioadmin/minioadmin123)
- 🗄️ **Redis** → localhost:6379
- 🗄️ **ChromaDB** → http://localhost:8002
- 📈 **Prometheus** → http://localhost:9090
- 📊 **Grafana** → http://localhost:3000 (admin/admin)

Aguarde ~15 segundos para os serviços iniciarem.

### **Passo 4: Configurar LLM (Opcional)**

Se quiser usar o agente LLM com Google Gemini:

```bash
# Edite o arquivo .env
nano .env

# Adicione ou descomente:
LLM_MODEL=gemini/gemini-2.0-flash-exp
GOOGLE_API_KEY=sua-chave-api-aqui

# Popule o conhecimento base (RAG)
make seed-rag
```

**Obter Google API Key:**
1. Acesse: https://makersuite.google.com/app/apikey
2. Crie uma chave de API
3. Cole no `.env`

### **Passo 5: Baixar e Processar Dados**

```bash
# Baixar dados históricos do Yahoo Finance (ITUB4, PETR4, VALE3, etc.)
make data-download

# Gerar features técnicas (RSI, MACD, Bollinger Bands)
make data-features
```

### **Passo 6: Treinar Modelo LSTM**

```bash
# Treinar e registrar no MLflow
make train

# Ver experimento: http://localhost:5001
```

### **Passo 7: Iniciar API**

```bash
# Iniciar FastAPI na porta 8000
make serve
```

A API estará disponível em: **http://localhost:8000**

Documentação interativa: **http://localhost:8000/docs**

---

## 🧪 Testando a API

### **Health Check**
```bash
curl http://localhost:8000/health
```

**Resposta esperada:**
```json
{
  "status": "healthy",
  "timestamp": "2026-04-26T14:30:00",
  "model_loaded": true
}
```

### **Predição LSTM**
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"ticker": "ITUB4.SA"}'
```

**Resposta esperada:**
```json
{
  "ticker": "ITUB4.SA",
  "prediction": 1,
  "probability": 0.67,
  "signal": "buy",
  "timestamp": "2026-04-26T14:30:00"
}
```

### **Agente LLM com RAG** (requer `make install-llm` + Google API Key)
```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "Qual a cotação da ITUB4.SA?"}'
```

**Perguntas disponíveis:**
- "Quais os tickers disponíveis?"
- "Qual a cotação da PETR4.SA?"
- "Comparar o desempenho das ações"
- "Recomendar investimento no ITUB4.SA"

**Fallback automático:**
- Se Gemini falhar (503), tenta `gemini-1.5-flash`
- Se LLM indisponível, retorna dados diretos do yfinance

### **Drift Detection**
```bash
curl http://localhost:8000/drift
```

### **Métricas Prometheus**
```bash
curl http://localhost:8000/metrics
```

---

## 📊 Acessando Dashboards

### **MLflow UI** (Tracking de Modelos)
- URL: http://localhost:5001
- Ver experimentos, métricas de treino, modelos registrados

### **Grafana** (Monitoramento)
- URL: http://localhost:3000
- Login: `admin` / `admin`
- Dashboard: "API Overview" (já provisionado)

### **MinIO Console** (Storage S3)
- URL: http://localhost:9001
- Login: `minioadmin` / `minioadmin123`
- Buckets: mlflow-artifacts, data

### **Prometheus** (Métricas)
- URL: http://localhost:9090
- Query: `api_requests_total`, `api_request_duration_seconds`

---

## 🎯 Fluxos de Trabalho Comuns

### **1. Pipeline Completo (Do Zero)**
```bash
# 1. Instalar
make install

# 2. Infraestrutura
make setup-infra

# 3. Dados
make data-download
make data-features

# 4. Treinar
make train

# 5. Servir
make serve
```

### **2. Adicionar Feature Store (Feast)**
```bash
# Instalar Feast
make install-feast

# Aplicar definições
make feast-apply

# Materializar features no Redis
make feast-materialize

# UI do Feast (porta 8888)
make feast-ui
```

### **3. Adicionar LLM/RAG (Agente)**
```bash
# Instalar dependências LLM
make install-llm

# Iniciar API com agente
make serve

# Testar endpoint /agent
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare PETR4 e VALE3"}'
```

### **4. Rodar Testes**
```bash
# Todos os testes
make test

# Com cobertura HTML
make test-cov
# Ver: htmlcov/index.html

# Smoke test rápido
make test-smoke
```

### **5. Monitorar Drift**
```bash
# Instalar Evidently
pip install -e ".[monitoring]"

# Endpoint de drift
curl http://localhost:8000/drift
```

---

## 🗂️ Estrutura de Comandos Make

| Comando | Descrição |
|---------|-----------|
| `make help` | Lista todos os comandos disponíveis |
| `make install` | Instala core (ML + API) |
| `make install-full` | Instala tudo (LLM + Feast + Security) |
| `make install-llm` | Adiciona LLM/RAG (LiteLLM + ChromaDB) |
| `make install-feast` | Adiciona Feature Store (Feast + Redis) |
| `make setup-infra` | Sobe Docker (MLflow, Redis, Prometheus, etc.) |
| `make teardown-infra` | Para e remove todos os containers |
| `make data-download` | Baixa dados do Yahoo Finance |
| `make data-features` | Gera features técnicas |
| `make train` | Treina modelo LSTM |
| `make serve` | Inicia API FastAPI (porta 8000) |
| `make test` | Executa testes unitários |
| `make test-cov` | Testes com relatório de cobertura |

---

## 🐛 Troubleshooting

### **Erro: `docker: command not found`**
→ Instale o Docker Desktop e inicie o aplicativo

### **Erro: `make setup-infra` falha**
→ Certifique-se que o Docker Desktop está rodando (ícone na barra de menu)

### **Erro: `No module named 'tensorflow'`**
→ Rode `make install` dentro do `.venv`:
```bash
source .venv/bin/activate
make install
```

### **Erro: `No module named 'litellm'`**
→ Instale dependências LLM: `make install-llm`

### **Erro: `No module named 'feast'`**
→ Instale Feature Store: `make install-feast`

### **Erro: `resolution-too-deep`**
→ Use instalação modular (não `install-full`):
```bash
make install
make install-llm
make install-feast
```

### **Porta 8000 já em uso**
→ Mude a porta no comando serve:
```bash
uvicorn src.serving.app:app --host 0.0.0.0 --port 8080 --reload
```

### **MLflow não carrega modelo**
→ Verifique se treinou primeiro: `make train`

### **Docker out of memory**
→ Aumente memória no Docker Desktop: Preferences → Resources → Memory (mínimo 4GB)

---

## 🧹 Limpeza

```bash
# Parar infraestrutura Docker
make teardown-infra

# Limpar cache Python
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Remover ambiente virtual (se quiser recriar)
rm -rf .venv
```

---

## 🚀 Deploy em Produção

### **AWS (ECS + ECR)**
```bash
# 1. Build imagem Docker
docker build -t fiap-tc-fase5 -f src/serving/Dockerfile .

# 2. Push para ECR (configurar AWS CLI primeiro)
make deploy-aws

# Ver detalhes no docs/SYSTEM_CARD.md
```

### **Configuração Cloud**
Edite `.env` para usar S3/GCS/Azure:

```bash
# AWS S3
STORAGE_BACKEND=s3
STORAGE_URI=s3://my-bucket/fiap-tc-fase5
MLFLOW_TRACKING_URI=http://mlflow-server.mydomain.com

# Google Cloud Storage
STORAGE_BACKEND=gcs
STORAGE_URI=gs://my-bucket/fiap-tc-fase5

# Azure Blob
STORAGE_BACKEND=azure
STORAGE_URI=az://my-container/fiap-tc-fase5
```

---

## 📚 Documentação Adicional

- **Instalação**: [INSTALL.md](INSTALL.md)
- **Arquitetura**: [README.md](README.md)
- **Model Card**: [docs/MODEL_CARD.md](docs/MODEL_CARD.md)
- **System Card**: [docs/SYSTEM_CARD.md](docs/SYSTEM_CARD.md)
- **LGPD Compliance**: [docs/LGPD_PLAN.md](docs/LGPD_PLAN.md)
- **Security (OWASP)**: [docs/OWASP_MAPPING.md](docs/OWASP_MAPPING.md)
- **Red Team Report**: [docs/RED_TEAM_REPORT.md](docs/RED_TEAM_REPORT.md)

---

## 💡 Próximos Passos

1. ✅ **Executar pipeline básico** (data → features → train → serve)
2. ✅ **Testar API** (health, predict, drift)
3. ✅ **Visualizar no MLflow** (http://localhost:5001)
4. 📊 **Criar dashboards Grafana** personalizados
5. 🤖 **Adicionar LLM** para agente inteligente
6. 🗄️ **Configurar Feast** para features online
7. 🚀 **Deploy AWS/GCP** para produção
