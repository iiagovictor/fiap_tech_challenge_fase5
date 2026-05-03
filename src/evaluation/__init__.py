"""Evaluation helpers: golden set, RAG assessment, LLM-as-judge, A/B benchmarks."""

from .golden_set import GoldenSetEntry, evaluate_golden_set, load_golden_set

# litellm is an optional dependency (extras: llm, dev).
# Guard these imports so that modules without litellm installed can still use
# golden_set (and tests can still be collected by pytest).
_llm_extras_available = False
try:
    from .ab_test_prompts import (
        ALL_VARIANTS,
        VARIANT_A,
        VARIANT_B,
        VARIANT_C,
        PromptBenchmark,
        PromptVariant,
    )
    from .llm_judge import CRITERIA_LABELS, PASS_THRESHOLD, CriterionResult, JudgeResult, LLMJudge

    _llm_extras_available = True
except ImportError:
    pass

__all__ = [
    # Golden set (always available)
    "GoldenSetEntry",
    "evaluate_golden_set",
    "load_golden_set",
]

if _llm_extras_available:
    __all__ += [
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
