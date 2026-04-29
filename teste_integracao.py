import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool

# 1. Carrega as configurações do arquivo .env
load_dotenv()

# 2. Definição da ferramenta
@tool
def execute_pipeline(stage: str, mode: str = "incremental"):
    """Executa as etapas do pipeline de dados: fetch, process ou validate."""
    return f"Status: Pipeline na etapa '{stage}' rodando no modo '{mode}'."

# 3. Configuração do Gemini 
# Usando o modelo que apareceu na lista (gemini-2.5-flash-lite)
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    temperature=0
)

# Vincula a ferramenta ao modelo
llm_with_tools = model.bind_tools([execute_pipeline])

# 4. Execução do teste
def run_agent_test():
    print("Enviando tarefa para o Gemini...")
    try:
        task = "Preciso que você execute o pipeline na etapa de processamento."
        response = llm_with_tools.invoke(task)
        
        print("\n--- RESPOSTA ---")
        if response.tool_calls:
            print("Sucesso! O modelo decidiu chamar a ferramenta:")
            for call in response.tool_calls:
                print(f"Nome da Tool: {call['name']}")
                print(f"Argumentos: {call['args']}")
        else:
            print("Resposta do modelo:")
            print(response.content)
            
    except Exception as e:
        print(f"\nErro ao rodar o teste: {e}")

if __name__ == "__main__":
    run_agent_test()