from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEMO_DATASETS: dict[str, dict[str, Any]] = {
    "refund_policy": {
        "documents": {
            "refund_policy.md": """# Refund Policy

## Standard refunds
Customers may request a refund within 30 days of purchase when the product has not been consumed or customized. Refunds are returned to the original payment method.

## Processing time
Approved refunds are processed within 7 business days after the support team confirms eligibility.

## Non-refundable items
Shipping upgrades, gift cards, and consumed digital credits are non-refundable.
""",
            "exchange_policy.md": """# Exchange Policy

## Exchanges
Customers may exchange an unopened item within 45 days of purchase. Exchanges use store credit when the original item is no longer available.

## Defective items
Defective items may be replaced after support receives a photo of the defect and the order number.
""",
            "legacy_refund_memo.md": """# Legacy Refund Memo

## Archived policy
Before March 2024, refunds were limited to 14 days after purchase. This memo is archived and should not be used for current customer answers.
""",
            "subscription_terms.md": """# Subscription Terms

## Renewal
Monthly subscriptions renew automatically until canceled. Cancellation stops future renewals but does not refund prior months unless support grants an exception.
""",
        },
        "questions": [
            {"id": "refund_q1", "query": "How long do customers have to request a refund?", "type": "answerable"},
            {"id": "refund_q2", "query": "How long do approved refunds take to process?", "type": "citation-sensitive", "expected_failure": "citation_mismatch"},
            {"id": "refund_q3", "query": "Can shipping upgrades be refunded?", "type": "answerable"},
            {"id": "refund_q4", "query": "Can customers refund consumed digital credits?", "type": "answerable"},
            {"id": "refund_q5", "query": "Does the company provide refunds after 90 days for loyalty members?", "type": "unanswerable", "expected_failure": "should_have_abstained"},
            {"id": "refund_q6", "query": "What was the old refund window and what is the current window?", "type": "conflicting", "expected_failure": "conflicting_sources"},
            {"id": "refund_q7", "query": "Can an unopened item be exchanged after 40 days?", "type": "multi-hop"},
            {"id": "refund_q8", "query": "Are defective items replaceable?", "type": "answerable"},
            {"id": "refund_q9", "query": "Which payment method receives approved refunds?", "type": "answerable", "expected_failure": "retrieval_miss"},
            {"id": "refund_q10", "query": "Are subscription renewals automatically charged?", "type": "edge-case", "expected_failure": "unsupported_answer"},
        ],
        "expected_answers": {
            "refund_q1": "Customers have 30 days from purchase to request a refund.",
            "refund_q2": "Approved refunds are processed within 7 business days.",
            "refund_q3": "No. Shipping upgrades are non-refundable.",
            "refund_q4": "No. Consumed digital credits are non-refundable.",
            "refund_q5": "The documents do not state a 90-day loyalty-member refund exception.",
            "refund_q6": "The archived memo says 14 days before March 2024, while the current policy says 30 days.",
            "refund_q7": "Yes. Unopened items may be exchanged within 45 days.",
            "refund_q8": "Yes. Defective items may be replaced after support receives a photo and order number.",
            "refund_q9": "Approved refunds are returned to the original payment method.",
            "refund_q10": "Monthly subscriptions renew automatically until canceled.",
        },
        "expected_sources": {
            "refund_q1": ["refund_policy.md"],
            "refund_q2": ["refund_policy.md"],
            "refund_q3": ["refund_policy.md"],
            "refund_q4": ["refund_policy.md"],
            "refund_q5": [],
            "refund_q6": ["refund_policy.md", "legacy_refund_memo.md"],
            "refund_q7": ["exchange_policy.md"],
            "refund_q8": ["exchange_policy.md"],
            "refund_q9": ["refund_policy.md"],
            "refund_q10": ["subscription_terms.md"],
        },
    },
    "employee_handbook": {
        "documents": {
            "pto_policy.md": """# PTO Policy

## Annual allowance
Full-time employees receive 18 days of paid time off each calendar year. Unused PTO does not roll over unless a state law requires it.

## Approval
PTO requests for more than five consecutive business days require manager approval at least two weeks before the first day away.
""",
            "remote_work.md": """# Remote Work Policy

## Eligibility
Employees may work remotely up to three days per week with manager approval. Security training must be completed before remote work begins.

## Equipment
The company reimburses up to 600 USD for approved home-office equipment after receipts are submitted.
""",
            "security_handbook.md": """# Security Handbook

## Data handling
Customer data must not be copied into personal accounts, public AI tools, or unmanaged devices. Lost devices must be reported within one hour.
""",
            "old_remote_memo.md": """# Archived Remote Work Memo

## Archived rule
In 2021, employees could work remotely one day per week. This memo is archived and no longer applies.
""",
        },
        "questions": [
            {"id": "emp_q1", "query": "How many PTO days do full-time employees receive?", "type": "answerable"},
            {"id": "emp_q2", "query": "When is manager approval required for long PTO?", "type": "citation-sensitive", "expected_failure": "citation_mismatch"},
            {"id": "emp_q3", "query": "How many remote days are allowed now?", "type": "answerable"},
            {"id": "emp_q4", "query": "What is the home-office equipment reimbursement limit?", "type": "answerable"},
            {"id": "emp_q5", "query": "Can employees paste customer data into a public AI tool?", "type": "answerable"},
            {"id": "emp_q6", "query": "Does the handbook mention a four-day workweek benefit?", "type": "unanswerable", "expected_failure": "should_have_abstained"},
            {"id": "emp_q7", "query": "Compare the old and current remote work allowance.", "type": "conflicting", "expected_failure": "conflicting_sources"},
            {"id": "emp_q8", "query": "When must a lost device be reported?", "type": "answerable", "expected_failure": "retrieval_miss"},
            {"id": "emp_q9", "query": "Can unused PTO roll over everywhere?", "type": "edge-case"},
            {"id": "emp_q10", "query": "Can interns expense 1200 USD for chairs?", "type": "edge-case", "expected_failure": "unsupported_answer"},
        ],
        "expected_answers": {
            "emp_q1": "Full-time employees receive 18 days of PTO each calendar year.",
            "emp_q2": "PTO requests over five consecutive business days require manager approval at least two weeks in advance.",
            "emp_q3": "Employees may work remotely up to three days per week with manager approval.",
            "emp_q4": "The reimbursement limit is 600 USD for approved home-office equipment.",
            "emp_q5": "No. Customer data must not be copied into public AI tools.",
            "emp_q6": "The handbook does not mention a four-day workweek benefit.",
            "emp_q7": "The archived memo allowed one remote day per week; the current policy allows up to three days with approval.",
            "emp_q8": "Lost devices must be reported within one hour.",
            "emp_q9": "Unused PTO generally does not roll over unless state law requires it.",
            "emp_q10": "The handbook only mentions up to 600 USD for approved equipment after receipts are submitted.",
        },
        "expected_sources": {
            "emp_q1": ["pto_policy.md"],
            "emp_q2": ["pto_policy.md"],
            "emp_q3": ["remote_work.md"],
            "emp_q4": ["remote_work.md"],
            "emp_q5": ["security_handbook.md"],
            "emp_q6": [],
            "emp_q7": ["remote_work.md", "old_remote_memo.md"],
            "emp_q8": ["security_handbook.md"],
            "emp_q9": ["pto_policy.md"],
            "emp_q10": ["remote_work.md"],
        },
    },
    "ai_paper_qa": {
        "documents": {
            "retrieval_paper.md": """# Synthetic Retrieval Paper

## Method
The paper evaluates hybrid retrieval by combining sparse BM25 scores with dense embedding similarity before reranking the top candidates.

## Findings
Hybrid reranking improved answer citation support from 0.71 to 0.84 on the policy QA set, with a 120 ms median latency increase.
""",
            "chunking_paper.md": """# Synthetic Chunking Paper

## Chunk size
The authors found that 350-token chunks with 60-token overlap reduced boundary errors on multi-hop questions.

## Compression
Aggressive context compression removed important qualifier sentences in 18 percent of citation-sensitive answers.
""",
            "agent_memory_paper.md": """# Synthetic Agent Memory Paper

## Memory
The study warns that stale memory caused agents to reuse obsolete policy facts even when retrieval returned newer evidence.
""",
            "old_retrieval_note.md": """# Archived Retrieval Note

## Archived result
An early draft claimed dense-only retrieval outperformed hybrid retrieval. The authors later retracted this note after finding a dataset labeling bug.
""",
        },
        "questions": [
            {"id": "paper_q1", "query": "What retrieval strategy did the paper evaluate?", "type": "answerable"},
            {"id": "paper_q2", "query": "How much did hybrid reranking improve citation support?", "type": "citation-sensitive", "expected_failure": "citation_mismatch"},
            {"id": "paper_q3", "query": "What chunk size reduced boundary errors?", "type": "answerable"},
            {"id": "paper_q4", "query": "What problem did aggressive compression create?", "type": "answerable"},
            {"id": "paper_q5", "query": "Did the paper evaluate German legal contracts?", "type": "unanswerable", "expected_failure": "should_have_abstained"},
            {"id": "paper_q6", "query": "Compare the archived dense-only claim with the final retrieval result.", "type": "conflicting", "expected_failure": "conflicting_sources"},
            {"id": "paper_q7", "query": "Why can stale memory hurt agents?", "type": "answerable"},
            {"id": "paper_q8", "query": "What latency cost did reranking add?", "type": "answerable", "expected_failure": "retrieval_miss"},
            {"id": "paper_q9", "query": "What overlap did the chunking paper use?", "type": "multi-hop"},
            {"id": "paper_q10", "query": "Did hybrid retrieval reduce latency by 500 ms?", "type": "edge-case", "expected_failure": "unsupported_answer"},
        ],
        "expected_answers": {
            "paper_q1": "It evaluated hybrid retrieval combining BM25 scores with dense embedding similarity before reranking.",
            "paper_q2": "Hybrid reranking improved citation support from 0.71 to 0.84.",
            "paper_q3": "The paper used 350-token chunks.",
            "paper_q4": "Aggressive compression removed important qualifier sentences.",
            "paper_q5": "The documents do not say the paper evaluated German legal contracts.",
            "paper_q6": "The archived note claimed dense-only was better, but the final paper found hybrid reranking improved citation support.",
            "paper_q7": "Stale memory can cause agents to reuse obsolete policy facts even when newer evidence is retrieved.",
            "paper_q8": "Hybrid reranking added a 120 ms median latency increase.",
            "paper_q9": "The chunking paper used 60-token overlap.",
            "paper_q10": "No. The paper reports a 120 ms latency increase, not a 500 ms reduction.",
        },
        "expected_sources": {
            "paper_q1": ["retrieval_paper.md"],
            "paper_q2": ["retrieval_paper.md"],
            "paper_q3": ["chunking_paper.md"],
            "paper_q4": ["chunking_paper.md"],
            "paper_q5": [],
            "paper_q6": ["retrieval_paper.md", "old_retrieval_note.md"],
            "paper_q7": ["agent_memory_paper.md"],
            "paper_q8": ["retrieval_paper.md"],
            "paper_q9": ["chunking_paper.md"],
            "paper_q10": ["retrieval_paper.md"],
        },
    },
}


def load_demo_dataset(name_or_path: str) -> dict[str, Any]:
    path = _resolve_dataset_path(name_or_path)
    if path is not None:
        return _load_dataset_from_path(path)
    if name_or_path in DEMO_DATASETS:
        return {"name": name_or_path, **DEMO_DATASETS[name_or_path]}
    raise FileNotFoundError("Demo dataset not found: %s" % name_or_path)


def list_demo_datasets() -> list[str]:
    return sorted(DEMO_DATASETS)


def _resolve_dataset_path(name_or_path: str) -> Path | None:
    direct = Path(name_or_path)
    if direct.exists():
        return direct
    cwd_dataset = Path("datasets") / "demo" / name_or_path
    if cwd_dataset.exists():
        return cwd_dataset
    return None


def _load_dataset_from_path(path: Path) -> dict[str, Any]:
    documents_dir = path / "documents"
    documents = {
        document.name: document.read_text(encoding="utf-8")
        for document in sorted(documents_dir.glob("*.md"))
    }
    questions = json.loads((path / "questions.json").read_text(encoding="utf-8"))
    expected_answers = _read_optional(path / "expected_answers.json")
    expected_sources = _read_optional(path / "expected_sources.json")
    return {
        "name": path.name,
        "documents": documents,
        "questions": questions,
        "expected_answers": expected_answers,
        "expected_sources": expected_sources,
    }


def _read_optional(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
