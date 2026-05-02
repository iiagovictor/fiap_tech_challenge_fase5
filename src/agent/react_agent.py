"""
ReAct (Reasoning + Acting) agent for financial analysis.

Implements the ReAct pattern:
1. Thought: Reason about what to do next
2. Action: Execute a tool or search for information
3. Observation: Observe the result
4. Repeat until answer is found

Uses LiteLLM for cloud-agnostic LLM access.
"""

import json
import logging
import os
import re
from typing import Any

from src.agent.rag_pipeline import get_rag_pipeline
from src.agent.tools import TOOLS
from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Export API keys to environment variables for LiteLLM (must be done before importing litellm)
if settings.google_api_key:
    # LiteLLM for Gemini accepts both GOOGLE_API_KEY and GEMINI_API_KEY
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key
    os.environ["GEMINI_API_KEY"] = settings.google_api_key
    logger.info(f"✅ Google/Gemini API key exported: {settings.google_api_key[:20]}...")
else:
    logger.warning("⚠️ No Google API key found in settings")

if settings.openai_api_key:
    os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    logger.info("✅ OpenAI API key exported to environment")

if settings.groq_api_key:
    os.environ["GROQ_API_KEY"] = settings.groq_api_key
    logger.info(f"✅ Groq API key exported: {settings.groq_api_key[:20]}...")
else:
    logger.warning("⚠️ No Groq API key found in settings")

# Import litellm AFTER setting environment variables
from litellm import completion  # noqa: E402


class ReactAgent:
    """
    ReAct agent for answering financial questions with tools and RAG.

    Follows the ReAct pattern: Thought -> Action -> Observation -> Answer
    """

    def __init__(self) -> None:
        # Initialize RAG pipeline (optional - may fail if ChromaDB unavailable or empty)
        try:
            self.rag = get_rag_pipeline()
            logger.info("✅ RAG pipeline initialized")
        except Exception as e:
            # RAG is optional, don't log as error if collection is empty
            if "404" in str(e) or "Not Found" in str(e):
                logger.info("ℹ️  RAG collection empty - will work without RAG context")
            else:
                logger.warning(f"⚠️ RAG pipeline unavailable: {e}")
            self.rag = None

        self.tools = {tool["name"]: tool["function"] for tool in TOOLS}
        self.max_iterations = 5

    def _build_system_prompt(self) -> str:
        """Build system prompt with tool descriptions."""
        tool_descriptions = []
        for tool in TOOLS:
            params = ", ".join([f"{k}: {v['type']}" for k, v in tool["parameters"].items()])
            tool_descriptions.append(f"- {tool['name']}({params}): {tool['description']}")

        tools_text = "\n".join(tool_descriptions)

        return f"""You are a financial analysis assistant with access to real-time
stock market data through specialized tools.

CRITICAL RULES:
1. You MUST use tools to get real data - do NOT make up or guess numbers
2. For questions about stocks, ALWAYS call the appropriate tool first
3. For prediction questions (probabilidade, valorizar, vai subir, previsão),
   you MUST use predict_stock_direction
4. Only provide an Answer after you have executed tools and received real data

Available Tools:
{tools_text}

RESPONSE FORMAT (MANDATORY):
Thought: [Explain what tool you need to use and why]
Action: [tool_name(param1="value1", param2="value2")]

Then wait for Observation with the result.

After receiving the Observation:
Thought: [Analyze the result]
Action: [Call another tool if needed, OR proceed to Answer if you have enough data]

When you have all data:
Answer: [Provide clear answer using the REAL DATA from tools]

EXAMPLE 1 - Prediction Question:
User: "Qual \u00e9 a probabilidade do ITUB4.SA valorizar?"

Thought: This is a prediction question, I must use predict_stock_direction
to get the model's forecast.
Action: predict_stock_direction(ticker="ITUB4.SA")

[Wait for Observation with prediction data]

Thought: I received the prediction. Now I can provide a complete answer with the real probability.
Answer: De acordo com o modelo LSTM, a probabilidade de ITUB4.SA valorizar
no pr\u00f3ximo dia \u00fatil \u00e9 de [X]%, com recomenda\u00e7\u00e3o [COMPRA/VENDA/NEUTRO].

EXAMPLE 2 - Price History:
User: "Qual a cota\u00e7\u00e3o da PETR4.SA?"

Thought: I need current price data, so I'll use get_stock_price_history.
Action: get_stock_price_history(ticker="PETR4.SA", period="1d")

[Wait for Observation]

Thought: I have the current price from the tool.
Answer: A cotação atual da PETR4.SA é R$ [X], com variação de [Y]% no dia.

IMPORTANT: Never invent numbers - always use tools to get real data first!
"""

    def _call_llm(self, messages: list[dict]) -> str:
        """Call LLM via LiteLLM with retry logic."""
        try:
            # Double-check API keys are in environment (safety measure)
            if settings.google_api_key:
                if "GOOGLE_API_KEY" not in os.environ:
                    os.environ["GOOGLE_API_KEY"] = settings.google_api_key
                    logger.warning("⚠️ Had to re-export GOOGLE_API_KEY")
                if "GEMINI_API_KEY" not in os.environ:
                    os.environ["GEMINI_API_KEY"] = settings.google_api_key
                    logger.warning("⚠️ Had to re-export GEMINI_API_KEY")

            logger.info(f"Calling LLM with model: {settings.llm_model}")
            logger.debug(
                f"API keys in env: GOOGLE={('GOOGLE_API_KEY' in os.environ)},"
                f" GEMINI={('GEMINI_API_KEY' in os.environ)}"
            )

            # Try primary model
            try:
                response = completion(
                    model=settings.llm_model,
                    messages=messages,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                    api_base=settings.llm_base_url if "ollama" in settings.llm_model else None,
                )
                return response.choices[0].message.content
            except Exception as primary_error:
                # If Gemini returns 503 (high demand), try a fallback model
                if "503" in str(primary_error) or "UNAVAILABLE" in str(primary_error):
                    logger.warning("⚠️ Primary model unavailable (503), trying fallback model...")
                    # Try gemini-1.5-flash as fallback (faster, more available)
                    fallback_model = "gemini/gemini-1.5-flash"
                    response = completion(
                        model=fallback_model,
                        messages=messages,
                        temperature=settings.llm_temperature,
                        max_tokens=settings.llm_max_tokens,
                    )
                    logger.info(f"✅ Fallback model {fallback_model} succeeded")
                    return response.choices[0].message.content
                else:
                    raise primary_error

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise  # Re-raise to trigger fallback

    def _parse_action(self, text: str) -> tuple[str | None, dict]:
        """
        Parse action from agent output.

        Expected format: Action: tool_name(param1="value1", param2="value2")
        """
        action_pattern = r"Action:\s*(\w+)\((.*?)\)"
        match = re.search(action_pattern, text, re.IGNORECASE)

        if not match:
            return None, {}

        tool_name = match.group(1)
        params_str = match.group(2)

        # Parse parameters
        params = {}
        if params_str:
            # Simple parameter parsing (handles strings and lists)
            param_pattern = r'(\w+)=(["\'])(.*?)\2'
            for param_match in re.finditer(param_pattern, params_str):
                param_name = param_match.group(1)
                param_value = param_match.group(3)
                params[param_name] = param_value

        return tool_name, params

    def _execute_tool(self, tool_name: str, params: dict) -> Any:  # noqa: ANN401
        """Execute a tool with given parameters."""
        if tool_name not in self.tools:
            return f"Error: Tool '{tool_name}' not found"

        try:
            tool_func = self.tools[tool_name]
            result = tool_func(**params)
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return f"Error: {str(e)}"

    def query(self, user_query: str) -> dict:
        """
        Process a user query using the ReAct pattern.

        Args:
            user_query: User's question

        Returns:
            Dictionary with answer, reasoning steps, and tool calls
        """
        logger.info(f"Processing query: {user_query}")

        # Retrieve relevant context from RAG (if available)
        if self.rag:
            try:
                context = self.rag.retrieve_context(user_query, n_results=2)
                logger.info("✅ Retrieved context from RAG")
            except Exception as e:
                logger.warning(f"⚠️ RAG retrieval failed: {e}")
                context = "No additional context available."
        else:
            context = "No additional context available."

        # Build messages
        system_prompt = self._build_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Context from knowledge base:\n{context}\n\n" f"User Question: {user_query}"
                ),
            },
        ]

        reasoning_steps = []
        tool_calls = []

        for iteration in range(self.max_iterations):
            logger.info(f"🔄 Iteration {iteration + 1}/{self.max_iterations}")

            # Get LLM response
            response = self._call_llm(messages)
            reasoning_steps.append(response)

            # Log the raw response for debugging
            logger.debug(f"📝 LLM Response:\n{response}")

            # Check if answer is provided
            if "Answer:" in response:
                # Extract final answer
                answer = response.split("Answer:")[-1].strip()
                logger.info(f"✅ Agent provided final answer after {iteration + 1} iteration(s)")
                logger.info(f"🔧 Tools called: {len(tool_calls)}")

                return {
                    "query": user_query,
                    "answer": answer,
                    "reasoning_steps": reasoning_steps,
                    "tool_calls": tool_calls,
                    "iterations": iteration + 1,
                }

            # Parse and execute action
            tool_name, params = self._parse_action(response)

            if tool_name:
                logger.info(f"🔧 Executing tool: {tool_name} with params {params}")
                tool_result = self._execute_tool(tool_name, params)
                tool_calls.append({"tool": tool_name, "params": params, "result": tool_result})
                logger.info(f"✅ Tool {tool_name} executed successfully")

                # Add observation to messages
                observation = f"Observation: {json.dumps(tool_result, indent=2)}"
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": observation})
            else:
                # No action found, ask LLM to continue
                logger.warning("⚠️ No action found in response. Asking LLM to continue...")
                messages.append({"role": "assistant", "content": response})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Please continue with your analysis" " or provide the final answer."
                        ),
                    }
                )

        # Max iterations reached
        logger.warning("Max iterations reached without final answer")
        return {
            "query": user_query,
            "answer": (
                "I apologize, but I wasn't able to complete the analysis within"
                " the allowed steps. Please try rephrasing your question."
            ),
            "reasoning_steps": reasoning_steps,
            "tool_calls": tool_calls,
            "iterations": self.max_iterations,
            "error": "max_iterations_reached",
        }


def get_agent() -> ReactAgent:
    """Get ReAct agent instance."""
    return ReactAgent()


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Test agent (requires Ollama running locally)
    agent = get_agent()

    # Test query
    print("\n🤖 Testing ReAct Agent\n")
    query = "What is the current technical analysis for ITUB4.SA?"

    print(f"Query: {query}\n")
    result = agent.query(query)

    print(f"\nAnswer: {result['answer']}")
    print(f"\nTool Calls: {len(result['tool_calls'])}")
    print(f"Iterations: {result['iterations']}")
