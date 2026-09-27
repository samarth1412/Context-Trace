"""Build V12 claim groups for local disputed-evidence ranking."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.build_v9_climate_fever import (
    DATASET_SHA256,
    _example,
    _read_jsonl,
    _sha256_file,
    _validate_source,
)
from benchmarks.requirement_alignment.build_v10_climate_development import (
    _evidence_components,
    _evidence_hashes,
)
from benchmarks.requirement_alignment.build_v11_span_training import (
    _flatten_ids,
    _load_selection,
    _sha256_json,
)


EXPERIMENT = "contexttrace_v12_conflict_ranking"
SPLIT = "climate_fever_v12_conflict_training"


class V12BuildError(RuntimeError):
    """Raised when V12 claim training violates its exclusion contract."""


def build(
    source_path: str | Path,
    consumed_v9_selection_path: str | Path,
    v10_selection_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    source_file = Path(source_path)
    if not source_file.is_file() or _sha256_file(source_file) != DATASET_SHA256:
        raise V12BuildError("Climate-FEVER source does not match its frozen SHA-256.")
    rows = _read_jsonl(source_file)
    _validate_source(rows)
    v9 = _load_selection(Path(consumed_v9_selection_path), "selected_claim_ids")
    v10 = _load_selection(Path(v10_selection_path), "development_claim_ids")
    consumed_ids = _flatten_ids(v9["selected_claim_ids"])
    development_ids = _flatten_ids(v10["development_claim_ids"])
    after_v9 = [row for row in rows if str(row["claim_id"]) not in consumed_ids]
    component_by_id, _ = _evidence_components(after_v9)
    development_components = {component_by_id[claim_id] for claim_id in development_ids}
    selected = [
        row
        for row in after_v9
        if component_by_id[str(row["claim_id"])] not in development_components
    ]
    if not selected:
        raise V12BuildError("No V12 conflict-training claims remain after exclusions.")
    examples = []
    for row in selected:
        example = _example(row)
        example["split"] = SPLIT
        example["task"] = "disputed_evidence_ranking"
        example["source"]["v12_source_partition"] = SPLIT
        examples.append(example)
    examples.sort(key=lambda row: str(row["id"]))
    training = {
        "schema_version": "contexttrace-climate-fever-v12-conflict-training-1.0",
        "experiment": EXPERIMENT,
        "split": SPLIT,
        "source": {
            "dataset": "Climate-FEVER",
            "source_file": source_file.name,
            "source_sha256": DATASET_SHA256,
            "license": "not stated on official dataset page",
            "redistribution_policy": "source text remains external",
        },
        "examples": examples,
    }
    selected_ids = {str(row["claim_id"]) for row in selected}
    development_rows = [row for row in rows if str(row["claim_id"]) in development_ids]
    counts = Counter(str(row["claim_label"]) for row in selected)
    selection = {
        "schema_version": "contexttrace-climate-fever-v12-selection-1.0",
        "experiment": EXPERIMENT,
        "algorithm": "all_claims_outside_v9_and_fixed_v10_development_evidence_components",
        "consumed_v9_claim_ids_sha256": _sha256_json(sorted(consumed_ids)),
        "fixed_v10_development_claim_ids_sha256": _sha256_json(sorted(development_ids)),
        "selected_claim_ids_sha256": _sha256_json(sorted(selected_ids)),
        "model_outputs_used": False,
        "source_text_included": False,
    }
    audit = {
        "schema_version": "contexttrace-climate-fever-v12-audit-1.0",
        "experiment": EXPERIMENT,
        "counts": {
            "claims": len(selected),
            "claim_labels": dict(sorted(counts.items())),
            "evidence_spans": sum(len(row["evidences"]) for row in selected),
            "evidence_components": len(
                {component_by_id[str(row["claim_id"])] for row in selected}
            ),
        },
        "checks": {
            "source_hash_verified": True,
            "all_v9_claim_ids_excluded": not bool(consumed_ids & selected_ids),
            "all_v10_development_components_excluded": all(
                component_by_id[str(row["claim_id"])] not in development_components
                for row in selected
            ),
            "exact_evidence_disjoint_from_v10_development": not bool(
                _evidence_hashes(selected) & _evidence_hashes(development_rows)
            ),
            "labels_absent_from_inputs": all(
                not ({"label", "target", "relation"} & set(row["input"]))
                for row in examples
            ),
            "model_outputs_used_for_selection": False,
        },
        "redistribution": {
            "source_text_committed": False,
            "committed_receipts_contain_only_hashes_and_aggregates": True,
        },
        "limitations": [
            "Training and development share the Climate-FEVER domain despite exact-evidence exclusion.",
            "Training claims can share evidence inside the training partition.",
            "The fixed V10 development set is for selection and cannot serve as release confirmation.",
        ],
    }
    manifest = {
        "schema_version": "contexttrace-climate-fever-v12-manifest-1.0",
        "experiment": EXPERIMENT,
        "status": "conflict_training_data_frozen_before_v12_scoring",
        "source_sha256": DATASET_SHA256,
        "training_sha256": _sha256_json(training),
        "selection_sha256": _sha256_json(selection),
        "audit_sha256": _sha256_json(audit),
        "v10_development_remains_fixed": True,
        "v9_holdout_reused": False,
        "model_outputs_accessed": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
    }
    return training, selection, audit, manifest


def _write(path: str | Path, value: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--consumed-v9-selection", required=True)
    parser.add_argument("--v10-selection", required=True)
    parser.add_argument("--training-output", required=True)
    parser.add_argument("--selection-output", required=True)
    parser.add_argument("--audit-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    args = parser.parse_args(argv)
    values = build(args.source, args.consumed_v9_selection, args.v10_selection)
    for path, value in zip(
        (
            args.training_output,
            args.selection_output,
            args.audit_output,
            args.manifest_output,
        ),
        values,
        strict=True,
    ):
        _write(path, value)
    training, _, audit, manifest = values
    print(
        json.dumps(
            {
                "training_sha256": manifest["training_sha256"],
                "cases": len(training["examples"]),
                "counts": audit["counts"],
                "checks": audit["checks"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
