"""
ReAct Agent com Tools para o Projeto FIAP Tech Challenge

Arquitetura:
    Agent (ReAct)
    ├─ Reasoning (pensar)
    ├─ Tools (executar)
    │   ├─ read_project_files
    │   ├─ execute_pipeline
    │   ├─ validate_golden_set
    │   └─ generate_report
    └─ Observation (observar resultados)

Padrão: Reason → Act → Observe → Repeat
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("react_agent")

PROJECT_ROOT = Path(__file__).parent.parent.parent


# ── Tool Base Class ────────────────────────────────────────────────────────

@dataclass
class ToolInput:
    """Input para executar uma tool"""
    tool_name: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolOutput:
    """Output de uma tool"""
    tool_name: str
    status: str  # success, error, partial
    result: Any
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class Tool(ABC):
    """Interface base para tools"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nome da tool"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Descrição do que a tool faz"""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolOutput:
        """Executar a tool"""
        pass


# ── Tools ──────────────────────────────────────────────────────────────────

class ReadProjectFilesTool(Tool):
    """Tool para ler arquivos do projeto"""
    
    @property
    def name(self) -> str:
        return "read_project_files"
    
    @property
    def description(self) -> str:
        return "Ler arquivos do projeto (config, dados, código)"
    
    def execute(self, file_path: str = None, pattern: str = None) -> ToolOutput:
        """
        Ler arquivos do projeto.
        
        Args:
            file_path: Caminho específico do arquivo
            pattern: Padrão glob para encontrar arquivos
        """
        try:
            results = {}
            
            if file_path:
                # Ler arquivo específico
                full_path = PROJECT_ROOT / file_path
                if full_path.exists() and full_path.is_file():
                    content = full_path.read_text()
                    results[file_path] = content
                else:
                    return ToolOutput(
                        tool_name=self.name,
                        status="error",
                        result={},
                        message=f"Arquivo não encontrado: {file_path}"
                    )
            
            elif pattern:
                # Encontrar arquivos pelo padrão
                for path in PROJECT_ROOT.glob(pattern):
                    if path.is_file():
                        try:
                            content = path.read_text()
                            rel_path = path.relative_to(PROJECT_ROOT)
                            results[str(rel_path)] = content
                        except Exception as e:
                            log.warning(f"Erro ao ler {path}: {e}")
            
            return ToolOutput(
                tool_name=self.name,
                status="success" if results else "error",
                result=results,
                message=f"Lidos {len(results)} arquivo(s)"
            )
        
        except Exception as e:
            return ToolOutput(
                tool_name=self.name,
                status="error",
                result={},
                message=str(e)
            )


class ExecutePipelineTool(Tool):
    """Tool para executar etapas do pipeline"""
    
    @property
    def name(self) -> str:
        return "execute_pipeline"
    
    @property
    def description(self) -> str:
        return "Executar etapas do pipeline (fetch, process, validate)"
    
    def execute(
        self,
        stage: str = "fetch",
        mode: str = "incremental",
        days_back: int = 7
    ) -> ToolOutput:
        """
        Executar etapa do pipeline.
        
        Args:
            stage: Etapa a executar (fetch, process, validate)
            mode: Modo de execução (historical, incremental)
            days_back: Dias a buscar (para incremental)
        """
        try:
            # Importar módulos dinamicamente
            import sys
            sys.path.insert(0, str(PROJECT_ROOT / "src"))
            
            results = {
                "stage": stage,
                "mode": mode,
                "status": "starting",
                "timestamp": datetime.now().isoformat()
            }
            
            if stage == "fetch":
                from data.ingest import main as fetch_main
                log.info(f"Executando ingestão em modo {mode}...")
                fetch_main(mode=mode, days_back=days_back)
                results["status"] = "completed"
                results["message"] = f"Ingestão {mode} completada"
            
            elif stage == "process":
                from features.process import main as process_main
                log.info("Executando processamento...")
                process_main()
                results["status"] = "completed"
                results["message"] = "Processamento completado"
            
            elif stage == "validate":
                from features.validation import validate_against_golden_set
                import pandas as pd
                log.info("Executando validação...")
                processed_path = PROJECT_ROOT / "data" / "processed" / "ohlcv_processed.parquet"
                if processed_path.exists():
                    df = pd.read_parquet(processed_path)
                    validation_result = validate_against_golden_set(df)
                    results["status"] = "completed"
                    results["validation"] = validation_result.to_dict()
                    results["message"] = f"Validação: {validation_result.status}"
                else:
                    return ToolOutput(
                        tool_name=self.name,
                        status="error",
                        result=results,
                        message="Dados processados não encontrados"
                    )
            
            else:
                return ToolOutput(
                    tool_name=self.name,
                    status="error",
                    result=results,
                    message=f"Stage desconhecida: {stage}"
                )
            
            return ToolOutput(
                tool_name=self.name,
                status="success",
                result=results,
                message=results.get("message", "Execução completada")
            )
        
        except Exception as e:
            log.error(f"Erro ao executar pipeline: {e}", exc_info=True)
            return ToolOutput(
                tool_name=self.name,
                status="error",
                result={"stage": stage, "error": str(e)},
                message=f"Erro na execução: {e}"
            )


class ValidateGoldenSetTool(Tool):
    """Tool para validar dados contra golden_set"""
    
    @property
    def name(self) -> str:
        return "validate_golden_set"
    
    @property
    def description(self) -> str:
        return "Validar dados processados contra golden_set de referência"
    
    def execute(self, data_source: str = "processed") -> ToolOutput:
        """
        Validar dados.
        
        Args:
            data_source: Fonte de dados (processed, golden_set)
        """
        try:
            import sys
            sys.path.insert(0, str(PROJECT_ROOT / "src"))
            from features.validation import validate_against_golden_set
            
            if data_source == "processed":
                data_path = PROJECT_ROOT / "data" / "processed" / "ohlcv_processed.parquet"
            elif data_source == "golden_set":
                data_path = PROJECT_ROOT / "data" / "golden_set" / "ohlcv_golden.parquet"
            else:
                return ToolOutput(
                    tool_name=self.name,
                    status="error",
                    result={},
                    message=f"Fonte desconhecida: {data_source}"
                )
            
            if not data_path.exists():
                return ToolOutput(
                    tool_name=self.name,
                    status="error",
                    result={"source": data_source},
                    message=f"Arquivo não encontrado: {data_path}"
                )
            
            df = pd.read_parquet(data_path)
            validation_result = validate_against_golden_set(df)
            
            return ToolOutput(
                tool_name=self.name,
                status="success" if validation_result.status == "pass" else "partial",
                result=validation_result.to_dict(),
                message=f"Validação {data_source}: {validation_result.status}"
            )
        
        except Exception as e:
            log.error(f"Erro na validação: {e}", exc_info=True)
            return ToolOutput(
                tool_name=self.name,
                status="error",
                result={},
                message=str(e)
            )


class GenerateReportTool(Tool):
    """Tool para gerar relatórios"""
    
    @property
    def name(self) -> str:
        return "generate_report"
    
    @property
    def description(self) -> str:
        return "Gerar relatório de qualidade e validação dos dados"
    
    def execute(self, report_type: str = "full", output_format: str = "json") -> ToolOutput:
        """
        Gerar relatório.
        
        Args:
            report_type: Tipo de relatório (full, summary, validation)
            output_format: Formato de saída (json, markdown, html)
        """
        try:
            import sys
            sys.path.insert(0, str(PROJECT_ROOT / "src"))
            from features.validation import validate_against_golden_set
            
            report = {
                "generated_at": datetime.now().isoformat(),
                "report_type": report_type,
                "sections": {}
            }
            
            # Seção 1: Status dos dados
            processed_path = PROJECT_ROOT / "data" / "processed" / "ohlcv_processed.parquet"
            if processed_path.exists():
                df = pd.read_parquet(processed_path)
                report["sections"]["data_summary"] = {
                    "total_rows": len(df),
                    "total_tickers": df["Ticker"].nunique(),
                    "date_range": {
                        "start": str(df["Date"].min()),
                        "end": str(df["Date"].max())
                    },
                    "tickers": sorted(df["Ticker"].unique().tolist())
                }
            
            # Seção 2: Validação contra golden_set
            if report_type in ["full", "validation"]:
                try:
                    validation_result = validate_against_golden_set(df)
                    report["sections"]["validation"] = validation_result.to_dict()
                except Exception as e:
                    report["sections"]["validation"] = {"error": str(e)}
            
            # Seção 3: Estatísticas
            if report_type in ["full", "summary"] and processed_path.exists():
                report["sections"]["statistics"] = {
                    "price_stats": {
                        "close_mean": float(df["Close"].mean()),
                        "close_std": float(df["Close"].std()),
                        "close_min": float(df["Close"].min()),
                        "close_max": float(df["Close"].max())
                    },
                    "volume_stats": {
                        "volume_mean": float(df["Volume"].mean()),
                        "volume_median": float(df["Volume"].median())
                    },
                    "returns_stats": {
                        "daily_return_mean": float(df["Daily_Return"].mean()),
                        "daily_return_std": float(df["Daily_Return"].std())
                    }
                }
            
            # Formatar saída
            if output_format == "json":
                result = report
            elif output_format == "markdown":
                result = self._format_markdown(report)
            else:
                result = report
            
            return ToolOutput(
                tool_name=self.name,
                status="success",
                result=result,
                message=f"Relatório {report_type} gerado com sucesso"
            )
        
        except Exception as e:
            log.error(f"Erro ao gerar relatório: {e}", exc_info=True)
            return ToolOutput(
                tool_name=self.name,
                status="error",
                result={},
                message=str(e)
            )
    
    def _format_markdown(self, report: dict) -> str:
        """Formatar relatório como Markdown"""
        md = f"# Data Pipeline Report\n\nGerado em: {report['generated_at']}\n\n"
        
        for section_name, section_data in report["sections"].items():
            md += f"## {section_name}\n\n"
            md += f"```json\n{json.dumps(section_data, indent=2, default=str)}\n```\n\n"
        
        return md


# ── ReAct Agent ────────────────────────────────────────────────────────────

@dataclass
class Thought:
    """Pensamento do agente (Reasoning)"""
    step: int
    reasoning: str
    next_action: str


@dataclass
class Action:
    """Ação tomada pelo agente"""
    step: int
    tool: str
    params: Dict[str, Any]


@dataclass
class Observation:
    """Observação do resultado da ação"""
    step: int
    tool_output: ToolOutput


class ReActAgent:
    """
    Agente ReAct que raciocina e executa tools iterativamente.
    
    Ciclo:
        Thought → Action → Observation → (repeat)
    """
    
    def __init__(self, max_iterations: int = 10):
        """
        Inicializar agente.
        
        Args:
            max_iterations: Máximo de iterações antes de parar
        """
        self.max_iterations = max_iterations
        self.step = 0
        self.history: List[Dict[str, Any]] = []
        
        # Registrar tools
        self.tools = {
            "read_project_files": ReadProjectFilesTool(),
            "execute_pipeline": ExecutePipelineTool(),
            "validate_golden_set": ValidateGoldenSetTool(),
            "generate_report": GenerateReportTool(),
        }
        
        log.info(f"ReAct Agent inicializado com {len(self.tools)} tools")
    
    def get_tools_description(self) -> str:
        """Retornar descrição de todas as tools disponíveis"""
        desc = "Ferramentas disponíveis:\n"
        for tool_name, tool in self.tools.items():
            desc += f"  - {tool_name}: {tool.description}\n"
        return desc
    
    def think(self, current_state: str) -> Thought:
        """
        Etapa 1: REASONING - Raciocinar sobre o que fazer
        
        Args:
            current_state: Estado atual da conversa
        """
        self.step += 1
        log.info(f"[Step {self.step}] Reasoning...")
        
        # Aqui em produção você teria chamada a LLM
        # Por agora, simulamos raciocínio com lógica
        
        thought = Thought(
            step=self.step,
            reasoning=f"Analisando requisição: {current_state}",
            next_action="execute_pipeline"  # Default
        )
        
        log.info(f"[Step {self.step}] Pensamento: {thought.reasoning}")
        return thought
    
    def act(self, action_name: str, params: Dict[str, Any] = None) -> ToolOutput:
        """
        Etapa 2: ACTION - Executar uma tool
        
        Args:
            action_name: Nome da tool a executar
            params: Parâmetros para a tool
        """
        log.info(f"[Step {self.step}] Acting...")
        
        if action_name not in self.tools:
            log.error(f"Tool desconhecida: {action_name}")
            return ToolOutput(
                tool_name=action_name,
                status="error",
                result={},
                message=f"Tool não encontrada: {action_name}"
            )
        
        tool = self.tools[action_name]
        params = params or {}
        
        log.info(f"[Step {self.step}] Executando tool: {action_name}")
        log.info(f"[Step {self.step}] Parâmetros: {params}")
        
        output = tool.execute(**params)
        
        log.info(f"[Step {self.step}] Resultado: {output.status}")
        return output
    
    def observe(self, tool_output: ToolOutput) -> Observation:
        """
        Etapa 3: OBSERVE - Observar resultado da ação
        
        Args:
            tool_output: Output da tool
        """
        log.info(f"[Step {self.step}] Observing...")
        
        observation = Observation(
            step=self.step,
            tool_output=tool_output
        )
        
        log.info(f"[Step {self.step}] Observação: {tool_output.message}")
        
        # Registrar no histórico
        self.history.append({
            "step": self.step,
            "action": tool_output.tool_name,
            "status": tool_output.status,
            "timestamp": tool_output.timestamp
        })
        
        return observation
    
    def run(self, task: str) -> Dict[str, Any]:
        """
        Executar agente para completar uma tarefa.
        
        Args:
            task: Descrição da tarefa
        
        Returns:
            Resultado final da execução
        """
        log.info("=" * 80)
        log.info(f"INICIANDO AGENT PARA TAREFA: {task}")
        log.info("=" * 80)
        
        # Mapeamento de tarefas para sequências de ações
        task_actions = {
            "pipeline_completo": [
                ("execute_pipeline", {"stage": "fetch", "mode": "incremental"}),
                ("execute_pipeline", {"stage": "process"}),
                ("execute_pipeline", {"stage": "validate"}),
                ("generate_report", {"report_type": "full"})
            ],
            "validar_dados": [
                ("validate_golden_set", {"data_source": "processed"}),
                ("generate_report", {"report_type": "validation"})
            ],
            "gerar_relatorio": [
                ("generate_report", {"report_type": "full", "output_format": "json"})
            ],
            "ingestao": [
                ("execute_pipeline", {"stage": "fetch", "mode": "incremental"})
            ]
        }
        
        # Encontrar ações para a tarefa
        actions = task_actions.get(task, [])
        
        if not actions:
            log.warning(f"Tarefa desconhecida: {task}")
            return {"status": "error", "message": f"Tarefa desconhecida: {task}"}
        
        results = []
        
        for action_name, params in actions:
            if self.step >= self.max_iterations:
                log.warning(f"Máximo de iterações atingido: {self.max_iterations}")
                break
            
            # Cycle ReAct
            thought = self.think(f"Executar {action_name}")
            output = self.act(action_name, params)
            observation = self.observe(output)
            
            results.append({
                "action": action_name,
                "output": output.result,
                "status": output.status
            })
            
            # Parar se error crítico
            if output.status == "error":
                log.error(f"Erro crítico em {action_name}, parando")
                break
        
        final_result = {
            "task": task,
            "total_steps": self.step,
            "results": results,
            "status": "completed",
            "history": self.history
        }
        
        log.info("=" * 80)
        log.info(f"AGENT COMPLETADO: {self.step} steps executados")
        log.info("=" * 80)
        
        return final_result
    
    def get_history(self) -> List[Dict[str, Any]]:
        """Retornar histórico de execução"""
        return self.history
    
    def reset(self) -> None:
        """Resetar agent para novo run"""
        self.step = 0
        self.history = []
        log.info("Agent resetado")


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Criar agent
    agent = ReActAgent(max_iterations=10)
    
    # Mostrar tools disponíveis
    print("\n" + agent.get_tools_description())
    
    # Executar tarefas de exemplo
    print("\n" + "=" * 80)
    print("EXEMPLO 1: Validar dados contra golden_set")
    print("=" * 80 + "\n")
    
    result = agent.run("validar_dados")
    print(json.dumps(result, indent=2, default=str))
    
    # Reset para próxima tarefa
    agent.reset()
    
    print("\n" + "=" * 80)
    print("EXEMPLO 2: Gerar relatório completo")
    print("=" * 80 + "\n")
    
    result = agent.run("gerar_relatorio")
    print(json.dumps(result, indent=2, default=str))
