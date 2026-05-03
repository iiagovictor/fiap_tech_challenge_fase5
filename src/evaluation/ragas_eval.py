"""
RAGAS Evaluation Script

This script evaluates RAG (Retrieval-Augmented Generation) systems using RAGAS metrics:
- Faithfulness: Measures how faithful the generated answer is to the retrieved context.
- Answer Relevancy: Measures how relevant the generated answer is to the question.
- Context Precision: Measures how precise the retrieved context is.
- Context Recall: Measures how well the retrieved context covers the ground truth.

The evaluation is executed using Ollama instead of OpenAI.
"""

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import Any

import pandas as pd
from ragas import evaluate
from ragas.evaluation import EvaluationDataset
from ragas.llms.base import InstructorBaseRagasLLM, InstructorTypeVar
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecisionWithReference,
    ContextRecall,
    Faithfulness,
)


class OllamaRagasLLM(InstructorBaseRagasLLM):
    """Instructor-style RAGAS LLM wrapper for Ollama HTTP API."""

    def __init__(
        self,
        model: str,
        endpoint: str = "http://127.0.0.1:11434",
        temperature: float = 0.1,
        system_prompt: str | None = None,
        request_kwargs: dict[str, Any] | None = None,
    ) -> None:
        self.model = model
        self.endpoint = endpoint.rstrip("/")
        self.temperature = temperature
        self.system_prompt = system_prompt
        self.request_kwargs = request_kwargs or {}

    def _build_prompt(self, prompt: str) -> str:
        if self.system_prompt:
            return f"{self.system_prompt}\n\n{prompt}"
        return prompt

    def _send_request(self, prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": self.temperature,
            **self.request_kwargs,
        }
        request_body = json.dumps(payload).encode("utf-8")
        request_url = f"{self.endpoint}/api/generate"

        request = urllib.request.Request(
            request_url,
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Ollama API returned HTTP {exc.code}: {exc.read().decode(errors='ignore')}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                "Unable to connect to Ollama. Ensure the server is running "
                "and OLLAMA_API_URL is correct."
            ) from exc

    def _extract_text(self, response: object) -> str:
        if isinstance(response, dict):
            if "choices" in response and response["choices"]:
                first = response["choices"][0]
                if isinstance(first, dict) and "text" in first:
                    return first["text"]
            if "text" in response and isinstance(response["text"], str):
                return response["text"]
            if "result" in response:
                result = response["result"]
                if isinstance(result, str):
                    return result
                if isinstance(result, dict) and "text" in result:
                    return result["text"]
            if "output" in response and isinstance(response["output"], str):
                return response["output"]

        raise ValueError("Cannot parse Ollama response body into text.")

    def _parse_structured_output(
        self, text: str, response_model: type[InstructorTypeVar]
    ) -> InstructorTypeVar:
        trimmed = text.strip()
        if not trimmed:
            raise ValueError("Ollama returned an empty response.")

        try:
            parsed = json.loads(trimmed)
        except json.JSONDecodeError as exc:
            start = trimmed.find("{")
            end = trimmed.rfind("}")
            if start == -1 or end == -1:
                raise RuntimeError("Ollama response could not be parsed as JSON.") from exc
            parsed = json.loads(trimmed[start : end + 1])

        return response_model.parse_obj(parsed)

    def generate(self, prompt: str, response_model: type[InstructorTypeVar]) -> InstructorTypeVar:
        response = self._send_request(self._build_prompt(prompt))
        prompt_text = self._extract_text(response)
        return self._parse_structured_output(prompt_text, response_model)

    async def agenerate(
        self, prompt: str, response_model: type[InstructorTypeVar]
    ) -> InstructorTypeVar:
        return await asyncio.to_thread(self.generate, prompt, response_model)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model!r}, endpoint={self.endpoint!r})"


def build_sample_dataset() -> EvaluationDataset:
    samples = [
        {
            "user_input": "What is the main objective of the FIAP Tech Challenge Fase 5 project?",
            "retrieved_contexts": [
                "FIAP Tech Challenge Fase 5 is a cloud-agnostic MLOps/LLMOps platform "
                "for financial data analytics, monitoring, and model serving."
            ],
            "response": (
                "The project aims to build a cloud-agnostic MLOps/LLMOps platform "
                "for financial analysis, model serving, and drift-aware monitoring."
            ),
            "reference": (
                "The project builds a cloud-agnostic MLOps/LLMOps platform for financial "
                "analysis using RAG, monitoring, and API serving capabilities."
            ),
        },
        {
            "user_input": "How does the RAG pipeline work in this project?",
            "retrieved_contexts": [
                "The RAG pipeline retrieves documents from ChromaDB and uses a language "
                "model to generate answers based on retrieved context."
            ],
            "response": (
                "The RAG pipeline retrieves relevant documents from the vector store "
                "and uses an LLM to generate context-aware answers."
            ),
            "reference": (
                "The RAG pipeline retrieves information from ChromaDB vector database and "
                "uses language models to generate context-aware answers about the system "
                "and financial data."
            ),
        },
        {
            "user_input": "What is drift monitoring and how is it implemented?",
            "retrieved_contexts": [
                "Drift monitoring is implemented with Evidently to compare reference and "
                "current data distributions and detect drift in model inputs."
            ],
            "response": (
                "Drift monitoring compares historical data distributions with current "
                "inputs using Evidently to identify concept and data drift."
            ),
            "reference": (
                "Drift monitoring uses Evidently to detect data distribution changes, "
                "comparing reference datasets with current data to identify drift in "
                "ML model inputs and predictions."
            ),
        },
        {
            "user_input": "How can I use the API endpoints for prediction?",
            "retrieved_contexts": [
                "The FastAPI application serves endpoints for prediction, health checks, "
                "and drift monitoring."
            ],
            "response": (
                "Use the /predict endpoint with JSON payload to obtain model predictions, "
                "and /health to verify service status."
            ),
            "reference": (
                "The API provides REST endpoints for prediction, health monitoring, and "
                "drift detection, using FastAPI framework with proper validation and "
                "metrics collection."
            ),
        },
        {
            "user_input": "What is the role of the feature store in this system?",
            "retrieved_contexts": [
                "Feast stores and serves machine learning features in MinIO and "
                "coordinates metadata in the registry."
            ],
            "response": (
                "The feature store stores and serves features for training and inference, "
                "using Feast with MinIO as storage."
            ),
            "reference": (
                "The feature store uses Feast to manage ML features, storing them in MinIO "
                "with metadata in PostgreSQL, enabling both real-time and batch feature "
                "serving."
            ),
        },
    ]
    return EvaluationDataset.from_list(samples)


def main() -> None:
    ollama_url = os.getenv("OLLAMA_API_URL") or os.getenv("OLLAMA_URL") or "http://127.0.0.1:11434"
    ollama_model = os.getenv("OLLAMA_MODEL", "llama2")

    print(f"Using Ollama endpoint: {ollama_url}")
    print(f"Using Ollama model: {ollama_model}")

    llm = OllamaRagasLLM(model=ollama_model, endpoint=ollama_url)

    dataset = build_sample_dataset()
    print(f"Dataset created with {len(dataset.samples)} samples")
    sample_keys = list(dataset.samples[0].dict().keys())
    print(f"Dataset columns: {sample_keys}")

    metrics = [
        Faithfulness(llm=llm),
        AnswerRelevancy(llm=llm),
        ContextPrecisionWithReference(llm=llm),
        ContextRecall(llm=llm),
    ]
    print(f"Evaluating {len(metrics)} metrics: {[metric.name for metric in metrics]}")

    try:
        result = evaluate(dataset, metrics=metrics)
        print("Evaluation completed successfully!")
    except Exception as exc:
        print(f"Error during evaluation: {exc}")
        print("Please verify that Ollama is running and reachable at the configured endpoint.")
        print("Example: ollama serve --listen http://127.0.0.1:11434")
        return

    print("\nEvaluation Results:")
    print(result)

    result_dict = result.to_dict() if hasattr(result, "to_dict") else dict(result)

    if any(pd.isna(value) for value in result_dict.values()):
        print("\nWarning: Some metrics returned NaN values.")
        print("This might be due to:")
        print("- Ollama model output not being valid JSON")
        print("- Mismatch between sample fields and metric expectations")
        print("- Ollama server error or timeout")

    print("\nIndividual Scores:")
    for metric_name, value in result_dict.items():
        if pd.isna(value):
            print(f"{metric_name}: NaN")
        else:
            print(f"{metric_name}: {value:.4f}")


if __name__ == "__main__":
    main()
