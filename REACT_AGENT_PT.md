# ReAct Agent - Guia Rápido em Português

## O que foi criado?

Um **Agente com Raciocínio e Ação (ReAct)** para seu projeto com **4 ferramentas** que automatiza:

1. ✅ Leitura de arquivos do projeto
2. ✅ Execução do pipeline de dados
3. ✅ Validação contra golden_set
4. ✅ Geração de relatórios

---

## 📦 Arquivos Criados

```
src/agent/
├── react_agent.py        ← Implementação principal (4 tools + agent)
├── examples.py          ← 5 exemplos práticos
├── architecture.py      ← Visualização da arquitetura
├── __init__.py         ← Package Python
└── README.md           ← Documentação técnica

docs/
└── REACT_AGENT.md      ← Guia completo (uso, customização, casos)

tests/
└── test_react_agent.py ← 20+ testes unitários

Makefile
└── Adicionados 4 targets novos (agent-example, agent-tools, etc)
```

---

## 🚀 Como Usar?

### Opção 1: Teste Rápido

```bash
# Ver tools disponíveis
make agent-tools

# Validar dados
make agent-validate

# Gerar relatório
make agent-report
```

### Opção 2: Python Direto

```python
from src.agent.react_agent import ReActAgent

# Criar agent
agent = ReActAgent(max_iterations=10)

# Executar tarefa
result = agent.run("validar_dados")

# Ver resultado
print(result)
```

### Opção 3: Exemplos

```bash
python src/agent/examples.py 1    # Pipeline completo
python src/agent/examples.py 2    # Validar dados
python src/agent/examples.py 3    # Gerar relatório
python src/agent/examples.py 4    # Sequência customizada
```

---

## 🛠️ As 4 Tools Explicadas

### Tool 1: **read_project_files**
**O que faz**: Ler arquivos do projeto

```python
agent.act("read_project_files", {
    "file_path": "configs/model_config.yaml"  # Um arquivo
    # ou
    "pattern": "configs/*.yaml"                # Vários arquivos
})
```

### Tool 2: **execute_pipeline**
**O que faz**: Rodar etapas do pipeline

```python
agent.act("execute_pipeline", {
    "stage": "fetch",           # fetch, process, validate
    "mode": "incremental",      # ou historical
    "days_back": 7              # Quantos dias buscar
})
```

### Tool 3: **validate_golden_set**
**O que faz**: Validar dados em 4 níveis
- Schema (colunas/tipos corretos?)
- Tickers (dados esperados?)
- Integridade (nulls/valores inválidos?)
- Estatísticas (valores dentro da faixa?)

```python
agent.act("validate_golden_set", {
    "data_source": "processed"  # processed ou golden_set
})
```

### Tool 4: **generate_report**
**O que faz**: Gerar relatório de qualidade

```python
agent.act("generate_report", {
    "report_type": "full",      # full, summary, validation
    "output_format": "json"     # json, markdown, html
})
```

---

## 🔄 O Ciclo ReAct

```
1. PENSAR (Reasoning)
   └─ "O que preciso fazer?"

2. AGIR (Acting)
   └─ "Vou usar esta tool"

3. OBSERVAR (Observation)
   └─ "Qual foi o resultado?"

Repetir até tarefa completa
```

---

## 💡 Exemplos Práticos

### Exemplo 1: Pipeline Completo

```python
agent = ReActAgent()
result = agent.run("pipeline_completo")

# Executa:
# 1. Buscar dados (fetch)
# 2. Processar (process)
# 3. Validar (validate)
# 4. Gerar relatório (report)
```

### Exemplo 2: Validação

```python
agent = ReActAgent()
result = agent.run("validar_dados")

# Valida dados processados
if result["results"][0]["output"]["status"] == "pass":
    print("✓ Dados OK")
else:
    print("✗ Problemas encontrados")
```

### Exemplo 3: Usar Tools Manualmente

```python
agent = ReActAgent()

# Step 1: Pensar
thought = agent.think("Preciso validar os dados")
print(thought.reasoning)

# Step 2: Agir
output = agent.act("validate_golden_set")
print(f"Status: {output.status}")

# Step 3: Observar
observation = agent.observe(output)

# Ver histórico
print(agent.get_history())
```

---

## 📊 Resultado Esperado

```json
{
  "task": "validar_dados",
  "total_steps": 2,
  "results": [
    {
      "action": "validate_golden_set",
      "output": {
        "status": "pass",
        "num_records": 1000,
        "tickers_validated": 5,
        "anomalies": []
      },
      "status": "success"
    },
    {
      "action": "generate_report",
      "output": {
        "generated_at": "2024-01-01T12:30:00",
        "sections": {
          "validation": { ... },
          "statistics": { ... }
        }
      },
      "status": "success"
    }
  ],
  "status": "completed"
}
```

---

## 🧪 Executar Testes

```bash
# Todos os testes
pytest tests/test_react_agent.py -v

# Teste específico
pytest tests/test_react_agent.py::TestReActAgent -v

# Com detalhes
pytest tests/test_react_agent.py -v -s
```

---

## 🎨 Criar Sua Própria Tool

```python
from src.agent.react_agent import Tool, ToolOutput

class MinhaFerramentaTool(Tool):
    @property
    def name(self) -> str:
        return "minha_ferramenta"
    
    @property
    def description(self) -> str:
        return "Descrição do que faz"
    
    def execute(self, **kwargs) -> ToolOutput:
        try:
            # Sua lógica aqui
            resultado = {}
            
            return ToolOutput(
                tool_name=self.name,
                status="success",
                result=resultado,
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
agent.tools["minha_ferramenta"] = MinhaFerramentaTool()

# Usar
result = agent.act("minha_ferramenta", {"param": "valor"})
```

---

## 📚 Documentação

- **Guia Completo**: [docs/REACT_AGENT.md](../../docs/REACT_AGENT.md)
- **Técnico**: [src/agent/README.md](README.md)
- **Arquitetura**: `python src/agent/architecture.py`
- **Exemplos**: [src/agent/examples.py](examples.py)

---

## ✨ O que o Agent faz?

✅ **Raciocina**: Pensa sobre a melhor sequência de ações
✅ **Executa**: Chama as tools certas nos momentos certos
✅ **Observa**: Registra resultados e aprende com eles
✅ **Itera**: Repete o ciclo até completar a tarefa

---

## 🎯 Tarefas Disponíveis

| Tarefa | Faz | Comando |
|--------|------|---------|
| `pipeline_completo` | Fetch → Process → Validate → Report | `agent.run("pipeline_completo")` |
| `validar_dados` | Validate → Report | `agent.run("validar_dados")` |
| `gerar_relatorio` | Report | `agent.run("gerar_relatorio")` |
| `ingestao` | Fetch | `agent.run("ingestao")` |

---

## 🚀 Próximos Passos

1. **Testar localmente**: `make agent-example`
2. **Validar dados**: `make agent-validate`
3. **Gerar relatório**: `make agent-report`
4. **Criar sua ferramenta**: Estender com custom tools
5. **Integrar LLM**: Usar Claude para raciocínio automático

---

## 📞 Precisa de Ajuda?

```bash
# Ver tools disponíveis
make agent-tools

# Rodar exemplos
python src/agent/examples.py

# Ver arquitetura
python src/agent/architecture.py

# Executar testes
pytest tests/test_react_agent.py -v
```

---

## 💬 Resumo em Uma Frase

**Um Agente Inteligente que raciocina sobre tarefas, executa 4 ferramentas poderosas (leitura, execução, validação, relatório) e observa resultados para garantir sucesso do pipeline.**
