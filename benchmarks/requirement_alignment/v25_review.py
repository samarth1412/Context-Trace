"""Export blinded, input-bound development label review; never a holdout."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.v14_fiveway_policy import LABELS, _sha256_json
from benchmarks.requirement_alignment.v25_joint_representation import encoder_pairs


def export_review(dataset: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    encoder_pairs(dataset)
    examples = sorted(
        dataset["examples"],
        key=lambda row: hashlib.sha256(
            ("v25-blinded-review|" + row["id"]).encode()
        ).hexdigest(),
    )
    rows, key_rows = [], []
    for index, example in enumerate(examples):
        review_id = f"review-{index:04d}"
        state = {
            "claim": example["input"]["claim"],
            "query": example["input"]["query"],
            "evidence": [
                {"id": f"evidence-{i:02d}", "text": span["text"]}
                for i, span in enumerate(example["input"]["evidence"])
            ],
        }
        rows.append(
            {
                "review_id": review_id,
                "input": state,
                "verdict": None,
                "rationale": None,
                "reviewer": None,
            }
        )
        key_rows.append(
            {
                "review_id": review_id,
                "case_id": example["id"],
                "input_sha256": _sha256_json(state),
                "inherited_verdict": example["target"]["verdict"],
            }
        )
    pack = {
        "purpose": "development_annotation_review_not_confirmation",
        "allowed_verdicts": list(LABELS),
        "verdict_definitions": {
            "supported": "Evidence directly entails every material part of the claim.",
            "partially_supported": "Some material facts are supported but others are missing.",
            "unsupported": "Evidence is related but does not support the claim.",
            "contradicted": "Evidence conflicts with the claim, including wrong entities, dates, numbers, negation or attribution roles.",
            "unverifiable": "Evidence is too ambiguous to decide.",
        },
        "instructions": "Judge only the displayed evidence using the existing ContextTrace definitions. Do not use outside knowledge. Fill verdict, rationale and reviewer. No model predictions or inherited labels are included.",
        "rows": rows,
    }
    key = {"dataset_sha256": _sha256_json(dataset), "rows": key_rows}
    return pack, key


def validate_review(review: dict[str, Any], key: dict[str, Any]) -> dict[str, Any]:
    expected = {row["review_id"]: row for row in key["rows"]}
    rows = review["rows"]
    ids = [row["review_id"] for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError("Review coverage must be complete and unique.")
    output = []
    for row in rows:
        binding = expected[row["review_id"]]
        if _sha256_json(row["input"]) != binding["input_sha256"]:
            raise ValueError("Reviewed evidence differs from the bound input.")
        if row["verdict"] not in LABELS or any(
            not isinstance(row.get(field), str) or not row[field].strip()
            for field in ("rationale", "reviewer")
        ):
            raise ValueError("Every row requires a verdict, rationale and reviewer.")
        output.append(
            {
                "case_id": binding["case_id"],
                "verdict": row["verdict"],
                "inherited_verdict": binding["inherited_verdict"],
                "changed": row["verdict"] != binding["inherited_verdict"],
                "input_sha256": binding["input_sha256"],
            }
        )
    return {
        "status": "development_review_complete",
        "rows": output,
        "changed_labels": sum(row["changed"] for row in output),
        "review_sha256": _sha256_json(review),
        "key_sha256": _sha256_json(key),
        "release_gate_eligible": False,
        "limitations": "Validation checks completeness and binding, not semantic correctness or reviewer independence. These consumed development cases cannot become confirmation data.",
    }


def summarize_partial_review(
    review: dict[str, Any], key: dict[str, Any], freeze: dict[str, Any]
) -> dict[str, Any]:
    """Compare locked proposals without treating them as approved labels."""
    if _sha256_json(review) != freeze.get("review_sha256"):
        raise ValueError("Review differs from the frozen pre-comparison proposals.")
    expected = {row["review_id"]: row for row in key["rows"]}
    rows = review["rows"]
    ids = [row["review_id"] for row in rows]
    if (
        len(expected) != len(key["rows"])
        or len(ids) != len(set(ids))
        or set(ids) != set(expected)
    ):
        raise ValueError("Review and key must have unique, complete matching coverage.")
    for row in rows:
        if _sha256_json(row["input"]) != expected[row["review_id"]]["input_sha256"]:
            raise ValueError("Reviewed evidence differs from the bound input.")
    reviewed = [row for row in rows if row.get("verdict") is not None]
    reviewed_ids = [row["review_id"] for row in reviewed]
    if reviewed_ids != freeze.get("reviewed_ids") or len(reviewed) != freeze.get(
        "cases_reviewed"
    ):
        raise ValueError("Reviewed coverage differs from the freeze.")
    partial_key = {**key, "rows": [expected[row_id] for row_id in reviewed_ids]}
    validated = validate_review({**review, "rows": reviewed}, partial_key)
    confusion = {label: {proposal: 0 for proposal in LABELS} for label in LABELS}
    output = []
    for row, comparison in zip(reviewed, validated["rows"], strict=True):
        evidence_ids = {span["id"] for span in row["input"]["evidence"]}
        citations = row.get("evidence_ids")
        if (
            not isinstance(citations, list)
            or not citations
            or not set(citations) <= evidence_ids
        ):
            raise ValueError("Every proposal must cite supplied evidence IDs.")
        if not isinstance(row.get("needs_adjudication"), bool) or not row.get("issue"):
            raise ValueError("Every proposal requires an issue and adjudication flag.")
        confusion[comparison["inherited_verdict"]][comparison["verdict"]] += 1
        output.append(
            {
                "review_id": row["review_id"],
                "case_id": comparison["case_id"],
                "inherited_verdict": comparison["inherited_verdict"],
                "proposed_verdict": comparison["verdict"],
                "suggested_change": comparison["changed"],
                "input_sha256": comparison["input_sha256"],
                "rationale_sha256": _sha256_json(row["rationale"]),
                "evidence_ids": citations,
                "issue": row["issue"],
                "needs_adjudication": row["needs_adjudication"],
                "reviewer_kind": row.get("reviewer_kind", "unspecified"),
            }
        )
    return {
        "experiment": "contexttrace_v25_blinded_label_review",
        "status": "partial_model_assisted_review_requires_adjudication",
        "review_sha256": _sha256_json(review),
        "key_sha256": _sha256_json(key),
        "freeze_sha256": _sha256_json(freeze),
        "dataset_sha256": key["dataset_sha256"],
        "total_cases": len(rows),
        "provisionally_reviewed": len(reviewed),
        "remaining_unreviewed": len(rows) - len(reviewed),
        "suggested_label_changes": validated["changed_labels"],
        "explicit_adjudication_flags": sum(
            row["needs_adjudication"] for row in reviewed
        ),
        "inherited_to_proposed": confusion,
        "issue_counts": dict(sorted(Counter(row["issue"] for row in reviewed).items())),
        "protocol": review.get("review_protocol", {}),
        "rows": output,
        "human_verified": False,
        "approved_label_changes": 0,
        "release_gate_eligible": False,
        "stable_defaults_changed": False,
        "candidate_retrained": False,
        "candidate_rescored_against_proposals": False,
        "limitations": "Proposals from the development assistant are not independent human annotations. Disagreement is not proof the inherited label is wrong. Validate the rubric and adjudicate before using any replacement targets.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--dataset", required=True)
    export.add_argument("--review-output", required=True)
    export.add_argument("--key-output", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--review", required=True)
    validate.add_argument("--key", required=True)
    validate.add_argument("--output", required=True)
    summarize = commands.add_parser("summarize")
    summarize.add_argument("--review", required=True)
    summarize.add_argument("--key", required=True)
    summarize.add_argument("--freeze", required=True)
    summarize.add_argument("--output", required=True)
    args = parser.parse_args()

    def load(path: str) -> dict[str, Any]:
        return json.loads(Path(path).read_text())

    if args.command == "export":
        if Path(args.review_output).exists() or Path(args.key_output).exists():
            raise FileExistsError("Refusing to overwrite an existing review or key.")
        pack, key = export_review(load(args.dataset))
        outputs = [(args.review_output, pack), (args.key_output, key)]
    elif args.command == "validate":
        outputs = [(args.output, validate_review(load(args.review), load(args.key)))]
    else:
        outputs = [
            (
                args.output,
                summarize_partial_review(
                    load(args.review), load(args.key), load(args.freeze)
                ),
            )
        ]
    for path, value in outputs:
        Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
