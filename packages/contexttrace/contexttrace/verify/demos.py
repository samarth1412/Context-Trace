from __future__ import annotations

from copy import deepcopy
from typing import Any

from contexttrace.verify.schema import RAGTrace, load_trace


VERIFY_DEMO_NAMES = (
    "unsupported_claim",
    "partial_support",
    "citation_mismatch",
    "should_abstain",
    "supported_answer",
)


VERIFY_DEMOS: dict[str, dict[str, Any]] = {
    "unsupported_claim": {
        "query": "How long does refund processing take?",
        "answer": "Refunds are processed within 5 business days.",
        "contexts": [
            {
                "id": "policy_2026",
                "text": "Customers may request refunds within 30 days of purchase.",
                "metadata": {
                    "source": "refund_policy.pdf",
                    "page": 2,
                    "version": "2026",
                },
            }
        ],
        "metadata": {
            "model": "demo-rag",
            "retriever": "hybrid_top_5",
            "run_id": "golden_unsupported_claim",
        },
    },
    "partial_support": {
        "query": "What refund details apply?",
        "answer": "Refunds within 30 days require manager approval.",
        "contexts": [
            {
                "id": "policy_2026",
                "text": "Customers may request refunds within 30 days of purchase.",
                "metadata": {
                    "source": "refund_policy.pdf",
                    "page": 2,
                    "version": "2026",
                },
            }
        ],
        "metadata": {
            "model": "demo-rag",
            "retriever": "hybrid_top_5",
            "run_id": "demo_partial_support",
        },
    },
    "citation_mismatch": {
        "query": "What is the current refund window?",
        "answer": "Refunds are allowed within 30 days of purchase.",
        "contexts": [
            {
                "id": "policy_2024",
                "text": (
                    "Customers may exchange eligible items within 14 days of purchase. "
                    "This archived memo does not define the current refund window."
                ),
                "metadata": {
                    "source": "archived_exchange_policy.pdf",
                    "page": 1,
                    "version": "2024",
                },
            },
            {
                "id": "policy_2026",
                "text": "Customers may request refunds within 30 days of purchase.",
                "metadata": {
                    "source": "refund_policy.pdf",
                    "page": 2,
                    "version": "2026",
                },
            },
        ],
        "citations": [
            {
                "claim": "Refunds are allowed within 30 days of purchase.",
                "source_id": "policy_2024",
            }
        ],
        "metadata": {
            "model": "demo-rag",
            "retriever": "hybrid_top_5",
            "run_id": "golden_citation_mismatch",
        },
    },
    "should_abstain": {
        "query": "What refund exception applies to VIP customers?",
        "answer": "VIP customers receive cash refunds up to 90 days after purchase.",
        "contexts": [
            {
                "id": "shipping_policy",
                "text": (
                    "Standard shipping takes 3 to 5 business days. "
                    "Expedited shipping is available for eligible orders."
                ),
                "metadata": {
                    "source": "shipping_policy.pdf",
                    "page": 4,
                },
            }
        ],
        "metadata": {
            "model": "demo-rag",
            "retriever": "keyword_top_3",
            "run_id": "golden_should_abstain",
        },
    },
    "supported_answer": {
        "query": "What is the refund policy?",
        "answer": (
            "Refunds are allowed within 30 days of purchase. "
            "Refund requests must include an order number."
        ),
        "contexts": [
            {
                "id": "policy_2026",
                "text": (
                    "Customers may request refunds within 30 days of purchase. "
                    "Refund requests must include an order number."
                ),
                "metadata": {
                    "source": "refund_policy.pdf",
                    "page": 2,
                    "version": "2026",
                },
            }
        ],
        "citations": [
            {
                "claim": "Refunds are allowed within 30 days of purchase.",
                "source_id": "policy_2026",
            },
            {
                "claim": "Refund requests must include an order number.",
                "source_id": "policy_2026",
            },
        ],
        "metadata": {
            "model": "demo-rag",
            "retriever": "hybrid_top_5",
            "run_id": "golden_supported_answer",
        },
    },
}


def list_verify_demos() -> list[str]:
    return list(VERIFY_DEMO_NAMES)


def load_verify_demo(name: str) -> RAGTrace:
    if name not in VERIFY_DEMOS:
        raise KeyError(name)
    return load_trace(deepcopy(VERIFY_DEMOS[name]), source="verify demo %s" % name)
