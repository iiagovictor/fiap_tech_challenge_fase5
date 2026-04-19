"""
Testes para ReAct Agent

Cobre:
- Tools individuais
- Ciclo ReAct (Reason → Act → Observe)
- Sequências de execução
- Tratamento de erros
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.react_agent import (
    ReActAgent,
    ReadProjectFilesTool,
    ExecutePipelineTool,
    ValidateGoldenSetTool,
    GenerateReportTool,
    ToolOutput,
)


# ── Testes: Tools Individuais ──────────────────────────────────────────────

class TestReadProjectFilesTool:
    """Testes para ReadProjectFilesTool"""
    
    def test_tool_has_properties(self):
        """Tool deve ter nome e descrição"""
        tool = ReadProjectFilesTool()
        assert tool.name == "read_project_files"
        assert len(tool.description) > 0
    
    def test_read_config_file(self):
        """Deve conseguir ler arquivos de config"""
        tool = ReadProjectFilesTool()
        result = tool.execute(file_path="configs/model_config.yaml")
        
        assert isinstance(result, ToolOutput)
        assert result.tool_name == "read_project_files"
    
    def test_read_nonexistent_file(self):
        """Deve retornar erro para arquivo que não existe"""
        tool = ReadProjectFilesTool()
        result = tool.execute(file_path="nonexistent.txt")
        
        assert result.status == "error"
        assert result.message != ""


class TestExecutePipelineTool:
    """Testes para ExecutePipelineTool"""
    
    def test_tool_properties(self):
        """Tool deve ter propriedades corretas"""
        tool = ExecutePipelineTool()
        assert tool.name == "execute_pipeline"
        assert len(tool.description) > 0
    
    def test_invalid_stage(self):
        """Deve retornar erro para stage inválida"""
        tool = ExecutePipelineTool()
        result = tool.execute(stage="invalid_stage")
        
        assert result.status == "error"


class TestValidateGoldenSetTool:
    """Testes para ValidateGoldenSetTool"""
    
    def test_tool_properties(self):
        """Tool deve ter propriedades corretas"""
        tool = ValidateGoldenSetTool()
        assert tool.name == "validate_golden_set"
        assert len(tool.description) > 0
    
    def test_invalid_source(self):
        """Deve retornar erro para fonte inválida"""
        tool = ValidateGoldenSetTool()
        result = tool.execute(data_source="invalid")
        
        assert result.status == "error"


class TestGenerateReportTool:
    """Testes para GenerateReportTool"""
    
    def test_tool_properties(self):
        """Tool deve ter propriedades corretas"""
        tool = GenerateReportTool()
        assert tool.name == "generate_report"
        assert len(tool.description) > 0
    
    def test_generate_report_success(self):
        """Deve gerar relatório com sucesso"""
        tool = GenerateReportTool()
        result = tool.execute(report_type="summary", output_format="json")
        
        assert result.status == "success"
        assert isinstance(result.result, dict)


# ── Testes: ReAct Agent ────────────────────────────────────────────────────

class TestReActAgent:
    """Testes para ReActAgent"""
    
    def test_agent_initialization(self):
        """Agent deve ser inicializado corretamente"""
        agent = ReActAgent(max_iterations=5)
        
        assert agent.max_iterations == 5
        assert len(agent.tools) >= 3
        assert agent.step == 0
        assert len(agent.history) == 0
    
    def test_agent_has_required_tools(self):
        """Agent deve ter tools obrigatórias"""
        agent = ReActAgent()
        
        required_tools = [
            "read_project_files",
            "execute_pipeline",
            "validate_golden_set",
            "generate_report"
        ]
        
        for tool_name in required_tools:
            assert tool_name in agent.tools
    
    def test_get_tools_description(self):
        """Deve retornar descrição de tools"""
        agent = ReActAgent()
        desc = agent.get_tools_description()
        
        assert len(desc) > 0
        assert "read_project_files" in desc
        assert "execute_pipeline" in desc
    
    def test_think_returns_thought(self):
        """Etapa think deve retornar pensamento"""
        agent = ReActAgent()
        thought = agent.think("Testar sistema")
        
        assert thought.step > 0
        assert thought.reasoning != ""
        assert thought.next_action != ""
    
    def test_act_with_valid_tool(self):
        """Etapa act com tool válida"""
        agent = ReActAgent()
        result = agent.act("generate_report", {"report_type": "summary"})
        
        assert isinstance(result, ToolOutput)
        assert result.tool_name == "generate_report"
    
    def test_act_with_invalid_tool(self):
        """Etapa act com tool inválida"""
        agent = ReActAgent()
        result = agent.act("nonexistent_tool")
        
        assert result.status == "error"
        assert "desconhecida" in result.message.lower() or "not found" in result.message.lower()
    
    def test_observe_adds_to_history(self):
        """Etapa observe deve adicionar ao histórico"""
        agent = ReActAgent()
        agent.act("generate_report")
        
        assert len(agent.history) > 0
        assert agent.history[0]["status"] != ""
    
    def test_cycle_react(self):
        """Ciclo ReAct completo: Reason → Act → Observe"""
        agent = ReActAgent()
        
        thought = agent.think("Testar")
        output = agent.act("generate_report")
        observation = agent.observe(output)
        
        assert thought.step > 0
        assert output.status != ""
        assert observation.step > 0
    
    def test_reset_agent(self):
        """Reset deve limpar histórico e step"""
        agent = ReActAgent()
        agent.step = 5
        agent.history = [{"test": "data"}]
        
        agent.reset()
        
        assert agent.step == 0
        assert len(agent.history) == 0


# ── Testes: Task Execution ────────────────────────────────────────────────

class TestReActAgentTasks:
    """Testes para execução de tarefas"""
    
    def test_run_gerar_relatorio_task(self):
        """Deve executar tarefa de gerar relatório"""
        agent = ReActAgent()
        result = agent.run("gerar_relatorio")
        
        assert result["status"] == "completed"
        assert result["task"] == "gerar_relatorio"
        assert result["total_steps"] > 0
        assert len(result["results"]) > 0
    
    def test_run_validar_dados_task(self):
        """Deve executar tarefa de validar dados"""
        agent = ReActAgent()
        result = agent.run("validar_dados")
        
        assert result["status"] == "completed"
        assert result["task"] == "validar_dados"
    
    def test_run_ingestao_task(self):
        """Deve executar tarefa de ingestão"""
        agent = ReActAgent()
        result = agent.run("ingestao")
        
        assert result["status"] == "completed"
        assert result["task"] == "ingestao"
    
    def test_run_unknown_task(self):
        """Deve retornar erro para tarefa desconhecida"""
        agent = ReActAgent()
        result = agent.run("unknown_task")
        
        assert result["status"] == "error"
    
    def test_run_respects_max_iterations(self):
        """Deve respeitar máximo de iterações"""
        agent = ReActAgent(max_iterations=2)
        result = agent.run("pipeline_completo")
        
        # Deve parar antes de completar todas as ações
        assert result["total_steps"] <= agent.max_iterations


# ── Testes: Output Structure ───────────────────────────────────────────────

class TestToolOutput:
    """Testes para estrutura de ToolOutput"""
    
    def test_tool_output_serializable(self):
        """ToolOutput deve ser serializável"""
        import json
        
        output = ToolOutput(
            tool_name="test_tool",
            status="success",
            result={"key": "value"},
            message="Test message"
        )
        
        # Deve ser convertível para JSON
        json_str = json.dumps(output.__dict__, default=str)
        assert len(json_str) > 0
    
    def test_tool_output_has_timestamp(self):
        """ToolOutput deve ter timestamp"""
        output = ToolOutput(
            tool_name="test",
            status="success",
            result={},
            message="test"
        )
        
        assert output.timestamp != ""


# ── Integration Tests ──────────────────────────────────────────────────────

class TestReActAgentIntegration:
    """Testes de integração do agent"""
    
    def test_full_workflow(self):
        """Teste completo do workflow"""
        agent = ReActAgent(max_iterations=10)
        
        # Executar tarefa completa
        result = agent.run("gerar_relatorio")
        
        assert result["status"] in ["completed", "error"]
        assert "total_steps" in result
        assert "results" in result
        assert "history" in result
    
    def test_multiple_tasks_sequential(self):
        """Executar múltiplas tarefas em sequência"""
        agent = ReActAgent()
        
        results = []
        tasks = ["validar_dados", "gerar_relatorio"]
        
        for task in tasks:
            agent.reset()
            result = agent.run(task)
            results.append(result)
        
        assert len(results) == 2
        assert all(r["status"] == "completed" for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
