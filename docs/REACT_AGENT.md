# ReAct Agent - Documentação Completa

## 📋 O que é ReAct Agent?

Um **Agente ReAct** (Reasoning + Acting) é um padrão de arquitetura que permite um sistema executar tarefas complexas através de um ciclo iterativo:

```
┌──────────────┐
│ 1. REASONING │ (Pensar)
└──────┬───────┘
       ↓
┌──────────────┐
│ 2. ACTING    │ (Executar Tools)
└──────┬───────┘
       ↓
┌──────────────┐
│ 3. OBSERVING │ (Observar Resultado)
└──────┬───────┘
       ↓
    Repetir?
```

## 🛠️ Tools Disponíveis

### 1. **read_project_files** - Ler Arquivos do Projeto
```python
agent.act("read_project_files", {
    "file_path": "configs/model_config.yaml"  # Arquivo específico
    # ou
    "pattern": "configs/*.yaml"  # Padrão glob
})
```

**Usa para:**
- Ler configurações
- Verificar estrutura do projeto
- Inspecionar código/dados

---

### 2. **execute_pipeline** - Executar Etapas do Pipeline
```python
agent.act("execute_pipeline", {
    "stage": "fetch",      # fetch, process, validate
    "mode": "incremental", # historical, incremental
    "days_back": 7         # Dias a buscar
})
```

**Stages disponíveis:**
- `fetch`: Ingestão de dados
- `process`: Processamento e enriquecimento
- `validate`: Validação contra golden_set

---

### 3. **validate_golden_set** - Validar Dados
```python
agent.act("validate_golden_set", {
    "data_source": "processed"  # processed ou golden_set
})
```

**Retorna:**
- Schema válido?
- Tickers compatíveis?
- Integridade dos dados?
- Propriedades estatísticas OK?

---

### 4. **generate_report** - Gerar Relatórios
```python
agent.act("generate_report", {
    "report_type": "full",      # full, summary, validation
    "output_format": "json"     # json, markdown, html
})
```

**Report types:**
- `full`: Relatório completo com todas as seções
- `summary`: Resumo de dados
- `validation`: Apenas validação

---

## 📖 Uso Básico

### Instalação

```bash
# As dependências já estão instaladas
pip install pandas pyyaml
```

### Exemplo 1: Executar Pipeline Completo

```python
from src.agent.react_agent import ReActAgent

agent = ReActAgent(max_iterations=10)
result = agent.run("pipeline_completo")

# Resultado:
# {
#   "task": "pipeline_completo",
#   "total_steps": 4,
#   "results": [...],
#   "status": "completed"
# }
```

### Exemplo 2: Validar Dados

```python
agent = ReActAgent()
result = agent.run("validar_dados")

print(result["results"])
```

### Exemplo 3: Gerar Relatório

```python
agent = ReActAgent()
result = agent.run("gerar_relatorio")

# Acessar dados do relatório
report_data = result["results"][0]["output"]
```

### Exemplo 4: Usar Tools Manualmente

```python
agent = ReActAgent()

# Usar uma tool específica
output = agent.act("read_project_files", {
    "pattern": "configs/*.yaml"
})

print(output.status)     # success/error
print(output.result)     # conteúdo lido
print(output.message)    # mensagem descritiva
```

---

## 🔄 Ciclo ReAct Completo

```python
agent = ReActAgent()

# 1. THINK - Pensar no que fazer
thought = agent.think("Preciso validar os dados")
print(f"Pensamento: {thought.reasoning}")
print(f"Próxima ação: {thought.next_action}")

# 2. ACT - Executar uma tool
output = agent.act("validate_golden_set", {
    "data_source": "processed"
})
print(f"Resultado: {output.status}")

# 3. OBSERVE - Observar o resultado
observation = agent.observe(output)
print(f"Observação: {output.message}")

# Histórico
print(f"Histórico: {agent.get_history()}")
```

---

## 🚀 Tarefas Pré-configuradas

### `pipeline_completo`
Executa ingestão → processamento → validação → relatório

```bash
python src/agent/examples.py 1
```

### `validar_dados`
Valida dados processados contra golden_set

```bash
python src/agent/examples.py 2
```

### `gerar_relatorio`
Gera relatório completo

```bash
python src/agent/examples.py 3
```

### `ingestao`
Apenas ingestão incremental

```python
agent.run("ingestao")
```

---

## 📊 Estrutura de Dados

### ToolOutput
```python
@dataclass
class ToolOutput:
    tool_name: str      # Nome da tool
    status: str         # success, error, partial
    result: Any         # Resultado da execução
    message: str        # Mensagem descritiva
    timestamp: str      # Quando foi executado
```

### Thought
```python
@dataclass
class Thought:
    step: int           # Número do step
    reasoning: str      # Raciocínio
    next_action: str    # Próxima ação
```

### Observation
```python
@dataclass
class Observation:
    step: int           # Número do step
    tool_output: ToolOutput  # Output da tool
```

---

## 🔧 Customizando o Agent

### Criar Custom Tool

```python
from src.agent.react_agent import Tool, ToolOutput

class MyCustomTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def description(self) -> str:
        return "Descrição da minha tool"
    
    def execute(self, **kwargs) -> ToolOutput:
        try:
            # Sua lógica aqui
            result = {}
            return ToolOutput(
                tool_name=self.name,
                status="success",
                result=result,
                message="Executado com sucesso"
            )
        except Exception as e:
            return ToolOutput(
                tool_name=self.name,
                status="error",
                result={},
                message=str(e)
            )

# Adicionar ao agent
agent.tools["my_tool"] = MyCustomTool()
```

### Criar Custom Task

```python
agent.tools["new_task"] = [
    ("tool1_name", {"param": "value"}),
    ("tool2_name", {"param": "value"}),
]

result = agent.run("new_task")
```

---

## 📈 Exemplos de Saída

### Sucesso ✓
```json
{
  "task": "validar_dados",
  "total_steps": 2,
  "results": [
    {
      "action": "validate_golden_set",
      "output": {
        "status": "pass",
        "num_records": 1000
      },
      "status": "success"
    }
  ],
  "status": "completed"
}
```

### Com Avisos ⚠️
```json
{
  "task": "validar_dados",
  "results": [
    {
      "action": "validate_golden_set",
      "output": {
        "status": "warning",
        "anomalies": ["AAPL divergiu 12%"]
      },
      "status": "partial"
    }
  ],
  "status": "completed"
}
```

### Erro ❌
```json
{
  "task": "pipeline_completo",
  "results": [
    {
      "action": "execute_pipeline",
      "output": {},
      "status": "error"
    }
  ],
  "status": "completed"
}
```

---

## 🧪 Testes

### Rodar Testes do Agent

```bash
# Todos os testes
pytest tests/test_react_agent.py -v

# Testes específicos
pytest tests/test_react_agent.py::TestReActAgent -v

# Com output detalhado
pytest tests/test_react_agent.py -v -s
```

---

## 🎯 Casos de Uso

### Caso 1: Validação Automática de Qualidade
```python
agent = ReActAgent()
result = agent.run("validar_dados")

if result["results"][0]["output"]["status"] == "pass":
    print("✓ Dados validados com sucesso")
else:
    print("✗ Anomalias detectadas")
```

### Caso 2: Monitoramento de Pipeline
```python
import schedule
import time

def monitor_pipeline():
    agent = ReActAgent()
    result = agent.run("pipeline_completo")
    
    if result["status"] == "completed":
        print("Pipeline executado com sucesso")
    else:
        print("Erro no pipeline!")

# Agendar para rodar a cada hora
schedule.every(1).hour.do(monitor_pipeline)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Caso 3: Geração de Relatórios Automatizados
```python
import datetime

agent = ReActAgent()
result = agent.run("gerar_relatorio")

report = result["results"][0]["output"]

with open(f"relatorio_{datetime.date.today()}.json", "w") as f:
    json.dump(report, f, indent=2, default=str)

print(f"Relatório salvo")
```

---

## 🔍 Debugging

### Ver Histórico de Execução
```python
agent = ReActAgent()
result = agent.run("validar_dados")

for step in result["history"]:
    print(f"Step {step['step']}: {step['action']} → {step['status']}")
```

### Ver Detalhes de uma Tool
```python
agent = ReActAgent()

output = agent.act("validate_golden_set", {"data_source": "processed"})

print(f"Tool: {output.tool_name}")
print(f"Status: {output.status}")
print(f"Resultado: {output.result}")
print(f"Mensagem: {output.message}")
print(f"Timestamp: {output.timestamp}")
```

### Resetar Agent
```python
agent = ReActAgent()
agent.run("task1")

agent.reset()  # Limpa histórico e step

agent.run("task2")
```

---

## 📚 Referências

- [ReAct Paper](https://arxiv.org/abs/2210.03629)
- [Agent Architecture](https://docs.anthropic.com/en/docs/build-a-system-prompt-for-claude)
- [Tool Use](https://docs.anthropic.com/en/docs/build-a-system-prompt-for-claude)

---

## 🚀 Próximos Passos

1. **Integrar com LLM**: Usar Claude para gerar pensamentos automaticamente
2. **Persistence**: Salvar histórico de execuções
3. **Monitoring**: Integrar com CloudWatch/Prometheus
4. **Advanced Tools**: Adicionar mais tools especializadas
5. **Parallelization**: Executar tools em paralelo quando possível

---

## 📞 Suporte

Para problemas ou dúvidas sobre o ReAct Agent:

1. Verificar logs: `tail -f logs/react_agent.log`
2. Rodar testes: `pytest tests/test_react_agent.py -v`
3. Ver exemplos: `python src/agent/examples.py`
