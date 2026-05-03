"""
LLM-as-Judge evaluation for the financial LLM agent.

Evaluates agent responses against four criteria using an LLM as evaluator:

1. **Relevância** (Relevance)
   Is the answer directly relevant and responsive to the question asked?

2. **Fidelidade Técnica** (Technical Fidelity)
   Are the technical indicator claims accurate and consistent with the
   provided contexts (RSI values, MACD signals, moving averages, etc.)?

3. **Adequação para Decisão de Investimento** (Investment Decision Suitability)
   *Business criterion* — Is the answer useful for an investment decision,
   appropriately cautious, and does it include necessary disclaimers?

4. **Clareza e Fundamentação** (Clarity & Grounding)
   Is the answer clear, well-structured, and properly grounded in the
   data/indicators mentioned?

Each criterion is scored 1–5 by the LLM with a textual justification.
The overall score is the simple average of the four criterion scores.

Usage::

    from src.evaluation.llm_judge import LLMJudge

    judge = LLMJudge()
    result = judge.evaluate(
        query="A VALE3.SA está em sobrecompra?",
        answer="VALE3.SA está próxima da sobrecompra com RSI ~68.",
        contexts=["RSI próximo a 68", "Preço testando resistência anterior"],
        expected_answer="VALE3.SA está perto da zona de sobrecompra...",  # optional
    )
    print(result.overall_score)   # e.g. 4.25
    print(result.verdict)         # "PASS" | "FAIL"

"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from src.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── LiteLLM API key bootstrap (mirrors react_agent.py) ───────────────────────
if settings.google_api_key:
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
    os.environ.setdefault("GEMINI_API_KEY", settings.google_api_key)
if settings.openai_api_key:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
if settings.groq_api_key:
    os.environ.setdefault("GROQ_API_KEY", settings.groq_api_key)

# Import LiteLLM AFTER env vars are set
from litellm import completion  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

CRITERIA = [
    "relevancia",
    "fidelidade_tecnica",
    "adequacao_investimento",
    "clareza_e_fundamentacao",
]

CRITERIA_LABELS = {
    "relevancia": "Relevância",
    "fidelidade_tecnica": "Fidelidade Técnica",
    "adequacao_investimento": "Adequação para Decisão de Investimento",
    "clareza_e_fundamentacao": "Clareza e Fundamentação",
}

# Threshold below which a response is considered failing
PASS_THRESHOLD = 3.0


@dataclass
class CriterionResult:
    """Score and justification for a single evaluation criterion."""

    name: str
    label: str
    score: float  # 1–5
    justification: str


@dataclass
class JudgeResult:
    """Complete result of an LLM-as-judge evaluation."""

    query: str
    answer: str
    criteria: list[CriterionResult] = field(default_factory=list)
    overall_score: float = 0.0
    verdict: str = "UNKNOWN"  # "PASS" | "FAIL"
    model_used: str = ""
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "answer": self.answer,
            "overall_score": round(self.overall_score, 3),
            "verdict": self.verdict,
            "model_used": self.model_used,
            "error": self.error,
            "criteria": [
                {
                    "name": c.name,
                    "label": c.label,
                    "score": c.score,
                    "justification": c.justification,
                }
                for c in self.criteria
            ],
        }


# ─────────────────────────────────────────────────────────────────────────────
# Judge prompt
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
Você é um avaliador especialista em análise técnica do mercado financeiro brasileiro.
Sua tarefa é avaliar respostas de um assistente de IA sobre ações da B3.

Avalie a resposta em QUATRO critérios. Para cada critério, forneça:
- Uma pontuação de 1 a 5 (inteiro ou decimal com uma casa)
- Uma justificativa curta (1-2 frases)

ESCALA DE PONTUAÇÃO:
5 = Excelente — atende completamente ao critério
4 = Bom — atende ao critério com pequenas falhas
3 = Razoável — atende parcialmente
2 = Fraco — atende pouco ao critério
1 = Inaceitável — não atende ao critério

CRITÉRIOS:
1. relevancia: A resposta é diretamente relevante e responsiva à pergunta feita?
2. fidelidade_tecnica: As afirmações técnicas (RSI, MACD, médias móveis etc.) são
   consistentes com os contextos fornecidos?
3. adequacao_investimento: A resposta é útil para uma decisão de investimento,
   apropriadamente cautelosa e inclui os devidos disclaimers ou ressalvas?
4. clareza_e_fundamentacao: A resposta é clara, bem estruturada e fundamentada
   nos dados/indicadores mencionados?

RESPONDA APENAS COM JSON VÁLIDO no formato:
{
  "relevancia": {"score": <1-5>, "justification": "<texto>"},
  "fidelidade_tecnica": {"score": <1-5>, "justification": "<texto>"},
  "adequacao_investimento": {"score": <1-5>, "justification": "<texto>"},
  "clareza_e_fundamentacao": {"score": <1-5>, "justification": "<texto>"}
}

Não adicione nenhum texto fora do JSON.
"""


def _build_user_message(
    query: str,
    answer: str,
    contexts: list[str] | None,
    expected_answer: str | None,
) -> str:
    """Build the user message containing the evaluation request."""
    parts = [
        f"PERGUNTA DO USUÁRIO:\n{query}",
        f"\nRESPOSTA DO ASSISTENTE A AVALIAR:\n{answer}",
    ]
    if contexts:
        ctx_text = "\n".join(f"- {c}" for c in contexts)
        parts.append(f"\nCONTEXTOS FORNECIDOS AO ASSISTENTE:\n{ctx_text}")
    if expected_answer:
        parts.append(f"\nRESPOSTA ESPERADA (gabarito):\n{expected_answer}")
    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Main judge class
# ─────────────────────────────────────────────────────────────────────────────


class LLMJudge:
    """LLM-as-Judge evaluator for financial agent responses."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or settings.llm_model
        self._fallback_model = "gemini/gemini-1.5-flash"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        query: str,
        answer: str,
        contexts: list[str] | None = None,
        expected_answer: str | None = None,
    ) -> JudgeResult:
        """
        Evaluate a single agent response.

        Args:
            query: The user's original question.
            answer: The agent's response to evaluate.
            contexts: Optional list of context strings used by the agent.
            expected_answer: Optional gold-standard answer (improves judgment).

        Returns:
            JudgeResult with per-criterion scores and overall verdict.
        """
        result = JudgeResult(query=query, answer=answer, model_used=self.model)

        user_message = _build_user_message(query, answer, contexts, expected_answer)
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        try:
            raw_json = self._call_llm(messages)
            result = self._parse_response(raw_json, result)
        except Exception as exc:
            logger.error("LLM judge evaluation failed: %s", exc)
            result.error = str(exc)
            result.verdict = "ERROR"

        return result

    def evaluate_batch(
        self,
        entries: list[dict[str, Any]],
    ) -> list[JudgeResult]:
        """
        Evaluate a list of entries in sequence.

        Each entry must have: query, answer.
        Optional keys: contexts, expected_answer.

        Args:
            entries: List of dicts with evaluation data.

        Returns:
            List of JudgeResult objects.
        """
        results = []
        for i, entry in enumerate(entries):
            logger.info("Judging entry %d/%d …", i + 1, len(entries))
            result = self.evaluate(
                query=entry["query"],
                answer=entry["answer"],
                contexts=entry.get("contexts"),
                expected_answer=entry.get("expected_answer"),
            )
            results.append(result)
        return results

    def summarize(self, results: list[JudgeResult]) -> dict[str, Any]:
        """
        Compute aggregate statistics over a list of JudgeResult objects.

        Args:
            results: List of completed JudgeResult objects.

        Returns:
            Dict with per-criterion averages, overall average, and pass rate.
        """
        valid = [r for r in results if r.error is None and r.criteria]
        if not valid:
            return {"error": "No valid results to summarize"}

        criterion_totals: dict[str, list[float]] = {c: [] for c in CRITERIA}
        for result in valid:
            for crit in result.criteria:
                if crit.name in criterion_totals:
                    criterion_totals[crit.name].append(crit.score)

        criterion_averages = {
            CRITERIA_LABELS[c]: round(sum(v) / len(v), 3) if v else 0.0
            for c, v in criterion_totals.items()
        }

        overall_scores = [r.overall_score for r in valid]
        overall_avg = round(sum(overall_scores) / len(overall_scores), 3)
        pass_rate = round(sum(1 for r in valid if r.verdict == "PASS") / len(valid), 3)

        return {
            "total_evaluated": len(results),
            "valid": len(valid),
            "errors": len(results) - len(valid),
            "overall_average_score": overall_avg,
            "pass_rate": pass_rate,
            "pass_threshold": PASS_THRESHOLD,
            "criterion_averages": criterion_averages,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_llm(self, messages: list[dict]) -> str:
        """Call LLM via LiteLLM with 503 fallback (mirrors react_agent pattern)."""
        # Ensure keys are present (in case env was modified after import)
        if settings.google_api_key:
            os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
            os.environ.setdefault("GEMINI_API_KEY", settings.google_api_key)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,  # deterministic judging
            "max_tokens": 1024,
        }
        if "ollama" in self.model:
            kwargs["api_base"] = settings.llm_base_url

        try:
            response = completion(**kwargs)
            return response.choices[0].message.content
        except Exception as primary_error:
            if "503" in str(primary_error) or "UNAVAILABLE" in str(primary_error):
                logger.warning(
                    "Primary model unavailable (503), falling back to %s",
                    self._fallback_model,
                )
                fb_kwargs = {
                    "model": self._fallback_model,
                    "messages": messages,
                    "temperature": 0.0,
                    "max_tokens": 1024,
                }
                response = completion(**fb_kwargs)
                self.model = self._fallback_model  # update for reporting
                return response.choices[0].message.content
            raise

    def _parse_response(self, raw: str, result: JudgeResult) -> JudgeResult:
        """
        Parse LLM JSON response into a JudgeResult.

        Tolerant of markdown code fences (```json … ```) that some models add.
        """
        # Strip markdown fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned invalid JSON: {exc}\nRaw output: {raw[:500]}") from exc

        criteria_results: list[CriterionResult] = []
        for name in CRITERIA:
            if name not in data:
                logger.warning("Criterion '%s' missing from LLM response", name)
                continue

            entry = data[name]
            score = float(entry.get("score", 0))
            score = max(1.0, min(5.0, score))  # clamp to [1, 5]

            criteria_results.append(
                CriterionResult(
                    name=name,
                    label=CRITERIA_LABELS[name],
                    score=score,
                    justification=str(entry.get("justification", "")),
                )
            )

        if not criteria_results:
            raise ValueError("No valid criteria found in LLM response")

        overall = sum(c.score for c in criteria_results) / len(criteria_results)
        result.criteria = criteria_results
        result.overall_score = round(overall, 3)
        result.verdict = "PASS" if overall >= PASS_THRESHOLD else "FAIL"
        return result


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point  (python -m src.evaluation.llm_judge)
# ─────────────────────────────────────────────────────────────────────────────


def _run_demo() -> None:
    """Quick smoke test: judge a sample response from the golden set."""
    from src.evaluation.golden_set import load_golden_set

    entries = load_golden_set()
    if not entries:
        logger.error("Golden set is empty — cannot run demo")
        return

    sample = entries[0]
    judge = LLMJudge()

    logger.info("Judging golden set entry: %s", sample.id)
    result = judge.evaluate(
        query=sample.query,
        answer=sample.expected_answer,  # Self-judging: expected should score high
        contexts=sample.contexts,
        expected_answer=sample.expected_answer,
    )

    print("\n" + "=" * 60)
    print(f"Query   : {result.query}")
    print(f"Verdict : {result.verdict}")
    print(f"Overall : {result.overall_score:.2f} / 5.0")
    print("-" * 60)
    for crit in result.criteria:
        print(f"  [{crit.score:.1f}] {crit.label}")
        print(f"       {crit.justification}")
    print("=" * 60)


if __name__ == "__main__":
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(message)s")
    _run_demo()
