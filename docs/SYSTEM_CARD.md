# System Card: MLOps Platform for Stock Prediction

## System Overview

**System Name:** FIAP Tech Challenge Fase 5 - Stock Prediction MLOps Platform  
**Version:** 1.0.0  
**Date:** January 2025  
**Purpose:** Cloud-agnostic MLOps platform for stock price direction prediction with LLM-powered financial analysis agent

### Architecture

The system implements a complete MLOps pipeline following ML maturity level 2+ (automated training, continuous integration, monitoring).

**Components:**
1. **Data Ingestion**: Yahoo Finance → Feature Engineering → Feast Feature Store
2. **Model Training**: LSTM with MLflow tracking → Model Registry → Champion-Challenger
3. **Serving**: FastAPI → Online Predictions + LLM Agent
4. **Monitoring**: Prometheus + Grafana + Evidently Drift Detection
5. **Infrastructure**: Docker Compose (local) + Terraform (AWS ECS)

### Cloud-Agnostic Design

**Storage Abstraction (fsspec):**
- Local: `data/`
- AWS S3: `s3://bucket/`
- GCP GCS: `gs://bucket/`
- Azure Blob: `az://container/`

**LLM Abstraction (LiteLLM):**
- Google Gemini: `gemini/gemini-2.0-flash-exp` (default)
- Google Gemini Fallback: `gemini/gemini-1.5-flash` (if 503)
- Ollama (local): `ollama/llama3`
- AWS Bedrock: `bedrock/anthropic.claude-3-sonnet`
- Azure OpenAI: `azure/gpt-4o`
- OpenAI: `gpt-4o`

**Fallback Strategy:**
1. Primary LLM (Gemini 2.0)
2. Fallback LLM (Gemini 1.5 Flash on 503)
3. Direct tools (yfinance) if LLM unavailable

## System Behavior

### Data Flow

```
1. Data Ingestion
   yfinance → raw/{ticker}_data.parquet
   
2. Feature Engineering
   raw/ → feature_engineering.py → features/stock_features.parquet
   
3. Feature Store
   features/ → Feast (Redis online + Parquet offline)
   
4. Model Training
   features/ → LSTM train.py → MLflow → models/
   
5. Serving
   Feast online → FastAPI /predict
   LLM Agent → /agent (RAG + Tools)
   
6. Monitoring
   Predictions → Prometheus metrics
   features/ → Evidently drift → reports/
```

### Endpoints

**API Server (FastAPI):**
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics
- `POST /predict` - LSTM prediction
  - Input: `{"ticker": "ITUB4.SA", "timestamp": "2025-01-15T10:00:00Z"}`
  - Output: `{"prediction": 1, "probability": 0.65}`
- `POST /agent` - LLM agent query
  - Input: `{"query": "What's the technical analysis for ITUB4?", "ticker": "ITUB4.SA"}`
  - Output: `{"response": "...", "sources": ["LLM Agent", "Yahoo Finance"]}`
  - Fallback: Returns yfinance data if LLM unavailable
  - Output: `{"response": "...", "sources": [...]}`
- `GET /drift` - Drift detection report

### LLM Agent Capabilities

**ReAct Pattern:**
1. **Thought**: Reason about the query
2. **Action**: Execute tool (price history, technical indicators, compare stocks)
3. **Observation**: Analyze result
4. **Answer**: Provide final response

**Tools:**
- `get_stock_price_history(ticker, period)` - Historical prices
- `calculate_technical_indicators(ticker, period)` - RSI, MACD, MAs
- `compare_stocks(tickers, period)` - Compare multiple stocks

**RAG (Retrieval Augmented Generation):**
- ChromaDB vector store with market knowledge
- Semantic search for context retrieval
- Sources: Technical analysis guides, market concepts

## System Requirements

### Hardware
- **Minimum**: 4 CPU cores, 8 GB RAM, 20 GB disk
- **Recommended**: 8 CPU cores, 16 GB RAM, 50 GB disk
- **GPU**: Optional (speeds up LSTM training)

### Software
- Python 3.12+
- Docker 24.0+ (for infrastructure)
- Redis 7.2+ (Feast online store)
- Ollama (optional, for local LLM)

### Cloud Resources (AWS Example)
- **ECS Fargate**: 2 vCPU, 4 GB RAM per task
- **S3**: ~10 GB for models and data
- **Redis ElastiCache**: t3.micro (for Feast)
- **ALB**: Application Load Balancer
- **API Gateway**: Optional (REST API)

## User Interaction

### Primary Users
1. **Data Scientists**: Train models, analyze features, evaluate performance
2. **ML Engineers**: Deploy models, configure infrastructure, monitor drift
3. **Financial Analysts**: Query agent, interpret predictions
4. **DevOps Engineers**: Manage infrastructure, CI/CD, scaling

### User Flows

**Data Scientist:**
```bash
# 1. Download and prepare data
make data-download
make data-features

# 2. Apply Feast feature store
make feast-apply

# 3. Seed RAG knowledge base (optional)
make seed-rag

# 4. Train model
make train

# 5. Evaluate
make test
```

**Financial Analyst:**
```bash
# Query the agent
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "Should I buy ITUB4 today?"}'
```

**ML Engineer:**
```bash
# Monitor drift
make drift-check

# Deploy to AWS
make deploy-aws
```

## Risks and Mitigations

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Model drift | Degraded accuracy | Weekly drift monitoring, monthly retraining |
| API downtime | Service unavailable | ECS auto-scaling, health checks, ALB |
| Data source failure (yfinance) | No new data | Fallback to cached data, alerting |
| LLM hallucination | Incorrect advice | RAG grounding, confidence thresholds |

### Security Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| PII leakage | Privacy violation | Presidio PII detection, anonymization |
| Prompt injection | System compromise | Input validation, guardrails |
| API abuse | Resource exhaustion | Rate limiting, token limits |
| Credential exposure | Unauthorized access | Secret management (AWS Secrets Manager) |

### Financial Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Incorrect predictions | Financial loss | Disclaimer, human-in-the-loop |
| Over-reliance on model | Poor decisions | Model card transparency, confidence scores |
| Market manipulation | Regulatory issues | Audit logs, explainability |

## Performance

### Latency Targets
- `/predict` endpoint: < 200ms (P95)
- `/agent` endpoint: < 5s (P95, depends on LLM)
- Feature retrieval (Feast): < 50ms (P95)

### Throughput
- **Prediction API**: 100 req/s (with horizontal scaling)
- **Agent API**: 10 req/s (LLM bottleneck)
- **Training**: ~5 minutes per model (CPU)

### Accuracy
- **LSTM Model**: ROC-AUC ~0.50-0.55 (baseline: 0.46-0.48)
- **Agent Response**: Subjective (evaluated via RAGAS, LLM-as-judge)

## Monitoring and Alerting

### Metrics Collected

**Infrastructure:**
- CPU/Memory utilization
- Request rate, latency (P50, P95, P99)
- Error rate (4xx, 5xx)

**Model:**
- Prediction count
- Prediction confidence distribution
- Feature drift score
- Model version in use

**LLM:**
- Request latency
- Token usage (input/output)
- Tool call frequency
- Guardrail violations

### Alerts

| Condition | Severity | Action |
|-----------|----------|--------|
| Drift score > 0.15 | Warning | Review data, consider retraining |
| Drift score > 0.30 | Critical | Retrain immediately |
| API error rate > 5% | Critical | Rollback, investigate |
| P95 latency > 1s | Warning | Scale up resources |
| PII detections > 10/hour | Warning | Review logs, update filters |

### Dashboards

**Grafana:**
- API Overview: Request rate, latency, predictions
- Model Performance: Accuracy trends, drift scores
- Infrastructure: CPU, memory, disk usage

## Maintenance

### Regular Tasks
- **Daily**: Check API health, review error logs
- **Weekly**: Evaluate prediction accuracy, drift report
- **Monthly**: Retrain model, update features
- **Quarterly**: Review architecture, update dependencies

### Incident Response
1. **Detect**: Prometheus alerts → PagerDuty/Slack
2. **Diagnose**: Check Grafana dashboards, logs (CloudWatch)
3. **Mitigate**: Rollback to previous model version, scale resources
4. **Resolve**: Fix root cause, deploy patch
5. **Post-mortem**: Document incident, update runbooks

## Compliance and Governance

### Data Privacy (LGPD)
- PII detection and anonymization (Presidio)
- Data retention policy: 2 years
- User consent not required (public market data)
- Access logs maintained for auditing

### Model Governance
- **MLflow tags**: `stage`, `owner`, `data_version`
- **Champion-Challenger**: Compare new models before promotion
- **Explainability**: Feature importance, SHAP (future)
- **Audit trail**: All predictions logged with metadata

### Security (OWASP)
- Input validation (SQL injection, XSS prevention)
- Rate limiting (API Gateway)
- Authentication (optional: OAuth2, API keys)
- TLS encryption in production

## Deployment

### Local Development
```bash
# Start infrastructure
make setup-infra

# Run pipeline
make data-pipeline
make train
make serve
```

### AWS Deployment
```bash
# Configure Terraform
cd terraform/aws
terraform init

# Deploy
terraform apply

# Push Docker image
make docker-build-push

# Update ECS service
aws ecs update-service --cluster fiap-tc --service api --force-new-deployment
```

### CI/CD Pipeline
- **GitHub Actions**: Lint, test, build on push
- **Deployment**: Auto-deploy to staging on `develop`, manual promote to production

## Future Enhancements

### Short-term (3 months)
- [ ] Add A/B testing framework
- [ ] Implement SHAP explainability
- [ ] Expand to more tickers (Nasdaq, NYSE)
- [ ] Add sentiment analysis from news

### Long-term (6-12 months)
- [ ] Multi-model ensemble (LSTM + Transformer)
- [ ] Real-time streaming predictions (Kafka)
- [ ] Portfolio optimization tool
- [ ] Mobile app integration

## References

- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)
- [Feast Feature Store](https://docs.feast.dev/)
- [Evidently Monitoring](https://docs.evidentlyai.com/)
- [LiteLLM](https://docs.litellm.ai/)
- [OWASP ML Security](https://owasp.org/www-project-machine-learning-security-top-10/)

---

**Version:** 1.0.0  
**Last Updated:** January 2025  
**Maintainers:** FIAP Tech Challenge Team
