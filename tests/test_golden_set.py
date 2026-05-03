"""Tests for golden set loading and evaluation."""

from src.evaluation.golden_set import evaluate_golden_set, load_golden_set, score_response


def test_load_golden_set_has_expected_count():
    entries = load_golden_set()
    assert len(entries) >= 20
    assert entries[0].id.startswith("gs-")
    assert entries[0].query
    assert isinstance(entries[0].contexts, list)


def test_score_response_exact_match():
    expected = "A tendência de alta é moderada e sustentável."
    actual = "A tendência de alta é moderada e sustentável."
    result = score_response(expected, actual)

    assert result["exact_match"] is True
    assert result["token_overlap"] == 1.0
    assert result["similarity"] == 1.0
    assert result["score"] == 1.0


def test_score_response_partial_match():
    expected = "Tendência de alta moderada com suporte na média móvel de 20 dias."
    actual = "Tendência de alta moderada, com suporte na média móvel de 20 dias e RSI neutro."
    result = score_response(expected, actual)

    assert result["exact_match"] is False
    assert result["token_overlap"] >= 0.5
    assert 0.0 < result["similarity"] <= 1.0
    assert result["score"] > 0.0


def test_evaluate_golden_set_summary():
    sample_responses = {
        "gs-001": (
            "A tendência de curto prazo é de alta moderada, com suporte próximo "
            "à média móvel de 20 dias e RSI neutro."
        ),
        "gs-002": "VALE3.SA está quase em sobrecompra, mas ainda não passou de 70 no RSI.",
    }
    summary = evaluate_golden_set(sample_responses)

    assert summary["golden_set_size"] >= 20
    assert summary["evaluated"] == 2
    assert summary["average_score"] > 0.0
    assert isinstance(summary["results"], list)
