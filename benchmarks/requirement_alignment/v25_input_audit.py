"""Audit V21 question fragmentation and restore only selected QA records."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.build_v19_confirmation import _require_hash
from benchmarks.requirement_alignment.build_v21_development import (
    AVERITEC_TRAIN_SHA256,
    SPLIT,
    _averitec_train_candidates,
)
from benchmarks.requirement_alignment.v14_fiveway_policy import _sha256_json


class V25InputError(ValueError):
    """Reject inputs that cannot be restored exactly from pinned source data."""


def question_only(text: str) -> bool:
    return text.startswith("Question:") and "\nAnswer:" not in text


def restore_selected_records(
    model_input: dict[str, Any], contexts: list[dict[str, str]]
) -> dict[str, Any]:
    """Restore the QA unit of a selected fragment, without selecting new records."""
    if set(model_input) != {"query", "claim", "evidence"}:
        raise V25InputError("Model input must contain only query, claim, evidence.")
    lookup = {row["id"]: row["text"] for row in contexts}
    restored = []
    seen = set()
    for span in model_input["evidence"]:
        try:
            root, start, end = span["id"].rsplit(":", 2)
            start, end = int(start), int(end)
        except (KeyError, ValueError) as exc:
            raise V25InputError("Selected span has no source offsets.") from exc
        if root not in lookup or not 0 <= start < end <= len(lookup[root]):
            raise V25InputError("Selected span does not bind to a source QA record.")
        if lookup[root][start:end] != span["text"]:
            raise V25InputError("Selected span text differs from the source offsets.")
        if root not in seen:
            restored.append({"id": root, "text": lookup[root]})
            seen.add(root)
    return {**model_input, "evidence": restored}


def audit_and_restore(
    dataset: dict[str, Any], source_candidates: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    if dataset.get("split") != SPLIT or not dataset.get("examples"):
        raise V25InputError("Only the consumed V21 development set is accepted.")
    sources = {row["id"]: row for row in source_candidates}
    repaired = copy.deepcopy(dataset)
    repaired["experiment"] = "contexttrace_v25_qa_integrity_development"
    counts: Counter[str] = Counter()
    per_label: dict[str, Counter[str]] = defaultdict(Counter)
    source_labels: dict[str, Counter[str]] = defaultdict(Counter)
    audit_rows = []
    seen = set()
    for row in repaired["examples"]:
        if row["id"] in seen:
            raise V25InputError("Duplicate case IDs.")
        seen.add(row["id"])
        if set(row["input"]) != {"query", "claim", "evidence"}:
            raise V25InputError("Labels or metadata in model inputs.")
        source_labels[row["source"]["dataset"]][row["target"]["verdict"]] += 1
        if row["source"]["dataset"] != "AVeriTeC":
            continue
        source = sources.get(row["id"])
        if source is None or source["claim"] != row["input"]["claim"]:
            raise V25InputError("Source claim or ID mismatch.")
        original = row["input"]
        spans = original["evidence"]
        questions = [span for span in spans if question_only(span["text"])]
        answer_roots = {
            span["id"].rsplit(":", 2)[0]
            for span in spans
            if not question_only(span["text"])
        }
        orphans = [
            span
            for span in questions
            if span["id"].rsplit(":", 2)[0] not in answer_roots
        ]
        row["input"] = restore_selected_records(original, source["contexts"])
        row["source"]["selected_span_count"] = len(row["input"]["evidence"])
        values = {
            "cases": 1,
            "selected_spans": len(spans),
            "question_only_spans": len(questions),
            "question_only_cases": int(bool(spans) and len(questions) == len(spans)),
            "orphan_question_cases": int(bool(orphans)),
            "restored_qa_records": len(row["input"]["evidence"]),
        }
        counts.update(values)
        per_label[row["target"]["verdict"]].update(values)
        audit_rows.append(
            {
                "case_id": row["id"],
                "expected_verdict": row["target"]["verdict"],
                "original_input_sha256": _sha256_json(original),
                "restored_input_sha256": _sha256_json(row["input"]),
                "original_characters": sum(len(span["text"]) for span in spans),
                "restored_characters": sum(
                    len(span["text"]) for span in row["input"]["evidence"]
                ),
                **values,
            }
        )
    report = {
        "experiment": "contexttrace_v25_input_audit",
        "status": "benchmark_input_defect_confirmed",
        "original_dataset_sha256": _sha256_json(dataset),
        "restored_dataset_sha256": _sha256_json(repaired),
        "counts": dict(counts),
        "by_label": {key: dict(value) for key, value in per_label.items()},
        "source_label_counts": {
            key: dict(value) for key, value in source_labels.items()
        },
        "rows": audit_rows,
        "label_validity": {
            "inherited_upstream_labels": True,
            "independent_selected_evidence_annotation": False,
            "all_partial_support_cases_from_one_source": True,
            "automatic_relabeling_performed": False,
            "release_gate_eligible": False,
        },
        "repair": {
            "selected_qa_roots_only": True,
            "source_offsets_verified": True,
            "unselected_qa_records_added": False,
            "answers_or_explanations_generated": False,
            "wice_inputs_unchanged": True,
            "stable_selector_changed": False,
        },
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "future_confirmation_loaded": False,
        "decision": "repair_development_inputs_and_review_labels_before_promotion",
    }
    return repaired, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--averitec-train", required=True)
    parser.add_argument("--dataset-output", required=True)
    parser.add_argument("--audit-output", required=True)
    args = parser.parse_args()
    _require_hash(Path(args.averitec_train), AVERITEC_TRAIN_SHA256)
    dataset = json.loads(Path(args.dataset).read_text())
    repaired, audit = audit_and_restore(
        dataset, _averitec_train_candidates(Path(args.averitec_train))
    )
    for path, value in [(args.dataset_output, repaired), (args.audit_output, audit)]:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": audit["status"], "counts": audit["counts"]}, indent=2))


if __name__ == "__main__":
    main()
