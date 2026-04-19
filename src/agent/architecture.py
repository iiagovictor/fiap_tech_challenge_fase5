"""
Visualização de Arquitetura e Fluxos do ReAct Agent
"""

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║  ARQUITETURA DO ReAct AGENT COM 4 TOOLS                                   ║
# ╚════════════════════════════════════════════════════════════════════════════╝

ARCHITECTURE = """

┌──────────────────────────────────────────────────────────────────────────────┐
│                          ReAct Agent Architecture                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  CICLO ReAct (Reasoning + Acting)                                            │
│  ═══════════════════════════════════                                         │
│                                                                               │
│      ┌────────────────┐                                                      │
│      │  1. THINKING   │  Raciocinar sobre a tarefa                          │
│      │  Reasoning     │  • Analisar requisição                              │
│      │                │  • Decidir próxima ação                              │
│      └────────┬────────┘                                                     │
│             │                                                                │
│             ↓                                                                │
│      ┌────────────────┐                                                      │
│      │  2. ACTING     │  Executar tool selecionada                          │
│      │  Tool Calling  │  • Preparar parâmetros                              │
│      │                │  • Executar função                                  │
│      └────────┬────────┘                                                     │
│             │                                                                │
│             ↓                                                                │
│      ┌────────────────┐                                                      │
│      │  3. OBSERVING  │  Observar e registrar resultado                     │
│      │  Observation   │  • Analisar output                                  │
│      │                │  • Registrar em histórico                           │
│      └────────┬────────┘                                                     │
│             │                                                                │
│             └─ Repetir? ──→ SIM ──→ VOLTAR A STEP 1                        │
│                               ↓                                              │
│                             NÃO                                              │
│                               ↓                                              │
│                        TAREFA COMPLETA                                      │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────────┐
│                          4 TOOLS DISPONÍVEIS                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  Tool 1: read_project_files                                                  │
│  ════════════════════════════════════════════════════════════════════════   │
│  Função: Ler arquivos do projeto                                             │
│  Entrada: file_path ou pattern                                               │
│  Saída: Dict[arquivo] = conteúdo                                             │
│  Uso: agent.act("read_project_files", {"pattern": "configs/*.yaml"})        │
│                                                                               │
│                                                                               │
│  Tool 2: execute_pipeline                                                    │
│  ════════════════════════════════════════════════════════════════════════   │
│  Função: Executar etapas do pipeline                                         │
│  Stages: fetch │ process │ validate                                          │
│  Entrada: stage, mode, days_back                                             │
│  Saída: Status, message, resultados                                          │
│  Uso: agent.act("execute_pipeline", {"stage": "fetch", "mode": "incremental"})
│                                                                               │
│                                                                               │
│  Tool 3: validate_golden_set                                                 │
│  ════════════════════════════════════════════════════════════════════════   │
│  Função: Validar dados contra golden_set                                     │
│  Validações: schema, tickers, integridade, estatísticas                      │
│  Entrada: data_source (processed ou golden_set)                              │
│  Saída: ValidationResult com status e anomalias                              │
│  Uso: agent.act("validate_golden_set", {"data_source": "processed"})        │
│                                                                               │
│                                                                               │
│  Tool 4: generate_report                                                     │
│  ════════════════════════════════════════════════════════════════════════   │
│  Função: Gerar relatórios de qualidade                                       │
│  Tipos: full │ summary │ validation                                          │
│  Entrada: report_type, output_format                                         │
│  Saída: Relatório estruturado (json/markdown/html)                           │
│  Uso: agent.act("generate_report", {"report_type": "full"})                 │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────────┐
│                          FLUXO: Pipeline Completo                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  Tarefa: agent.run("pipeline_completo")                                      │
│                                                                               │
│  ┌─────────────────────────────────────┐                                    │
│  │ Step 1: execute_pipeline            │                                    │
│  │ • stage="fetch"                     │                                    │
│  │ • mode="incremental"                │                                    │
│  │ • days_back=7                       │                                    │
│  │                                      │                                    │
│  │ Resultado: CSV com dados novos      │                                    │
│  └────────────────┬────────────────────┘                                    │
│                   ↓                                                          │
│  ┌─────────────────────────────────────┐                                    │
│  │ Step 2: execute_pipeline            │                                    │
│  │ • stage="process"                   │                                    │
│  │                                      │                                    │
│  │ Resultado: Parquet processado       │                                    │
│  └────────────────┬────────────────────┘                                    │
│                   ↓                                                          │
│  ┌─────────────────────────────────────┐                                    │
│  │ Step 3: execute_pipeline            │                                    │
│  │ • stage="validate"                  │                                    │
│  │                                      │                                    │
│  │ Resultado: ValidationResult         │                                    │
│  └────────────────┬────────────────────┘                                    │
│                   ↓                                                          │
│  ┌─────────────────────────────────────┐                                    │
│  │ Step 4: generate_report             │                                    │
│  │ • report_type="full"                │                                    │
│  │                                      │                                    │
│  │ Resultado: Relatório completo       │                                    │
│  └─────────────────────────────────────┘                                    │
│                   ↓                                                          │
│             COMPLETO ✓                                                      │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────────┐
│                  ESTRUTURA DE DADOS: ToolOutput                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ToolOutput                                                                  │
│  ════════════════════════════════════════════════════════════════════════   │
│                                                                               │
│  @dataclass                                                                  │
│  class ToolOutput:                                                           │
│      tool_name: str       # Nome da tool que executou                        │
│      status: str          # success | error | partial                        │
│      result: Any          # Resultado da execução                            │
│      message: str         # Mensagem descritiva                              │
│      timestamp: str       # ISO 8601 datetime                                │
│                                                                               │
│  Exemplo:                                                                    │
│  ────────                                                                    │
│  ToolOutput(                                                                 │
│      tool_name="validate_golden_set",                                       │
│      status="partial",                                                       │
│      result={                                                                │
│          "status": "warning",                                                │
│          "num_records": 1000,                                                │
│          "anomalies": ["AAPL divergiu 12%"]                                  │
│      },                                                                      │
│      message="Validação completa com avisos",                                │
│      timestamp="2024-01-01T12:30:45.123456"                                  │
│  )                                                                           │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────────┐
│                         HISTÓRICO DE EXECUÇÃO                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  agent.get_history()                                                         │
│  ═════════════════════════════════════════════════════════════════════════  │
│                                                                               │
│  Retorna lista de todas as ações executadas:                                 │
│                                                                               │
│  [                                                                            │
│      {                                                                        │
│          "step": 1,                                                          │
│          "action": "execute_pipeline",                                       │
│          "status": "success",                                                │
│          "timestamp": "2024-01-01T12:30:10.000000"                           │
│      },                                                                      │
│      {                                                                        │
│          "step": 2,                                                          │
│          "action": "generate_report",                                        │
│          "status": "success",                                                │
│          "timestamp": "2024-01-01T12:31:15.000000"                           │
│      },                                                                      │
│      ...                                                                      │
│  ]                                                                            │
│                                                                               │
│  Útil para:                                                                  │
│  • Debugging                                                                 │
│  • Auditoria                                                                 │
│  • Monitoramento                                                             │
│  • Reprodução                                                                │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────────────┐
│                     FLUXO: Validação de Dados                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  agent.run("validar_dados")                                                  │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │ validate_golden_set (Carrega Golden Set)                    │           │
│  ├──────────────────────────────────────────────────────────────┤           │
│  │ Validação 1: Schema                                          │           │
│  │  └─ Verifica: colunas, tipos, não-nulos                     │           │
│  │     Status: ✓ pass | ✗ fail                                 │           │
│  │                                                              │           │
│  │ Validação 2: Tickers                                         │           │
│  │  └─ Verifica: tickers compatíveis                           │           │
│  │     Status: ✓ pass | ⚠ warning | ✗ fail                   │           │
│  │                                                              │           │
│  │ Validação 3: Integridade                                    │           │
│  │  └─ Verifica: nulls, infinities, OHLCV valid               │           │
│  │     Status: ✓ pass | ✗ fail                                 │           │
│  │                                                              │           │
│  │ Validação 4: Estatísticas                                    │           │
│  │  └─ Verifica: means/ranges ±15% tolerância                 │           │
│  │     Status: ✓ pass | ⚠ warning | ✗ fail                   │           │
│  │                                                              │           │
│  │ Resultado Final:                                            │           │
│  │  • Status: pass | warning | fail | skip                    │           │
│  │  • Anomalias: Lista de issues                               │           │
│  │  • Message: Descrição legível                               │           │
│  └──────────────────────────────────────────────────────────────┘           │
│                   ↓                                                          │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │ generate_report (Formata resultado)                         │           │
│  │  └─ json, markdown ou html                                  │           │
│  └──────────────────────────────────────────────────────────────┘           │
│                   ↓                                                          │
│             RETORNA RESULTADO                                               │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

"""

print(ARCHITECTURE)

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("Arquitetura visualizada. Ver docs/REACT_AGENT.md para detalhes completos.")
    print("=" * 80)
