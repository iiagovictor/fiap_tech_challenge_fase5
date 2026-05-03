"""
Unit tests for src/evaluation/llm_judge.py — LLM-as-Judge evaluator.

All LLM calls are mocked so tests run without network or API keys.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.evaluation.llm_judge import (
    CRITERIA,
    CRITERIA_LABELS,
    PASS_THRESHOLD,
    CriterionResult,
    JudgeResult,
    LLMJudge,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_QUERY = "A VALE3.SA está em zona de sobrecompra?"
SAMPLE_ANSWER = (
    "VALE3.SA está próxima da sobrecompra, com RSI em torno de 68, "
    "mas ainda não ultrapassou o nível crítico de 70."
)
SAMPLE_CONTEXTS = ["RSI próximo a 68", "Preço testando resistência anterior", "MACD ainda positivo"]
SAMPLE_EXPECTED = (
    "VALE3.SA está perto da zona de sobrecompra, mas ainda não atingiu RSI acima de 70."
)


def _make_llm_json(scores: dict[str, float] | None = None) -> str:
    """Build a valid LLM JSON response with given per-criterion scores."""
    default = {c: 4.0 for c in CRITERIA}
    if scores:
        default.update(scores)
    payload = {
        c: {"score": default[c], "justification": f"Justificativa de teste para {c}."}
        for c in CRITERIA
    }
    return json.dumps(payload)


def _mock_completion(raw_content: str):
    """Return a MagicMock that mimics litellm.completion() return value."""
    mock_choice = MagicMock()
    mock_choice.message.content = raw_content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


# ─────────────────────────────────────────────────────────────────────────────
# CriterionResult tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCriterionResult:
    def test_fields_stored(self):
        cr = CriterionResult(
            name="relevancia",
            label="Relevância",
            score=4.5,
            justification="Boa resposta.",
        )
        assert cr.name == "relevancia"
        assert cr.label == "Relevância"
        assert cr.score == 4.5
        assert cr.justification == "Boa resposta."


# ─────────────────────────────────────────────────────────────────────────────
# JudgeResult tests
# ─────────────────────────────────────────────────────────────────────────────


class TestJudgeResult:
    def test_as_dict_structure(self):
        result = JudgeResult(
            query="Pergunta?",
            answer="Resposta.",
            overall_score=4.0,
            verdict="PASS",
            model_used="gemini/gemini-2.0-flash-exp",
            criteria=[
                CriterionResult("relevancia", "Relevância", 4.0, "OK"),
            ],
        )
        d = result.as_dict()
        assert d["overall_score"] == 4.0
        assert d["verdict"] == "PASS"
        assert len(d["criteria"]) == 1
        assert d["criteria"][0]["name"] == "relevancia"
        assert d["criteria"][0]["score"] == 4.0

    def test_as_dict_with_error(self):
        result = JudgeResult(query="Q", answer="A", error="LLM timeout")
        d = result.as_dict()
        assert d["error"] == "LLM timeout"


# ─────────────────────────────────────────────────────────────────────────────
# LLMJudge._parse_response tests (no LLM call)
# ─────────────────────────────────────────────────────────────────────────────


class TestParseResponse:
    def _judge(self) -> LLMJudge:
        return LLMJudge(model="ollama/llama3")

    def test_parses_all_four_criteria(self):
        judge = self._judge()
        raw = _make_llm_json()
        base = JudgeResult(query="Q", answer="A")
        result = judge._parse_response(raw, base)

        assert len(result.criteria) == len(CRITERIA)
        for crit in result.criteria:
            assert crit.name in CRITERIA
            assert 1.0 <= crit.score <= 5.0
            assert crit.justification

    def test_overall_score_is_average(self):
        judge = self._judge()
        raw = _make_llm_json(
            {
                "relevancia": 5.0,
                "fidelidade_tecnica": 3.0,
                "adequacao_investimento": 4.0,
                "clareza_e_fundamentacao": 4.0,
            }
        )
        base = JudgeResult(query="Q", answer="A")
        result = judge._parse_response(raw, base)

        assert result.overall_score == pytest.approx(4.0, abs=0.01)

    def test_verdict_pass_when_above_threshold(self):
        judge = self._judge()
        raw = _make_llm_json({c: 4.0 for c in CRITERIA})
        base = JudgeResult(query="Q", answer="A")
        result = judge._parse_response(raw, base)

        assert result.verdict == "PASS"
        assert result.overall_score >= PASS_THRESHOLD

    def test_verdict_fail_when_below_threshold(self):
        judge = self._judge()
        raw = _make_llm_json({c: 1.5 for c in CRITERIA})
        base = JudgeResult(query="Q", answer="A")
        result = judge._parse_response(raw, base)

        assert result.verdict == "FAIL"
        assert result.overall_score < PASS_THRESHOLD

    def test_score_clamped_above_5(self):
        judge = self._judge()
        raw = _make_llm_json({c: 9.0 for c in CRITERIA})
        base = JudgeResult(query="Q", answer="A")
        result = judge._parse_response(raw, base)

        for crit in result.criteria:
            assert crit.score <= 5.0

    def test_score_clamped_below_1(self):
        judge = self._judge()
        raw = _make_llm_json({c: -2.0 for c in CRITERIA})
        base = JudgeResult(query="Q", answer="A")
        result = judge._parse_response(raw, base)

        for crit in result.criteria:
            assert crit.score >= 1.0

    def test_strips_markdown_code_fence(self):
        judge = self._judge()
        raw = "```json\n" + _make_llm_json() + "\n```"
        base = JudgeResult(query="Q", answer="A")
        result = judge._parse_response(raw, base)

        assert len(result.criteria) == len(CRITERIA)

    def test_invalid_json_raises(self):
        judge = self._judge()
        base = JudgeResult(query="Q", answer="A")
        with pytest.raises(ValueError, match="invalid JSON"):
            judge._parse_response("not json at all", base)

    def test_empty_json_object_raises(self):
        judge = self._judge()
        base = JudgeResult(query="Q", answer="A")
        with pytest.raises(ValueError, match="No valid criteria"):
            judge._parse_response("{}", base)


# ─────────────────────────────────────────────────────────────────────────────
# LLMJudge.evaluate — mocked LLM call
# ─────────────────────────────────────────────────────────────────────────────


class TestEvaluate:
    @patch("src.evaluation.llm_judge.completion")
    def test_evaluate_returns_judge_result(self, mock_completion):
        mock_completion.return_value = _mock_completion(_make_llm_json())

        judge = LLMJudge(model="ollama/llama3")
        result = judge.evaluate(
            query=SAMPLE_QUERY,
            answer=SAMPLE_ANSWER,
            contexts=SAMPLE_CONTEXTS,
            expected_answer=SAMPLE_EXPECTED,
        )

        assert isinstance(result, JudgeResult)
        assert result.query == SAMPLE_QUERY
        assert result.error is None
        assert len(result.criteria) == len(CRITERIA)

    @patch("src.evaluation.llm_judge.completion")
    def test_evaluate_without_optional_params(self, mock_completion):
        mock_completion.return_value = _mock_completion(_make_llm_json())

        judge = LLMJudge(model="ollama/llama3")
        result = judge.evaluate(query=SAMPLE_QUERY, answer=SAMPLE_ANSWER)

        assert result.error is None
        assert result.overall_score > 0

    @patch("src.evaluation.llm_judge.completion")
    def test_evaluate_sets_verdict(self, mock_completion):
        mock_completion.return_value = _mock_completion(_make_llm_json({c: 4.0 for c in CRITERIA}))

        judge = LLMJudge(model="ollama/llama3")
        result = judge.evaluate(query=SAMPLE_QUERY, answer=SAMPLE_ANSWER)

        assert result.verdict in ("PASS", "FAIL")

    @patch("src.evaluation.llm_judge.completion")
    def test_evaluate_llm_error_sets_error_field(self, mock_completion):
        mock_completion.side_effect = RuntimeError("Connection refused")

        judge = LLMJudge(model="ollama/llama3")
        result = judge.evaluate(query=SAMPLE_QUERY, answer=SAMPLE_ANSWER)

        assert result.verdict == "ERROR"
        assert result.error is not None
        assert "Connection refused" in result.error

    @patch("src.evaluation.llm_judge.completion")
    def test_evaluate_503_triggers_fallback(self, mock_completion):
        """When primary model raises 503, judge should retry with fallback model."""
        fallback_response = _mock_completion(_make_llm_json())

        def side_effect(**kwargs):
            if kwargs.get("model") != "gemini/gemini-1.5-flash":
                raise RuntimeError("503 UNAVAILABLE")
            return fallback_response

        mock_completion.side_effect = side_effect

        judge = LLMJudge(model="gemini/gemini-2.0-flash-exp")
        result = judge.evaluate(query=SAMPLE_QUERY, answer=SAMPLE_ANSWER)

        assert result.error is None
        assert judge.model == "gemini/gemini-1.5-flash"


# ─────────────────────────────────────────────────────────────────────────────
# LLMJudge.evaluate_batch
# ─────────────────────────────────────────────────────────────────────────────


class TestEvaluateBatch:
    @patch("src.evaluation.llm_judge.completion")
    def test_batch_length_matches_input(self, mock_completion):
        mock_completion.return_value = _mock_completion(_make_llm_json())

        entries = [{"query": f"Pergunta {i}?", "answer": f"Resposta {i}."} for i in range(3)]
        judge = LLMJudge(model="ollama/llama3")
        results = judge.evaluate_batch(entries)

        assert len(results) == 3

    @patch("src.evaluation.llm_judge.completion")
    def test_batch_passes_contexts_and_expected(self, mock_completion):
        mock_completion.return_value = _mock_completion(_make_llm_json())

        entries = [
            {
                "query": SAMPLE_QUERY,
                "answer": SAMPLE_ANSWER,
                "contexts": SAMPLE_CONTEXTS,
                "expected_answer": SAMPLE_EXPECTED,
            }
        ]
        judge = LLMJudge(model="ollama/llama3")
        results = judge.evaluate_batch(entries)

        assert results[0].error is None
        assert results[0].query == SAMPLE_QUERY


# ─────────────────────────────────────────────────────────────────────────────
# LLMJudge.summarize
# ─────────────────────────────────────────────────────────────────────────────


class TestSummarize:
    def _make_result(self, scores: dict[str, float], verdict: str = "PASS") -> JudgeResult:
        criteria = [
            CriterionResult(name=c, label=CRITERIA_LABELS[c], score=scores[c], justification="ok")
            for c in CRITERIA
        ]
        overall = sum(scores.values()) / len(scores)
        return JudgeResult(
            query="Q",
            answer="A",
            criteria=criteria,
            overall_score=round(overall, 3),
            verdict=verdict,
        )

    def test_summarize_returns_expected_keys(self):
        results = [self._make_result({c: 4.0 for c in CRITERIA})]
        judge = LLMJudge(model="ollama/llama3")
        summary = judge.summarize(results)

        assert "overall_average_score" in summary
        assert "pass_rate" in summary
        assert "criterion_averages" in summary
        assert "total_evaluated" in summary

    def test_summarize_pass_rate_all_pass(self):
        results = [self._make_result({c: 4.0 for c in CRITERIA}, verdict="PASS") for _ in range(5)]
        judge = LLMJudge(model="ollama/llama3")
        summary = judge.summarize(results)

        assert summary["pass_rate"] == pytest.approx(1.0)

    def test_summarize_pass_rate_mixed(self):
        results = [
            self._make_result({c: 4.0 for c in CRITERIA}, verdict="PASS"),
            self._make_result({c: 2.0 for c in CRITERIA}, verdict="FAIL"),
        ]
        judge = LLMJudge(model="ollama/llama3")
        summary = judge.summarize(results)

        assert summary["pass_rate"] == pytest.approx(0.5)

    def test_summarize_criterion_averages_present(self):
        results = [self._make_result({c: 3.0 for c in CRITERIA})]
        judge = LLMJudge(model="ollama/llama3")
        summary = judge.summarize(results)

        for label in CRITERIA_LABELS.values():
            assert label in summary["criterion_averages"]

    def test_summarize_skips_error_results(self):
        error_result = JudgeResult(query="Q", answer="A", verdict="ERROR", error="timeout")
        valid_result = self._make_result({c: 5.0 for c in CRITERIA}, verdict="PASS")

        judge = LLMJudge(model="ollama/llama3")
        summary = judge.summarize([error_result, valid_result])

        assert summary["total_evaluated"] == 2
        assert summary["valid"] == 1
        assert summary["errors"] == 1

    def test_summarize_empty_returns_error(self):
        judge = LLMJudge(model="ollama/llama3")
        summary = judge.summarize([])

        assert "error" in summary


# ─────────────────────────────────────────────────────────────────────────────
# Constants / metadata tests
# ─────────────────────────────────────────────────────────────────────────────


class TestConstants:
    def test_four_criteria_defined(self):
        assert len(CRITERIA) == 4

    def test_criteria_labels_cover_all_criteria(self):
        for c in CRITERIA:
            assert c in CRITERIA_LABELS

    def test_pass_threshold_is_reasonable(self):
        assert 1.0 <= PASS_THRESHOLD <= 5.0
