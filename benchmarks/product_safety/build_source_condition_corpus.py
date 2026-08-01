"""Generate the source-family-disjoint source-condition development corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE / "source_condition_development_cases.json"
BUILDER_VERSION = "contexttrace-source-condition-builder-v1.0.0"

_TOPICS = (
    {
        "id": "timeout",
        "query": "What is the current API timeout?",
        "old": "The API timeout is 60 seconds.",
        "new": "The API timeout is 30 seconds.",
    },
    {
        "id": "deadline",
        "query": "What is the current filing deadline?",
        "old": "The filing deadline is September 1.",
        "new": "The filing deadline is October 1.",
    },
    {
        "id": "retention",
        "query": "What is the current retention period?",
        "old": "The retention period is 90 days.",
        "new": "The retention period is 30 days.",
    },
    {
        "id": "endpoint",
        "query": "Which endpoint is current?",
        "old": "The search endpoint is /v1/search.",
        "new": "The search endpoint is /v2/search.",
    },
    {
        "id": "client",
        "query": "Which client version is current?",
        "old": "Clients must use API v1.0.",
        "new": "Clients must use API v2.0.",
    },
    {
        "id": "logging",
        "query": "Is audit logging currently enabled?",
        "old": "Audit logging is enabled by default.",
        "new": "Audit logging is disabled by default.",
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
    old_id = f"{topic['id']}-old"
    current_id = f"{topic['id']}-current"
    definitions = (
        (
            "current_canonical",
            "current_canonical",
            [
                {
                    "id": old_id,
                    "text": topic["old"],
                    "metadata": {"canonical": True, "current": True},
                }
            ],
        ),
        (
            "current_noncanonical",
            "current_noncanonical",
            [
                {
                    "id": old_id,
                    "text": topic["old"],
                    "metadata": {"canonical": "false", "current": "true"},
                }
            ],
        ),
        (
            "stale_explicit",
            "stale",
            [
                {
                    "id": old_id,
                    "text": topic["old"],
                    "metadata": {
                        "source_condition": "current_canonical",
                        "stale": True,
                    },
                }
            ],
        ),
        (
            "superseded_relation",
            "superseded",
            [
                {
                    "id": old_id,
                    "text": topic["old"],
                    "metadata": {"source_version": "1.0"},
                },
                {
                    "id": current_id,
                    "text": topic["new"],
                    "metadata": {"source_version": "2.0", "replaces": old_id},
                },
            ],
        ),
        (
            "superseded_version_conflict",
            "superseded",
            [
                {
                    "id": old_id,
                    "text": topic["old"],
                    "metadata": {
                        "source_family": topic["id"],
                        "source_version": "1.0",
                        "canonical": True,
                    },
                },
                {
                    "id": current_id,
                    "text": topic["new"],
                    "metadata": {
                        "source_family": topic["id"],
                        "source_version": "2.0",
                        "canonical": True,
                    },
                },
            ],
        ),
        (
            "stale_newer_same_fact",
            "stale",
            [
                {
                    "id": old_id,
                    "text": topic["old"],
                    "metadata": {
                        "source_group": topic["id"],
                        "published_at": "2025-01-01",
                    },
                },
                {
                    "id": current_id,
                    "text": topic["old"],
                    "metadata": {
                        "source_group": topic["id"],
                        "published_at": "2026-01-01",
                    },
                },
            ],
        ),
        (
            "low_authority",
            "low_authority",
            [
                {
                    "id": old_id,
                    "text": topic["old"],
                    "metadata": {"source_authority": "summary"},
                }
            ],
        ),
        (
            "conflicting_authorities",
            "conflicting_authorities",
            [
                {
                    "id": old_id,
                    "text": topic["old"],
                    "metadata": {"source_authority": "official", "current": True},
                },
                {
                    "id": current_id,
                    "text": topic["new"],
                    "metadata": {"source_authority": "regulator", "current": True},
                },
            ],
        ),
        (
            "unknown",
            "unknown",
            [{"id": old_id, "text": topic["old"], "metadata": {}}],
        ),
    )
    return [
        {
            "id": f"{category}__{topic['id']}",
            "category": category,
            "split": split,
            "source_family": f"{category}:{topic['id']}",
            "query": topic["query"],
            "answer": topic["old"],
            "contexts": contexts,
            "expected_source_condition": expected,
        }
        for category, expected, contexts in definitions
    ]


def _assert_disjoint(cases: list[dict[str, Any]]) -> None:
    families = {
        split: {case["source_family"] for case in cases if case["split"] == split}
        for split in ("development", "heldout_development")
    }
    if families["development"] & families["heldout_development"]:
        raise ValueError("Source-family leakage between development splits.")


def _canonical_sha256(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
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
            raise SystemExit("Source-condition corpus is missing or stale.")
        return 0
    args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
