"""Golden set evaluation utilities for the financial LLM agent."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


@dataclass
class GoldenSetEntry:
    id: str
    query: str
    ticker: str
    expected_answer: str
    contexts: list[str]


def _normalize_text(text: str) -> str:
    return " ".join(str(text).lower().strip().replace("\n", " ").split())


def _token_overlap(expected: str, actual: str) -> float:
    expected_tokens = set(_normalize_text(expected).split())
    actual_tokens = set(_normalize_text(actual).split())
    if not expected_tokens:
        return 0.0
    return len(expected_tokens & actual_tokens) / len(expected_tokens)


def load_golden_set(path: Path | str | None = None) -> list[GoldenSetEntry]:
    """Load the golden set examples from disk."""
    if path is None:
        path = Path(__file__).resolve().parents[2] / "data" / "golden_set" / "golden_set.jsonl"

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Golden set file not found: {path}")

    entries: list[GoldenSetEntry] = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            entries.append(GoldenSetEntry(**payload))

    return entries


def score_response(expected_answer: str, actual_answer: str) -> dict[str, Any]:
    """Score an agent answer against the golden-set expected answer."""
    actual_norm = _normalize_text(actual_answer)
    expected_norm = _normalize_text(expected_answer)

    exact_match = actual_norm == expected_norm
    overlap = _token_overlap(expected_norm, actual_norm)
    similarity = SequenceMatcher(None, expected_norm, actual_norm).ratio()
    score = round((0.5 if exact_match else 0.0) + overlap * 0.3 + similarity * 0.2, 3)

    return {
        "exact_match": exact_match,
        "token_overlap": round(overlap, 3),
        "similarity": round(similarity, 3),
        "score": score,
    }


def evaluate_golden_set(
    agent_responses: dict[str, str] | None = None,
    path: Path | str | None = None,
) -> dict[str, Any]:
    """Evaluate the golden set and return a summary report."""
    entries = load_golden_set(path)
    summary = {
        "golden_set_size": len(entries),
        "evaluated": 0,
        "exact_matches": 0,
        "average_score": 0.0,
        "results": [],
    }

    if not agent_responses:
        return summary

    total_score = 0.0
    for entry in entries:
        if entry.id not in agent_responses:
            continue
        result = score_response(entry.expected_answer, agent_responses[entry.id])
        total_score += result["score"]
        summary["evaluated"] += 1
        if result["exact_match"]:
            summary["exact_matches"] += 1
        summary["results"].append(
            {
                "id": entry.id,
                "query": entry.query,
                "ticker": entry.ticker,
                "score": result["score"],
                "exact_match": result["exact_match"],
                "token_overlap": result["token_overlap"],
                "similarity": result["similarity"],
            }
        )

    summary["average_score"] = round(total_score / summary["evaluated"], 3) if summary["evaluated"] else 0.0
    return summary


if __name__ == "__main__":
    entries = load_golden_set()
    print(f"Loaded {len(entries)} golden set examples")
    print("First example:")
    print(entries[0])
