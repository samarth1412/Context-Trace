from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class PlaygroundSampleDocument:
    filename: str
    content_type: str
    content: str


@dataclass(frozen=True)
class PlaygroundSampleDataset:
    sample_id: str
    name: str
    description: str
    suggested_queries: List[str]
    documents: List[PlaygroundSampleDocument]


SAMPLE_DATASETS = {
    "employee_handbook": PlaygroundSampleDataset(
        sample_id="employee_handbook",
        name="Employee handbook",
        description="Remote work, PTO, expenses, and device security policies.",
        suggested_queries=[
            "How many days per week can employees work remotely?",
            "How many unused PTO days can roll over?",
        ],
        documents=[
            PlaygroundSampleDocument(
                filename="employee-handbook.md",
                content_type="text/markdown",
                content=(
                    "# Employee Handbook\n\n"
                    "Employees may work remotely up to three days per week when their role supports remote work. "
                    "The schedule must be approved by the employee's manager and recorded in the team calendar.\n\n"
                    "Full-time employees receive 18 days of paid time off each calendar year. "
                    "Unused PTO can roll over up to five days into the next calendar year.\n\n"
                    "Employees must submit expenses within 45 days of the purchase date. "
                    "Manager approval is required for expenses above 500 dollars.\n\n"
                    "Lost or stolen company laptops must be reported to IT within one hour of discovery."
                ),
            )
        ],
    ),
    "refund_policy": PlaygroundSampleDataset(
        sample_id="refund_policy",
        name="Refund policy",
        description="Refund eligibility, processing time, final sale exclusions, and damaged item reviews.",
        suggested_queries=[
            "What is the refund policy?",
            "Can final sale items be refunded?",
        ],
        documents=[
            PlaygroundSampleDocument(
                filename="refund-policy.md",
                content_type="text/markdown",
                content=(
                    "# Refund Policy\n\n"
                    "Customers may request a refund within 30 calendar days of the purchase date when the product is unused "
                    "or the service has not been substantially consumed. Approved refunds are returned to the original payment method.\n\n"
                    "Refund approval normally takes two business days after support receives the required details. "
                    "Payment processing can take five to seven business days after approval.\n\n"
                    "Final sale items, gift cards, and accounts closed for policy abuse are not eligible for refunds. "
                    "Damaged item cases require a photo, proof of purchase, and the packaging label."
                ),
            )
        ],
    ),
    "ai_paper_qa": PlaygroundSampleDataset(
        sample_id="ai_paper_qa",
        name="AI paper QA",
        description="RAG evaluation, hybrid retrieval, citation support, and vector database tuning.",
        suggested_queries=[
            "What does citation support check in a RAG evaluation?",
            "Why combine lexical ranking with dense vector search?",
        ],
        documents=[
            PlaygroundSampleDocument(
                filename="rag-evaluation-notes.md",
                content_type="text/markdown",
                content=(
                    "# RAG Evaluation Notes\n\n"
                    "RAG systems can be evaluated with answer correctness, citation support, retrieval recall, and abstention behavior. "
                    "Citation support checks whether each answer claim is grounded in the cited passage.\n\n"
                    "Hybrid retrieval combines lexical ranking with dense vector search. Reranking can improve precision by scoring "
                    "retrieved candidates against the query before generation.\n\n"
                    "Vector database index choice, chunk size, embedding model, and metadata filters can change retrieval recall and latency. "
                    "Attention weights do not prove that a generated claim is supported by an external source."
                ),
            )
        ],
    ),
}


def list_samples() -> List[PlaygroundSampleDataset]:
    return list(SAMPLE_DATASETS.values())


def get_sample(sample_id: str) -> PlaygroundSampleDataset:
    try:
        return SAMPLE_DATASETS[sample_id]
    except KeyError as exc:
        raise ValueError("Unknown sample dataset: %s" % sample_id) from exc

