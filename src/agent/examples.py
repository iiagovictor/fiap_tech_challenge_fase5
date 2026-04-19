"""
Exemplos de uso do ReAct Agent

Demonstra os padrões de Reasoning, Acting e Observation
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.react_agent import ReActAgent


def example_1_full_pipeline():
    """Exemplo 1: Executar pipeline completo"""
    print("\n" + "=" * 80)
    print("EXEMPLO 1: Executar Pipeline Completo")
    print("=" * 80)
    print("Tarefa: Fazer ingestão, processar e validar dados\n")
    
    agent = ReActAgent(max_iterations=10)
    
    result = agent.run("pipeline_completo")
    
    print("\nResultado:")
    print(json.dumps(result, indent=2, default=str))
    
    return result


def example_2_validate_only():
    """Exemplo 2: Apenas validar dados"""
    print("\n" + "=" * 80)
    print("EXEMPLO 2: Validar Dados Contra Golden Set")
    print("=" * 80)
    print("Tarefa: Validar dados processados\n")
    
    agent = ReActAgent(max_iterations=5)
    
    result = agent.run("validar_dados")
    
    print("\nResultado:")
    print(json.dumps(result, indent=2, default=str))
    
    return result


def example_3_generate_report():
    """Exemplo 3: Gerar relatório"""
    print("\n" + "=" * 80)
    print("EXEMPLO 3: Gerar Relatório de Qualidade")
    print("=" * 80)
    print("Tarefa: Gerar relatório completo\n")
    
    agent = ReActAgent(max_iterations=5)
    
    result = agent.run("gerar_relatorio")
    
    print("\nResultado:")
    print(json.dumps(result, indent=2, default=str))
    
    return result


def example_4_custom_sequence():
    """Exemplo 4: Sequência customizada"""
    print("\n" + "=" * 80)
    print("EXEMPLO 4: Sequência Customizada")
    print("=" * 80)
    print("Demonstra o ciclo ReAct manualmente\n")
    
    agent = ReActAgent(max_iterations=3)
    
    print("Step 1: Ler arquivos de configuração")
    print("-" * 40)
    result1 = agent.act("read_project_files", {"pattern": "configs/*.yaml"})
    agent.observe(result1)
    print(f"Status: {result1.status}")
    print(f"Mensagem: {result1.message}\n")
    
    agent.reset()
    agent.step = 0
    
    print("Step 2: Executar validação")
    print("-" * 40)
    result2 = agent.act("validate_golden_set", {"data_source": "processed"})
    agent.observe(result2)
    print(f"Status: {result2.status}")
    print(f"Mensagem: {result2.message}\n")
    
    agent.reset()
    agent.step = 0
    
    print("Step 3: Gerar relatório")
    print("-" * 40)
    result3 = agent.act("generate_report", {"report_type": "summary"})
    agent.observe(result3)
    print(f"Status: {result3.status}")
    print(f"Mensagem: {result3.message}\n")
    
    print("Histórico:")
    print(json.dumps(agent.get_history(), indent=2, default=str))


def example_5_display_tools():
    """Exemplo 5: Mostrar tools disponíveis"""
    print("\n" + "=" * 80)
    print("EXEMPLO 5: Tools Disponíveis no Agent")
    print("=" * 80)
    
    agent = ReActAgent()
    print(agent.get_tools_description())


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        if example_num == "1":
            example_1_full_pipeline()
        elif example_num == "2":
            example_2_validate_only()
        elif example_num == "3":
            example_3_generate_report()
        elif example_num == "4":
            example_4_custom_sequence()
        elif example_num == "5":
            example_5_display_tools()
        else:
            print("Exemplo não encontrado. Use: 1, 2, 3, 4 ou 5")
    else:
        print("ReAct Agent - Exemplos de Uso")
        print("=" * 80)
        print("\nExecute um exemplo específico:")
        print("  python examples.py 1    # Pipeline completo")
        print("  python examples.py 2    # Validar dados")
        print("  python examples.py 3    # Gerar relatório")
        print("  python examples.py 4    # Sequência customizada")
        print("  python examples.py 5    # Mostrar tools")
        print()
