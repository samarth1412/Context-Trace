from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contexttrace.verify.runner import verify_trace
from contexttrace.verify.schema import RAGTrace, load_trace


@dataclass(frozen=True)
class VerifyBenchmarkCase:
    id: str
    trace: RAGTrace
    expected_labels: set[str]


def benchmark_cases() -> list[VerifyBenchmarkCase]:
    return [
        _case(
            "supported_refund_window",
            {
                "query": "What is the refund policy?",
                "answer": "Refunds are allowed within 30 days of purchase.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Customers may request refunds within 30 days of purchase.",
                    }
                ],
                "citations": [
                    {
                        "claim": "Refunds are allowed within 30 days of purchase.",
                        "source_id": "policy",
                    }
                ],
            },
            {"no_failure_detected"},
        ),
        _case(
            "semantic_money_back_window",
            {
                "query": "What is the refund policy?",
                "answer": "Refunds are allowed within 30 days.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Customers can request money back within thirty days of purchase.",
                    }
                ],
            },
            {"no_failure_detected"},
        ),
        _case(
            "semantic_order_id",
            {
                "query": "What do refund requests need?",
                "answer": "Refund requests must include an order number.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Refund requests require an order ID.",
                    }
                ],
            },
            {"no_failure_detected"},
        ),
        _case(
            "unsupported_processing_time",
            {
                "query": "How long does refund processing take?",
                "answer": "Refunds are processed within 5 business days.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Customers may request refunds within 30 days of purchase.",
                    }
                ],
            },
            {"should_have_abstained", "unsupported_answer"},
        ),
        _case(
            "partial_manager_approval",
            {
                "query": "Can customers request refunds within 30 days?",
                "answer": "Refunds within 30 days require manager approval.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Customers may request refunds within 30 days of purchase.",
                    }
                ],
            },
            {"partial_support"},
        ),
        _case(
            "citation_wrong_source",
            {
                "query": "What is the current refund window?",
                "answer": "Refunds are allowed within 30 days of purchase.",
                "contexts": [
                    {
                        "id": "archive",
                        "text": "Customers may exchange eligible items within 14 days of purchase.",
                    },
                    {
                        "id": "current_policy",
                        "text": "Customers may request refunds within 30 days of purchase.",
                    },
                ],
                "citations": [
                    {
                        "claim": "Refunds are allowed within 30 days of purchase.",
                        "source_id": "archive",
                    }
                ],
            },
            {"citation_mismatch"},
        ),
        _case(
            "should_abstain_vip",
            {
                "query": "What refund exception applies to VIP customers?",
                "answer": "VIP customers receive cash refunds up to 90 days after purchase.",
                "contexts": [
                    {
                        "id": "shipping",
                        "text": "Standard shipping takes 3 to 5 business days.",
                    }
                ],
            },
            {"should_have_abstained", "unsupported_answer"},
        ),
        _case(
            "contradicted_refund_allowed",
            {
                "query": "Are refunds allowed within 30 days?",
                "answer": "Refunds are allowed within 30 days of purchase.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Refunds are not allowed within 30 days of purchase.",
                    }
                ],
            },
            {"should_have_abstained", "contradicted_answer"},
        ),
        _case(
            "supported_two_claims",
            {
                "query": "What is the refund policy?",
                "answer": "Refunds are allowed within 30 days of purchase. Refund requests must include an order number.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Customers may request refunds within 30 days of purchase. Refund requests must include an order number.",
                    }
                ],
                "citations": [
                    {
                        "claim": "Refunds are allowed within 30 days of purchase.",
                        "source_id": "policy",
                    },
                    {
                        "claim": "Refund requests must include an order number.",
                        "source_id": "policy",
                    },
                ],
            },
            {"no_failure_detected"},
        ),
    ]


def run_verify_benchmark(*, mode: str = "lexical") -> dict[str, Any]:
    rows = []
    labels = set()
    for case in benchmark_cases():
        result = verify_trace(case.trace, mode=mode)
        predicted = _predicted_labels(result)
        labels.update(case.expected_labels)
        labels.update(predicted)
        rows.append(
            {
                "id": case.id,
                "expected": sorted(case.expected_labels),
                "predicted": sorted(predicted),
                "exact_match": predicted == case.expected_labels,
                "summary": result.get("summary") or {},
            }
        )

    per_label = {}
    for label in sorted(labels):
        tp = sum(1 for row in rows if label in row["expected"] and label in row["predicted"])
        fp = sum(1 for row in rows if label not in row["expected"] and label in row["predicted"])
        fn = sum(1 for row in rows if label in row["expected"] and label not in row["predicted"])
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        per_label[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
        }

    exact_matches = sum(1 for row in rows if row["exact_match"])
    return {
        "mode": mode,
        "cases": len(rows),
        "exact_match_rate": round(exact_matches / len(rows), 3) if rows else 0.0,
        "per_label": per_label,
        "rows": rows,
    }


def _case(case_id: str, payload: dict[str, Any], expected_labels: set[str]) -> VerifyBenchmarkCase:
    return VerifyBenchmarkCase(
        id=case_id,
        trace=load_trace(payload, source="benchmark case %s" % case_id),
        expected_labels=expected_labels,
    )


def _predicted_labels(result: dict[str, Any]) -> set[str]:
    labels = set((result.get("summary") or {}).get("failure_types") or [])
    return labels or {"no_failure_detected"}
