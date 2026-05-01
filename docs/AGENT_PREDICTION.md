# 🔮 Predição de Valorização com Agente LLM

## Nova Funcionalidade: Integração do Modelo LSTM com o Agente

O agente ReAct agora tem acesso direto ao modelo LSTM através da ferramenta `predict_stock_direction`, permitindo responder perguntas sobre probabilidade de valorização de ações.

---

## 📊 Como Funciona

Quando você faz uma pergunta ao agente como:
- "Qual é a probabilidade do ITUB4.SA valorizar amanhã?"
- "PETR4.SA vai subir no próximo pregão?"
- "Qual a chance de valorização do VALE3.SA?"

O agente **automaticamente escolhe** a ferramenta `predict_stock_direction` que:

1. **Tenta usar o modelo LSTM** (via endpoint `/predict`)
   - Retorna predição baseada em análise LSTM treinado
   - Probabilidades precisas de valorização/desvalorização
   
2. **Fallback para Indicadores Técnicos** (se modelo indisponível)
   - Usa RSI, Médias Móveis e outros indicadores
   - Gera predição baseada em análise técnica

---

## 🎯 Exemplos de Uso

### Exemplo 1: Pergunta Direta sobre Probabilidade

**Request:**
```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Qual é a probabilidade do ticker ITUB4.SA valorizar no próximo dia útil?",
    "ticker": "ITUB4.SA"
  }'
```

**Response Esperada (com modelo LSTM):**
```json
{
  "query": "Qual é a probabilidade do ticker ITUB4.SA valorizar no próximo dia útil?",
  "response": "Com base no modelo LSTM, a probabilidade de ITUB4.SA valorizar no próximo dia útil é de 68.5%. O modelo indica COMPRA com confiança alta, sugerindo tendência de alta no curto prazo.",
  "sources": [
    "predict_stock_direction(ticker='ITUB4.SA')",
    "RAG Knowledge Base"
  ],
  "timestamp": "2026-05-01T14:30:00"
}
```

**Response Esperada (fallback - indicadores técnicos):**
```json
{
  "query": "Qual é a probabilidade do ticker ITUB4.SA valorizar no próximo dia útil?",
  "response": "Baseado em análise técnica (RSI: 31.34, preço abaixo das médias móveis SMA20 e SMA50), a probabilidade de desvalorização é estimada em 100%. O RSI está próximo da zona de sobrevenda (below 30), o que pode indicar reversão de tendência em breve. Recomendação: NEUTRO - Incerteza alta, aguardar melhores sinais.",
  "sources": [
    "predict_stock_direction(ticker='ITUB4.SA')",
    "calculate_technical_indicators(ticker='ITUB4.SA')"
  ],
  "timestamp": "2026-05-01T14:30:00"
}
```

---

### Exemplo 2: Pergunta Casual

**Request:**
```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{
    "query": "PETR4.SA vai subir amanhã?",
    "ticker": "PETR4.SA"
  }'
```

**Response:**
```json
{
  "query": "PETR4.SA vai subir amanhã?",
  "response": "Segundo o modelo LSTM, há 72% de probabilidade de PETR4.SA valorizar amanhã. Esta é uma previsão com confiança moderada-alta, indicando tendência de alta. Recomendação: COMPRA",
  "sources": [
    "predict_stock_direction(ticker='PETR4.SA')"
  ],
  "timestamp": "2026-05-01T14:35:00"
}
```

---

### Exemplo 3: Comparação com Análise Técnica

**Request:**
```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Me dê uma análise completa do VALE3.SA: preço atual, indicadores técnicos e probabilidade de valorização",
    "ticker": "VALE3.SA"
  }'
```

**Response:**
```json
{
  "query": "Me dê uma análise completa do VALE3.SA...",
  "response": "Análise Completa de VALE3.SA:\n\n📊 Preço Atual: R$ 65.42\n\n🔧 Indicadores Técnicos:\n- RSI (14): 58.23 (neutro)\n- SMA20: R$ 64.10 (preço acima - sinal de alta)\n- SMA50: R$ 62.50 (preço acima - tendência de alta)\n- MACD: +0.52 (momento positivo)\n\n🔮 Predição do Modelo:\n- Probabilidade de Valorização: 65%\n- Probabilidade de Desvalorização: 35%\n- Confiança: Moderada\n- Recomendação: COMPRA - tendência positiva com suporte técnico\n\nO modelo LSTM indica perspectiva positiva para o curto prazo, confirmada pelos indicadores técnicos que mostram preço acima das principais médias móveis.",
  "sources": [
    "get_stock_price_history(ticker='VALE3.SA')",
    "calculate_technical_indicators(ticker='VALE3.SA')",
    "predict_stock_direction(ticker='VALE3.SA')"
  ],
  "timestamp": "2026-05-01T14:40:00"
}
```

---

## 🛠️ Ferramentas Disponíveis

O agente tem 4 ferramentas principais:

| Ferramenta | Descrição | Quando Usar |
|------------|-----------|-------------|
| `predict_stock_direction` | ✨ **NOVO!** Predição LSTM ou técnica | Perguntas sobre "probabilidade", "vai subir", "previsão" |
| `get_stock_price_history` | Histórico de preços | Perguntas sobre "cotação", "preço", "histórico" |
| `calculate_technical_indicators` | RSI, MACD, Médias Móveis | Perguntas sobre "indicadores", "RSI", "análise técnica" |
| `compare_stocks` | Comparação de ações | Perguntas "comparar", "melhor ação", "performance" |

---

## 🔄 Fluxo de Fallback

```
┌─────────────────────────────────────┐
│  Pergunta sobre Valorização         │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Ferramenta: predict_stock_direction│
└──────────────┬──────────────────────┘
               │
               ▼
    ┌──────────┴──────────┐
    │                     │
    ▼                     ▼
┌─────────┐         ┌──────────┐
│ Modelo  │         │ Modelo   │
│ LSTM OK │         │ LSTM N/A │
└────┬────┘         └────┬─────┘
     │                   │
     │                   ▼
     │          ┌─────────────────┐
     │          │ Indicadores     │
     │          │ Técnicos        │
     │          │ (Fallback)      │
     │          └────┬────────────┘
     │               │
     ▼               ▼
┌─────────────────────────┐
│  Resposta com Predição  │
│  + Recomendação         │
└─────────────────────────┘
```

---

## 🧪 Testando Localmente

### 1. Teste da Ferramenta Direta

```python
from src.agent.tools import predict_stock_direction
import json

result = predict_stock_direction("ITUB4.SA")
print(json.dumps(result, indent=2))
```

### 2. Teste do Agente via Script

```bash
python test_agent_prediction.py
```

### 3. Teste via API

```bash
# Certifique-se que a API está rodando
make serve

# Em outro terminal
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Qual a probabilidade do ITUB4.SA valorizar?",
    "ticker": "ITUB4.SA"
  }' | jq
```

---

## ✅ Benefícios da Integração

1. **Decisões Data-Driven**: Predições baseadas em modelo treinado com dados históricos
2. **Interação Natural**: Pergunte em linguagem natural, sem precisar chamar endpoints diretamente
3. **Contexto Completo**: Agente combina predição com análise técnica e histórico
4. **Fallback Robusto**: Sempre retorna resposta útil, mesmo sem modelo
5. **Recomendações Claras**: Recomendações de COMPRA/VENDA/NEUTRO baseadas em probabilidades

---

## 📝 Notas Técnicas

- **Timeout do Modelo**: Se o modelo demorar >5s, automaticamente usa fallback de indicadores técnicos
- **Cache**: Recomenda-se implementar cache para consultas frequentes ao mesmo ticker
- **Precisão**: Precisão do modelo depende dos dados de treinamento e recência do modelo
- **Disclaimer**: Predições são para fins educacionais, não constituem recomendação financeira

---

## 🚀 Próximos Passos

- [ ] Adicionar confiança do modelo na resposta
- [ ] Implementar cache de predições
- [ ] Comparar predição LSTM vs indicadores técnicos
- [ ] Adicionar histórico de acurácia do modelo
- [ ] Integrar com alertas de volatilidade
