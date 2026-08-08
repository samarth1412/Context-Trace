"""Generate the source-family-disjoint evidence-attribution development corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE / "evidence_attribution_development_cases.json"
BUILDER_VERSION = "contexttrace-evidence-attribution-builder-v1.0.0"

_TOPICS = (
    {
        "id": "release",
        "query": "What is required for a production release?",
        "claim": "A production release requires security approval within 24 hours.",
        "part1": "A production release requires security approval.",
        "part2": "Approval must occur within 24 hours.",
        "wrong": "A production release requires security approval within 48 hours.",
        "unsupported": "A production release uses quantum signing.",
    },
    {
        "id": "refund",
        "query": "What qualifies for a refund?",
        "claim": "Refund requests require unopened items within 30 days.",
        "part1": "Refund requests require unopened items.",
        "part2": "Requests must be submitted within 30 days.",
        "wrong": "Refund requests require unopened items within 90 days.",
        "unsupported": "Refund requests include international concierge service.",
    },
    {
        "id": "backup",
        "query": "How are enterprise snapshots retained?",
        "claim": "Enterprise backups retain encrypted snapshots for 90 days.",
        "part1": "Enterprise backups retain encrypted snapshots.",
        "part2": "Encrypted snapshots remain available for 90 days.",
        "wrong": "Enterprise backups retain encrypted snapshots for 30 days.",
        "unsupported": "Enterprise backups use lunar storage.",
    },
    {
        "id": "search",
        "query": "How must search requests be made?",
        "claim": "Search requests require OAuth at /v2/search.",
        "part1": "The search endpoint is /v2/search.",
        "part2": "Search requests require OAuth.",
        "wrong": "Search requests require OAuth at /v1/search.",
        "unsupported": "Search requests include unlimited translation.",
    },
    {
        "id": "audit",
        "query": "How are audit records stored?",
        "claim": "Audit records require encrypted storage for 30 days.",
        "part1": "Audit records require encrypted storage.",
        "part2": "Audit records are retained for 30 days.",
        "wrong": "Audit records require encrypted storage for 60 days.",
        "unsupported": "Audit records are delivered by drone.",
    },
    {
        "id": "migration",
        "query": "What is required for migration jobs?",
        "claim": "Migration jobs require administrator approval before July 1.",
        "part1": "Migration jobs require administrator approval.",
        "part2": "Approval must occur before July 1.",
        "wrong": "Migration jobs require administrator approval before July 10.",
        "unsupported": "Migration jobs guarantee zero downtime worldwide.",
    },
    {
        "id": "cafe",
        "query": "What is required for café access?",
        "claim": "Café access requires résumé approval within 14 days.",
        "part1": "Café access requires résumé approval.",
        "part2": "Approval must occur within 14 days.",
        "wrong": "Café access requires résumé approval within 40 days.",
        "unsupported": "Café access includes orbital delivery.",
    },
)


def build_corpus() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for index, topic in enumerate(_TOPICS):
        split = "development" if index < 4 else "heldout_development"
        cases.extend(_cases_for_topic(topic, split))
    _assert_disjoint(cases)
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "builder_version": BUILDER_VERSION,
        "evidence_class": "synthetic_development_only_not_research_evidence",
        "cases": cases,
        "counts": {
            split: sum(case["split"] == split for case in cases)
            for split in ("development", "heldout_development")
        },
    }
    payload["payload_sha256"] = _canonical_sha256(payload)
    return payload


def _cases_for_topic(topic: dict[str, str], split: str) -> list[dict[str, Any]]:
    metadata = {"canonical": True, "current": True}
    exact_text = f"Overview. {topic['claim']} Contact support for unrelated questions."
    multi_text = (
        f"{topic['part1']} {topic['part2']} Contact support for unrelated questions."
    )
    refuting_text = (
        f"Overview. {topic['claim']} Contact support for unrelated questions."
    )
    definitions = (
        (
            "minimal_exact",
            topic["claim"],
            [{"id": "primary", "text": exact_text, "metadata": metadata}],
            [("primary", topic["claim"], "supporting")],
        ),
        (
            "multi_span_one_document",
            topic["claim"],
            [{"id": "primary", "text": multi_text, "metadata": metadata}],
            [
                ("primary", topic["part1"], "supporting"),
                ("primary", topic["part2"], "supporting"),
            ],
        ),
        (
            "multi_span_two_documents",
            topic["claim"],
            [
                {"id": "policy", "text": topic["part1"], "metadata": metadata},
                {"id": "schedule", "text": topic["part2"], "metadata": metadata},
            ],
            [
                ("policy", topic["part1"], "supporting"),
                ("schedule", topic["part2"], "supporting"),
            ],
        ),
        (
            "minimal_refuting",
            topic["wrong"],
            [{"id": "primary", "text": refuting_text, "metadata": metadata}],
            [("primary", topic["claim"], "contradicting")],
        ),
        (
            "duplicate_support",
            topic["claim"],
            [
                {"id": "primary", "text": topic["claim"], "metadata": metadata},
                {"id": "duplicate", "text": topic["claim"], "metadata": metadata},
            ],
            [("primary", topic["claim"], "supporting")],
        ),
        (
            "unsupported_empty",
            topic["unsupported"],
            [
                {
                    "id": "unrelated",
                    "text": "Account owners can update their billing address.",
                    "metadata": metadata,
                }
            ],
            [],
        ),
    )
    return [
        _case(
            case_id=f"{category}__{topic['id']}",
            category=category,
            split=split,
            query=topic["query"],
            answer=answer,
            contexts=contexts,
            expected=expected,
        )
        for category, answer, contexts, expected in definitions
    ]


def _case(
    *,
    case_id: str,
    category: str,
    split: str,
    query: str,
    answer: str,
    contexts: list[dict[str, Any]],
    expected: list[tuple[str, str, str]],
) -> dict[str, Any]:
    expected_spans = []
    for context_id, text, role in expected:
        context = next(item for item in contexts if item["id"] == context_id)
        start = str(context["text"]).find(text)
        if start < 0 or str(context["text"]).count(text) != 1:
            raise ValueError(f"Expected span must occur exactly once in {case_id}.")
        expected_spans.append(
            {
                "context_id": context_id,
                "start_char": start,
                "end_char": start + len(text),
                "text": text,
                "role": role,
            }
        )
    return {
        "id": case_id,
        "category": category,
        "split": split,
        "source_family": f"{category}:{case_id.rsplit('__', 1)[-1]}",
        "query": query,
        "answer": answer,
        "contexts": contexts,
        "expected_spans": expected_spans,
    }


def _assert_disjoint(cases: list[dict[str, Any]]) -> None:
    families = {
        split: {case["source_family"] for case in cases if case["split"] == split}
        for split in ("development", "heldout_development")
    }
    if families["development"] & families["heldout_development"]:
        raise ValueError("Source-family leakage between attribution splits.")


def _canonical_sha256(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rendered = json.dumps(build_corpus(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != rendered
        ):
            raise SystemExit("Evidence-attribution corpus is missing or stale.")
        return 0
    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
