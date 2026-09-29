"""Export blinded, input-bound development label review; never a holdout."""

from __future__ import annotations

import argparse
import hashlib
import json
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
    args = parser.parse_args()

    def load(path: str) -> dict[str, Any]:
        return json.loads(Path(path).read_text())

    if args.command == "export":
        if Path(args.review_output).exists() or Path(args.key_output).exists():
            raise FileExistsError("Refusing to overwrite an existing review or key.")
        pack, key = export_review(load(args.dataset))
        outputs = [(args.review_output, pack), (args.key_output, key)]
    else:
        outputs = [(args.output, validate_review(load(args.review), load(args.key)))]
    for path, value in outputs:
        Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
