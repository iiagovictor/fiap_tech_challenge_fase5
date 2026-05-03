"""Evaluation helpers: golden set, RAG assessment, LLM-as-judge, A/B benchmarks."""

from .ab_test_prompts import (
    ALL_VARIANTS,
    VARIANT_A,
    VARIANT_B,
    VARIANT_C,
    PromptBenchmark,
    PromptVariant,
)
from .golden_set import GoldenSetEntry, evaluate_golden_set, load_golden_set
from .llm_judge import CRITERIA_LABELS, PASS_THRESHOLD, CriterionResult, JudgeResult, LLMJudge

__all__ = [
    # Golden set
    "GoldenSetEntry",
    "evaluate_golden_set",
    "load_golden_set",
    # LLM-as-judge
    "LLMJudge",
    "JudgeResult",
    "CriterionResult",
    "CRITERIA_LABELS",
    "PASS_THRESHOLD",
    # A/B prompt benchmark
    "PromptBenchmark",
    "PromptVariant",
    "VARIANT_A",
    "VARIANT_B",
    "VARIANT_C",
    "ALL_VARIANTS",
]
