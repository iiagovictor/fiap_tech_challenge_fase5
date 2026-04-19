"""
ReAct Agent Package

Módulo principal para Agentes com Raciocínio e Execução de Tools.
"""

from .react_agent import (
    ReActAgent,
    Tool,
    ToolOutput,
    ToolInput,
    Thought,
    Action,
    Observation,
    ReadProjectFilesTool,
    ExecutePipelineTool,
    ValidateGoldenSetTool,
    GenerateReportTool,
)

__all__ = [
    "ReActAgent",
    "Tool",
    "ToolOutput",
    "ToolInput",
    "Thought",
    "Action",
    "Observation",
    "ReadProjectFilesTool",
    "ExecutePipelineTool",
    "ValidateGoldenSetTool",
    "GenerateReportTool",
]

__version__ = "1.0.0"
