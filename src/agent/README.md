# ReAct Agent - Agent com Raciocínio e Ação

## 📁 Estrutura

```
src/agent/
├── __init__.py              # Exports principais
├── react_agent.py           # Implementação principal (4 tools + agent)
├── examples.py              # 5 exemplos de uso
└── README.md               # Este arquivo
```

## 🎯 Propósito

Implementar um **Agente ReAct** (Reasoning + Acting) que pode:

1. **Raciocinar** sobre tarefas complexas (Thinking)
2. **Executar** ferramentas/tools (Acting)
3. **Observar** resultados e iterar (Observation)

## 🛠️ 4 Tools Implementadas

### 1. **read_project_files**
Ler arquivos e configurações do projeto
- Suporta arquivo específico ou padrão glob
- Útil para inspecionar estrutura

### 2. **execute_pipeline**
Executar etapas do pipeline de dados
- Stages: fetch, process, validate
- Modos: historical, incremental
- Configurável com parâmetros

### 3. **validate_golden_set**
Validar dados contra referência de qualidade
- 4 camadas de validação
- Schema, tickers, integridade, estatísticas
- Retorna ValidationResult estruturado

### 4. **generate_report**
Gerar relatórios de qualidade e validação
- Tipos: full, summary, validation
- Formatos: json, markdown, html
- Inclui estatísticas e anomalias

## 🚀 Quick Start

```python
from src.agent.react_agent import ReActAgent

# Criar agent
agent = ReActAgent(max_iterations=10)

# Executar tarefa pré-configurada
result = agent.run("validar_dados")

# Ou usar tools manualmente
output = agent.act("generate_report", {
    "report_type": "summary"
})
```

## 🔄 Ciclo ReAct

```
1. Thought:   Pensar no que fazer
   └─ Raciocinar sobre a tarefa
   
2. Action:    Executar uma tool
   └─ Chamar execute() da tool selecionada
   
3. Observation: Observar resultado
   └─ Registrar em histórico
   
Repetir até tarefa completa
```

## 📋 Tarefas Pré-configuradas

- `pipeline_completo`: fetch → process → validate → report
- `validar_dados`: validate → report
- `gerar_relatorio`: report
- `ingestao`: fetch only

## 🧪 Exemplos

```bash
# Rodar exemplos
python src/agent/examples.py 1    # Pipeline completo
python src/agent/examples.py 2    # Validar dados
python src/agent/examples.py 3    # Gerar relatório
python src/agent/examples.py 4    # Sequência customizada
python src/agent/examples.py 5    # Listar tools
```

## 🧬 Criar Custom Tool

```python
from src.agent.react_agent import Tool, ToolOutput

class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    def execute(self, **kwargs) -> ToolOutput:
        try:
            # Sua lógica
            return ToolOutput(
                tool_name=self.name,
                status="success",
                result={},
                message="OK"
            )
        except Exception as e:
            return ToolOutput(
                tool_name=self.name,
                status="error",
                result={},
                message=str(e)
            )

agent.tools["my_tool"] = MyTool()
```

## 📊 Arquitetura

```
┌─────────────────────────────────────────┐
│         ReActAgent (Orquestrador)        │
├─────────────────────────────────────────┤
│ • think()    - Raciocina               │
│ • act()      - Executa tools           │
│ • observe()  - Observa resultados      │
│ • run()      - Executa tarefa          │
└─────────────────────────────────────────┘
         ↓         ↓         ↓         ↓
    ┌────────┬────────┬────────┬────────┐
    │ Tool 1 │ Tool 2 │ Tool 3 │ Tool 4 │
    │ Read   │Execute │Validate│Report  │
    └────────┴────────┴────────┴────────┘
```

## 📈 Output Estruturado

Todas as tools retornam:

```python
ToolOutput(
    tool_name="...",           # Nome da tool
    status="success|error|partial",  # Status
    result={...},              # Resultado
    message="...",             # Mensagem descritiva
    timestamp="2024-01-01T..."  # Quando executado
)
```

## 🔧 Configuração

Nenhuma configuração necessária! O agent:
- Detecta estrutura do projeto automaticamente
- Usa configs em `configs/model_config.yaml`
- Salva dados em `data/raw/` e `data/processed/`
- Usa golden_set em `data/golden_set/`

## 🧪 Testes

```bash
# Rodar testes
pytest tests/test_react_agent.py -v

# Testes específicos
pytest tests/test_react_agent.py::TestReActAgent -v

# Com output
pytest tests/test_react_agent.py -v -s
```

## 📚 Documentação Completa

Ver [docs/REACT_AGENT.md](../REACT_AGENT.md) para:
- Uso avançado
- Customização
- Integração
- Casos de uso
- Debugging

## 🎓 Padrão ReAct

**Origem**: [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)

**Ideia**:
- LLMs têm fraco desempenho em tarefas que requerem raciocínio + ação
- Combinar raciocínio explícito com execução de tools melhora resultados
- Iteração permite ajustamento baseado em feedback

**Benefícios**:
- ✓ Maior transparência (ver pensamentos)
- ✓ Melhor controle (escolher tools)
- ✓ Rastreabilidade (histórico)
- ✓ Iteração (refinar resultados)
