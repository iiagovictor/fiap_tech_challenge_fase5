# 🔍 GUIA DE DEBUG: Por que o Agente Não Usa Ferramentas?

## 🐛 Problema Identificado

O agente estava retornando respostas diretas **sem usar as ferramentas**, gerando números "alucinados" em vez de consultar o modelo LSTM real.

**Exemplo do problema:**
```json
{
  "sources": ["LLM Agent"],  // ❌ Nenhuma ferramenta usada!
  "response": "A probabilidade é de 65%"  // ❌ Número inventado
}
```

---

## ✅ Correções Aplicadas

### 1. **System Prompt Melhorado** ([react_agent.py](../src/agent/react_agent.py))

**Antes:**
```python
"You follow the ReAct pattern..."
"Format your responses as: ..."
```

**Depois:**
```python
"""
CRITICAL RULES:
1. You MUST use tools to get real data - do NOT make up numbers
2. For prediction questions, you MUST use predict_stock_direction
3. Only provide Answer after executing tools

EXAMPLE 1 - Prediction Question:
User: "Qual é a probabilidade do ITUB4.SA valorizar?"
Thought: This is a prediction question, I must use predict_stock_direction
Action: predict_stock_direction(ticker="ITUB4.SA")
[Wait for Observation]
Answer: De acordo com o modelo LSTM, a probabilidade é X%
"""
```

**Mudanças:**
- ✅ Regras OBRIGATÓRIAS em MAIÚSCULAS
- ✅ Exemplos concretos de uso correto
- ✅ Instrução explícita: "MUST use tools, do NOT make up numbers"
- ✅ Exemplo específico para perguntas de predição

### 2. **Logs Detalhados** ([react_agent.py](../src/agent/react_agent.py))

```python
logger.info(f"🔄 Iteration {iteration + 1}/{self.max_iterations}")
logger.debug(f"📝 LLM Response:\n{response}")
logger.info(f"🔧 Executing tool: {tool_name} with params {params}")
logger.info(f"✅ Agent provided final answer after {iteration + 1} iteration(s)")
logger.info(f"🔧 Tools called: {len(tool_calls)}")
```

**Agora você pode ver:**
- Cada iteração do agente
- Resposta bruta do LLM
- Quais ferramentas foram executadas
- Quantas ferramentas foram usadas no total

### 3. **Sources Corretas** ([app.py](../src/serving/app.py))

**Antes:**
```python
sources = ["LLM Agent"]  # Sempre igual
if result.get("tool_calls"):
    sources.extend([call["tool"] for call in result["tool_calls"]])
```

**Depois:**
```python
if result.get("tool_calls") and len(result["tool_calls"]) > 0:
    sources = [f"{call['tool']}(ticker={call['params'].get('ticker')})" 
               for call in result["tool_calls"]]
    logger.info(f"✅ Agent used {len(tool_names)} tool(s)")
else:
    sources = ["LLM Agent (no tools used)"]
    logger.warning("⚠️ Agent provided answer without using tools - may be hallucinated!")
```

**Agora:**
- ✅ Sources mostra exatamente quais ferramentas foram usadas
- ✅ Se nenhuma ferramenta foi usada, avisa explicitamente
- ✅ Logs mostram warning quando resposta pode ser "alucinada"

---

## 🧪 Como Testar

### Opção 1: Teste Manual

1. **Reinicie o servidor:**
   ```bash
   make stop-serve
   make serve
   ```

2. **Em outro terminal, faça a query:**
   ```bash
   curl -X POST http://localhost:8000/agent \
     -H "Content-Type: application/json" \
     -d '{
       "query": "Qual é a probabilidade do ticker ITUB4.SA valorizar no próximo dia útil?",
       "ticker": "ITUB4.SA"
     }' | jq
   ```

3. **Verifique os logs do servidor:**
   ```
   🔄 Iteration 1/5
   🔧 Executing tool: predict_stock_direction with params {'ticker': 'ITUB4.SA'}
   ✅ Tool predict_stock_direction executed successfully
   🔄 Iteration 2/5
   ✅ Agent provided final answer after 2 iteration(s)
   🔧 Tools called: 1
   ```

### Opção 2: Script Automatizado

```bash
chmod +x test_agent_detailed.sh
./test_agent_detailed.sh
```

---

## 🔍 O Que Procurar nos Logs

### ✅ **Comportamento CORRETO:**
```
INFO:     🔄 Iteration 1/5
INFO:     🔧 Executing tool: predict_stock_direction with params {'ticker': 'ITUB4.SA'}
INFO:     ✅ Tool predict_stock_direction executed successfully
INFO:     🔄 Iteration 2/5
INFO:     ✅ Agent provided final answer after 2 iteration(s)
INFO:     🔧 Tools called: 1
```

**Response esperada:**
```json
{
  "sources": [
    "predict_stock_direction(ticker=ITUB4.SA)"
  ],
  "response": "De acordo com o modelo LSTM, a probabilidade de ITUB4.SA valorizar..."
}
```

### ❌ **Comportamento ERRADO:**
```
INFO:     🔄 Iteration 1/5
WARNING:  ⚠️ No action found in response
INFO:     ✅ Agent provided final answer after 1 iteration(s)
INFO:     🔧 Tools called: 0
WARNING:  ⚠️ Agent provided answer without using tools - may be hallucinated!
```

**Response problemática:**
```json
{
  "sources": [
    "LLM Agent (no tools used)"
  ],
  "response": "A probabilidade é de 65%"  // ❌ Número inventado
}
```

---

## 🐛 Se Ainda Não Funcionar

### Problema 1: LLM Não Segue Formato

**Causa:** Gemini pode não seguir instruções de formato perfeitamente.

**Solução:**
1. Adicionar mais exemplos ao system prompt
2. Reduzir `temperature` para 0.0 (mais determinístico)
3. Considerar usar modelo com melhor instruction-following

### Problema 2: Parser Não Reconhece Action

**Debug:**
```python
# Em react_agent.py, adicione print no _parse_action:
logger.info(f"🔍 Parsing response for action...")
logger.debug(f"Raw response: {text}")
```

**Verifique:**
- Se o LLM está usando formato exato: `Action: tool_name(param="value")`
- Se há espaços extras ou formatação diferente

### Problema 3: Timeout do Modelo

Se `predict_stock_direction` demorar >5s, usa fallback técnico.

**Solução:**
```python
# Em tools.py, aumente timeout:
response = httpx.post(
    "http://localhost:8000/predict",
    json={"ticker": ticker},
    timeout=10.0  # Aumentado de 5.0
)
```

---

## 📊 Comparação: Antes vs Depois

| Aspecto | Antes (❌) | Depois (✅) |
|---------|-----------|------------|
| **System Prompt** | Instruções genéricas | Regras OBRIGATÓRIAS com exemplos |
| **Logs** | Básicos | Detalhados com emojis e contexto |
| **Sources** | Sempre "LLM Agent" | Lista exata de ferramentas usadas |
| **Validação** | Sem avisos | Warning se nenhuma ferramenta usada |
| **Debug** | Difícil identificar problema | Logs mostram cada passo do agente |

---

## 🎯 Resultado Esperado

Após as melhorias, para a pergunta:
> "Qual é a probabilidade do ticker ITUB4.SA valorizar no próximo dia útil?"

**Resposta esperada:**
```json
{
  "query": "Qual é a probabilidade do ticker ITUB4.SA valorizar no próximo dia útil?",
  "response": "Com base no modelo LSTM, a probabilidade de ITUB4.SA valorizar no próximo dia útil é de 68.5%. O modelo indica COMPRA com confiança alta. Análise técnica complementar mostra RSI em 45.2 (neutro) e preço acima das médias móveis, confirmando tendência de alta.",
  "sources": [
    "predict_stock_direction(ticker=ITUB4.SA)"
  ],
  "timestamp": "2026-05-01T14:30:00"
}
```

**Logs do servidor:**
```
🔄 Iteration 1/5
🔧 Executing tool: predict_stock_direction with params {'ticker': 'ITUB4.SA'}
Model API unavailable: Connection refused. Using technical indicators fallback...
✅ Tool predict_stock_direction executed successfully
🔄 Iteration 2/5
✅ Agent provided final answer after 2 iteration(s)
🔧 Tools called: 1
✅ Agent used 1 tool(s): predict_stock_direction
```

---

## 📝 Próximos Passos

Se o problema persistir:

1. **Verificar versão do modelo:**
   - Confirmar que está usando `gemini-2.0-flash-exp` (melhor instruction-following)
   - Considerar testar com `gpt-4o` se disponível

2. **Adicionar few-shot examples:**
   - Incluir 2-3 exemplos completos de conversas bem-sucedidas no system prompt

3. **Implementar function calling nativo:**
   - Se Gemini suportar function calling (não apenas tool use via prompting)
   - Usar API de function calling em vez de parsing manual

4. **Forçar validação:**
   ```python
   if not tool_calls and "probabilidade" in user_query.lower():
       logger.error("Prediction query but no tools used!")
       raise ValueError("Agent must use predict_stock_direction for prediction queries")
   ```

---

**Arquivos modificados:**
- [src/agent/react_agent.py](../src/agent/react_agent.py) - System prompt + logs
- [src/serving/app.py](../src/serving/app.py) - Sources + validação
- [test_agent_detailed.sh](../test_agent_detailed.sh) - Script de teste
