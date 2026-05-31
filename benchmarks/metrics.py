from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List


METRIC_KEYS = (
    "citation_support",
    "unsupported_claim_rate",
    "failure_rate",
    "retrieval_miss_rate",
    "average_tokens",
    "average_latency_ms",
    "average_cost_usd",
)


def aggregate_results(records: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["strategy"])].append(record)

    summary: Dict[str, Dict[str, float]] = {}
    for strategy, rows in grouped.items():
        count = max(len(rows), 1)
        summary[strategy] = {
            "citation_support": _average(row["citation_support"] for row in rows),
            "unsupported_claim_rate": _average(row["unsupported_claim_rate"] for row in rows),
            "failure_rate": round(sum(1 for row in rows if row.get("failure")) / count, 3),
            "retrieval_miss_rate": round(sum(1 for row in rows if row.get("retrieval_miss")) / count, 3),
            "average_tokens": _average((row["tokens"] for row in rows), digits=1),
            "average_latency_ms": _average((row["latency_ms"] for row in rows), digits=1),
            "average_cost_usd": _average((row["cost_usd"] for row in rows), digits=6),
        }
    return summary


def rank_strategies(summary: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
    return [
        {"strategy": strategy, **metrics}
        for strategy, metrics in sorted(
            summary.items(),
            key=lambda item: (
                -item[1]["citation_support"],
                item[1]["unsupported_claim_rate"],
                item[1]["average_cost_usd"],
            ),
        )
    ]


def _average(values: Iterable[Any], *, digits: int = 3) -> float:
    numbers = [float(value or 0.0) for value in values]
    if not numbers:
        return 0.0
    return round(sum(numbers) / len(numbers), digits)
