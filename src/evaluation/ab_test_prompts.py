"""
A/B Prompt Benchmark for the financial LLM agent.

Compares multiple system-prompt *variants* (strategies) by:
1. Generating an answer for each Golden Set entry using each variant via LiteLLM.
2. Evaluating every answer with ``LLMJudge`` (4 criteria, 1–5 scale).
3. Printing a side-by-side comparison report.

Three built-in variants are provided:

* **A — Assessor Conservador**: cautious financial advisor — always includes
  risk disclaimers and investment warnings.
* **B — Analista Técnico**: precise technical analyst — indicator-focused,
  numeric, without unnecessary disclaimers.
* **C — Educador Financeiro**: explanatory educator — explains what each
  indicator means before giving the recommendation.

Usage::

    # Run all variants against first 5 golden-set entries
    python -m src.evaluation.ab_test_prompts

    # Run programmatically with custom sample size
    from src.evaluation.ab_test_prompts import PromptBenchmark
    benchmark = PromptBenchmark(n_entries=10)
    results = benchmark.run()
    report = benchmark.compare(results)
    benchmark.print_report(report)

"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from src.config.settings import get_settings
from src.evaluation.golden_set import GoldenSetEntry, load_golden_set
from src.evaluation.llm_judge import PASS_THRESHOLD, JudgeResult, LLMJudge

logger = logging.getLogger(__name__)
settings = get_settings()

# ── LiteLLM API key bootstrap ─────────────────────────────────────────────────
if settings.google_api_key:
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
    os.environ.setdefault("GEMINI_API_KEY", settings.google_api_key)
if settings.openai_api_key:
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
if settings.groq_api_key:
    os.environ.setdefault("GROQ_API_KEY", settings.groq_api_key)

from litellm import completion  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Prompt Variants
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PromptVariant:
    """A named system-prompt strategy to benchmark."""

    id: str
    name: str
    system_prompt: str
    temperature: float = 0.3


# ---------------------------------------------------------------------------
# Variant A — Conservative Financial Advisor
# ---------------------------------------------------------------------------
VARIANT_A = PromptVariant(
    id="A",
    name="Assessor Conservador",
    system_prompt="""\
Você é um assessor financeiro certificado, especializado no mercado brasileiro (B3).

Seu papel é responder perguntas sobre ações com cautela e responsabilidade.

REGRAS OBRIGATÓRIAS:
1. Sempre inclua um aviso de que a análise é educacional e não constitui
   recomendação de investimento.
2. Cite apenas indicadores técnicos com base nos dados disponíveis.
3. Quando os dados forem inconclusivos, diga claramente que o sinal é misto.
4. Use linguagem acessível e profissional.
5. Recomende sempre consultar um especialista antes de tomar decisões.

Responda de forma completa mas sucinta (3–5 frases).
""",
    temperature=0.2,
)

# ---------------------------------------------------------------------------
# Variant B — Technical Analyst
# ---------------------------------------------------------------------------
VARIANT_B = PromptVariant(
    id="B",
    name="Analista Técnico",
    system_prompt="""\
Você é um analista técnico experiente do mercado de ações brasileiro.

Seu foco é análise técnica precisa: RSI, MACD, médias móveis, Bollinger Bands,
OBV, ATR e padrões de candle.

ABORDAGEM:
1. Responda de forma direta e objetiva com base nos indicadores disponíveis.
2. Use valores numéricos sempre que disponíveis (ex: RSI=67, SMA20=R$18,50).
3. Identifique claramente o sinal técnico: ALTA, BAIXA ou NEUTRO.
4. Mencione suportes e resistências relevantes.
5. Seja conciso — máximo 4 frases.

Não inclua disclaimers de investimento extensos; o usuário é um profissional.
""",
    temperature=0.1,
)

# ---------------------------------------------------------------------------
# Variant C — Financial Educator
# ---------------------------------------------------------------------------
VARIANT_C = PromptVariant(
    id="C",
    name="Educador Financeiro",
    system_prompt="""\
Você é um educador financeiro que ajuda investidores iniciantes a entenderem
análise técnica no mercado brasileiro.

ESTILO DE RESPOSTA:
1. Antes de dar o sinal, explique brevemente o que o indicador mencionado significa.
2. Use analogias simples quando necessário.
3. Dê o sinal técnico de forma clara ao final.
4. Inclua um lembrete de que análise técnica é uma ferramenta, não uma garantia.
5. Responda em no máximo 5 frases.

Exemplo de estrutura:
- "O RSI (Índice de Força Relativa) mede... Atualmente está em X, o que indica..."
""",
    temperature=0.3,
)

ALL_VARIANTS: list[PromptVariant] = [VARIANT_A, VARIANT_B, VARIANT_C]


# ─────────────────────────────────────────────────────────────────────────────
# Result data structures
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class VariantEntryResult:
    """Result of applying one prompt variant to one golden set entry."""

    entry_id: str
    variant_id: str
    query: str
    generated_answer: str
    judge_result: JudgeResult
    generation_error: str | None = None


@dataclass
class VariantBenchmarkResult:
    """Aggregated result for a single prompt variant."""

    variant: PromptVariant
    entry_results: list[VariantEntryResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Answer generation
# ─────────────────────────────────────────────────────────────────────────────


def _generate_answer(
    variant: PromptVariant,
    entry: GoldenSetEntry,
    model: str,
) -> tuple[str, str | None]:
    """
    Generate an answer for a golden set entry using the given prompt variant.

    Returns (answer, error_message). error_message is None on success.
    """
    context_block = "\n".join(f"- {c}" for c in entry.contexts)
    user_message = (
        f"Contextos disponíveis sobre {entry.ticker}:\n{context_block}\n\n"
        f"Pergunta: {entry.query}"
    )
    messages = [
        {"role": "system", "content": variant.system_prompt},
        {"role": "user", "content": user_message},
    ]
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": variant.temperature,
        "max_tokens": 512,
    }
    if "ollama" in model:
        kwargs["api_base"] = settings.llm_base_url

    try:
        response = completion(**kwargs)
        return response.choices[0].message.content, None
    except Exception as exc:
        # 503 fallback to Gemini Flash
        if "503" in str(exc) or "UNAVAILABLE" in str(exc):
            try:
                fallback_kwargs = {**kwargs, "model": "gemini/gemini-1.5-flash"}
                fallback_response = completion(**fallback_kwargs)
                return fallback_response.choices[0].message.content, None
            except Exception as fb_exc:
                return "", str(fb_exc)
        return "", str(exc)


# ─────────────────────────────────────────────────────────────────────────────
# Benchmark orchestrator
# ─────────────────────────────────────────────────────────────────────────────


class PromptBenchmark:
    """
    Runs an A/B (or A/B/C) benchmark across prompt variants on the Golden Set.

    Args:
        variants: List of :class:`PromptVariant` to compare. Defaults to
            ``ALL_VARIANTS`` (A, B, C).
        n_entries: Number of golden-set entries to evaluate. ``None`` = all.
        model: LiteLLM model string. Defaults to ``settings.llm_model``.
        golden_set_path: Optional override for the golden set JSONL path.
    """

    def __init__(
        self,
        variants: list[PromptVariant] | None = None,
        n_entries: int | None = 5,
        model: str | None = None,
        golden_set_path: str | None = None,
    ) -> None:
        self.variants = variants or ALL_VARIANTS
        self.n_entries = n_entries
        self.model = model or settings.llm_model
        self._golden_set_path = golden_set_path
        self._judge = LLMJudge(model=self.model)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> list[VariantBenchmarkResult]:
        """
        Run the benchmark for all variants.

        Returns:
            List of :class:`VariantBenchmarkResult` — one per variant.
        """
        entries = load_golden_set(self._golden_set_path)
        if self.n_entries is not None:
            entries = entries[: self.n_entries]

        logger.info(
            "Starting A/B benchmark: %d variants × %d entries",
            len(self.variants),
            len(entries),
        )

        results: list[VariantBenchmarkResult] = []
        for variant in self.variants:
            logger.info("── Variant %s (%s) ──", variant.id, variant.name)
            variant_result = self._run_variant(variant, entries)
            variant_result.summary = self._judge.summarize(
                [r.judge_result for r in variant_result.entry_results]
            )
            results.append(variant_result)

        return results

    def compare(self, results: list[VariantBenchmarkResult]) -> dict[str, Any]:
        """
        Build a side-by-side comparison dict from benchmark results.

        Returns:
            Dict keyed by variant id with summary statistics.
        """
        comparison: dict[str, Any] = {}
        for vr in results:
            comparison[vr.variant.id] = {
                "name": vr.variant.name,
                "n_entries": len(vr.entry_results),
                **vr.summary,
            }
        return comparison

    def print_report(self, comparison: dict[str, Any]) -> None:
        """Print a human-readable comparison report to stdout."""
        sep = "─" * 70
        print(f"\n{'═' * 70}")
        print("  A/B PROMPT BENCHMARK — Resultados")
        print(f"{'═' * 70}")

        # Header row
        header = f"{'Variant':<5} {'Nome':<26} {'Score Médio':>11} {'Pass Rate':>9} {'Válidos':>7}"
        print(header)
        print(sep)

        ranked = sorted(
            comparison.items(),
            key=lambda kv: kv[1].get("overall_average_score", 0.0),
            reverse=True,
        )
        for rank, (vid, stats) in enumerate(ranked, start=1):
            avg = stats.get("overall_average_score", 0.0)
            pr = stats.get("pass_rate", 0.0)
            valid = stats.get("valid", 0)
            name = stats.get("name", vid)
            medal = ["🥇", "🥈", "🥉"].pop(0) if rank <= 3 else "  "
            print(f"{medal} {vid:<4} {name:<26} {avg:>10.2f} {pr:>8.1%} {valid:>7}")

        print(sep)

        # Per-criterion breakdown
        print("\n  Scores médios por critério:\n")
        all_criteria: set[str] = set()
        for stats in comparison.values():
            all_criteria.update(stats.get("criterion_averages", {}).keys())

        crit_header = f"  {'Critério':<45}" + "".join(f"{vid:>8}" for vid in comparison)
        print(crit_header)
        print("  " + sep)

        for crit in sorted(all_criteria):
            row = f"  {crit:<45}"
            for vid in comparison:
                score = comparison[vid].get("criterion_averages", {}).get(crit, 0.0)
                row += f"{score:>8.2f}"
            print(row)

        print(f"\n  Threshold de aprovação: {PASS_THRESHOLD:.1f} / 5.0")
        print(f"{'═' * 70}\n")

    def save_results(
        self,
        results: list[VariantBenchmarkResult],
        output_path: str = "reports/ab_test_results.json",
    ) -> None:
        """Serialize full benchmark results to a JSON file."""
        import pathlib

        out = pathlib.Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        payload = []
        for vr in results:
            payload.append(
                {
                    "variant_id": vr.variant.id,
                    "variant_name": vr.variant.name,
                    "summary": vr.summary,
                    "entries": [
                        {
                            "entry_id": er.entry_id,
                            "query": er.query,
                            "generated_answer": er.generated_answer,
                            "generation_error": er.generation_error,
                            "judge": er.judge_result.as_dict() if er.judge_result else None,
                        }
                        for er in vr.entry_results
                    ],
                }
            )

        with out.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

        logger.info("Benchmark results saved to %s", output_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_variant(
        self,
        variant: PromptVariant,
        entries: list[GoldenSetEntry],
    ) -> VariantBenchmarkResult:
        variant_result = VariantBenchmarkResult(variant=variant)

        for i, entry in enumerate(entries):
            logger.info(
                "  [%s] Entry %d/%d — %s",
                variant.id,
                i + 1,
                len(entries),
                entry.id,
            )

            # Generate answer
            answer, gen_error = _generate_answer(variant, entry, self.model)

            # Judge the answer (even if generation failed — judge will give low score)
            judge_result = self._judge.evaluate(
                query=entry.query,
                answer=answer or "(sem resposta — erro de geração)",
                contexts=entry.contexts,
                expected_answer=entry.expected_answer,
            )

            variant_result.entry_results.append(
                VariantEntryResult(
                    entry_id=entry.id,
                    variant_id=variant.id,
                    query=entry.query,
                    generated_answer=answer,
                    judge_result=judge_result,
                    generation_error=gen_error,
                )
            )

        return variant_result


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point  (python -m src.evaluation.ab_test_prompts)
# ─────────────────────────────────────────────────────────────────────────────


def _run_cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="A/B Prompt Benchmark — compara variantes de system prompt no Golden Set."
    )
    parser.add_argument(
        "--n-entries",
        type=int,
        default=5,
        help="Número de entradas do golden set a avaliar (default: 5).",
    )
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=["A", "B", "C"],
        default=["A", "B", "C"],
        help="Variantes a comparar (default: A B C).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override do modelo LLM (default: LLM_MODEL do .env).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reports/ab_test_results.json",
        help="Caminho para salvar resultados JSON (default: reports/ab_test_results.json).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Não salvar resultados em disco.",
    )
    args = parser.parse_args()

    variant_map = {"A": VARIANT_A, "B": VARIANT_B, "C": VARIANT_C}
    selected_variants = [variant_map[v] for v in args.variants]

    benchmark = PromptBenchmark(
        variants=selected_variants,
        n_entries=args.n_entries,
        model=args.model,
    )

    print(
        f"\nIniciando benchmark: {len(selected_variants)} variantes × "
        f"{args.n_entries} entradas do golden set"
    )
    print(f"Modelo: {benchmark.model}\n")

    results = benchmark.run()
    comparison = benchmark.compare(results)
    benchmark.print_report(comparison)

    if not args.no_save:
        benchmark.save_results(results, output_path=args.output)
        print(f"Resultados salvos em: {args.output}")


if __name__ == "__main__":
    import logging as _logging

    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )
    _run_cli()
