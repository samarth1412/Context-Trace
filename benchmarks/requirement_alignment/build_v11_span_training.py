"""Build the V11 high-consensus evidence-relation training set."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.build_v9_climate_fever import (
    DATASET_SHA256,
    LABELS,
    _read_jsonl,
    _sha256_file,
    _validate_source,
)
from benchmarks.requirement_alignment.build_v10_climate_development import (
    _evidence_components,
)


EXPERIMENT = "contexttrace_v11_high_consensus_relations"
SPLIT = "climate_fever_v11_span_training"
RELATIONS = {
    "SUPPORTS": "entailment",
    "REFUTES": "contradiction",
    "NOT_ENOUGH_INFO": "neutral",
}


class V11BuildError(RuntimeError):
    """Raised when V11 training data violates its frozen exclusion contract."""


def build(
    source_path: str | Path,
    consumed_v9_selection_path: str | Path,
    v10_selection_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    source_file = Path(source_path)
    if not source_file.is_file() or _sha256_file(source_file) != DATASET_SHA256:
        raise V11BuildError("Climate-FEVER source does not match its frozen SHA-256.")
    rows = _read_jsonl(source_file)
    _validate_source(rows)
    v9 = _load_selection(Path(consumed_v9_selection_path), "selected_claim_ids")
    v10 = _load_selection(Path(v10_selection_path), "development_claim_ids")
    consumed_ids = _flatten_ids(v9["selected_claim_ids"])
    development_ids = _flatten_ids(v10["development_claim_ids"])
    source_ids = {str(row["claim_id"]) for row in rows}
    if not consumed_ids or not development_ids:
        raise V11BuildError("V9 and V10 exclusions must be non-empty.")
    if not (consumed_ids | development_ids) <= source_ids:
        raise V11BuildError("Exclusion IDs do not match the Climate-FEVER source.")

    after_v9 = [row for row in rows if str(row["claim_id"]) not in consumed_ids]
    component_by_id, _ = _evidence_components(after_v9)
    development_components = {component_by_id[claim_id] for claim_id in development_ids}
    eligible_claims = [
        row
        for row in after_v9
        if component_by_id[str(row["claim_id"])] not in development_components
    ]
    examples = []
    for row in eligible_claims:
        claim_id = str(row["claim_id"])
        claim = str(row["claim"]).strip()
        for index, evidence in enumerate(row["evidences"]):
            if float(evidence["entropy"]) != 0.0:
                continue
            label = str(evidence["evidence_label"])
            if label not in RELATIONS:
                raise V11BuildError("Unknown evidence relation label.")
            article = str(evidence["article"]).strip()
            text = str(evidence["evidence"]).strip()
            rendered = f"{article}: {text}" if article else text
            examples.append(
                {
                    "id": f"climate_fever_{claim_id}_span_{index:02d}",
                    "split": SPLIT,
                    "task": "evidence_relation",
                    "input": {
                        "claim": claim,
                        "evidence": {
                            "id": f"climate_fever_{claim_id}_e{index:02d}",
                            "text": rendered,
                        },
                    },
                    "target": {"relation": RELATIONS[label]},
                    "source": {
                        "dataset": "Climate-FEVER",
                        "claim_id": claim_id,
                        "claim_label": str(row["claim_label"]),
                        "upstream_evidence_id": str(evidence["evidence_id"]),
                        "evidence_label": label,
                        "annotation_entropy": 0.0,
                        "rendered_text_sha256": hashlib.sha256(
                            rendered.encode("utf-8")
                        ).hexdigest(),
                    },
                }
            )
    examples.sort(key=lambda row: str(row["id"]))
    if not examples or len({row["id"] for row in examples}) != len(examples):
        raise V11BuildError("V11 span IDs must be non-empty and unique.")

    training = {
        "schema_version": "contexttrace-climate-fever-v11-span-training-1.0",
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
    span_counts = Counter(str(row["target"]["relation"]) for row in examples)
    claim_counts = Counter(str(row["claim_label"]) for row in eligible_claims)
    training_evidence_hashes = {
        str(row["source"]["rendered_text_sha256"]) for row in examples
    }
    development_rows = [row for row in rows if str(row["claim_id"]) in development_ids]
    development_evidence_hashes = {
        _rendered_hash(evidence)
        for row in development_rows
        for evidence in row["evidences"]
    }
    selection = {
        "schema_version": "contexttrace-climate-fever-v11-selection-1.0",
        "experiment": EXPERIMENT,
        "algorithm": "all_claims_outside_v9_and_v10_development_components_with_zero_entropy_evidence",
        "consumed_v9_claim_ids_sha256": _sha256_json(sorted(consumed_ids)),
        "fixed_v10_development_claim_ids_sha256": _sha256_json(sorted(development_ids)),
        "eligible_claim_ids_sha256": _sha256_json(
            sorted(str(row["claim_id"]) for row in eligible_claims)
        ),
        "selected_span_ids_sha256": _sha256_json([str(row["id"]) for row in examples]),
        "annotation_entropy_required": 0.0,
        "model_outputs_used": False,
        "source_text_included": False,
    }
    audit = {
        "schema_version": "contexttrace-climate-fever-v11-audit-1.0",
        "experiment": EXPERIMENT,
        "counts": {
            "eligible_claims": len(eligible_claims),
            "eligible_claim_labels": dict(sorted(claim_counts.items())),
            "selected_spans": len(examples),
            "selected_relations": dict(sorted(span_counts.items())),
            "unique_selected_evidence_texts": len(training_evidence_hashes),
        },
        "checks": {
            "source_hash_verified": True,
            "all_v9_claim_ids_excluded": not bool(
                consumed_ids & {str(row["claim_id"]) for row in eligible_claims}
            ),
            "all_v10_development_components_excluded": all(
                component_by_id[str(row["claim_id"])] not in development_components
                for row in eligible_claims
            ),
            "exact_evidence_disjoint_from_v10_development": not bool(
                training_evidence_hashes & development_evidence_hashes
            ),
            "all_selected_annotations_unanimous": all(
                float(row["source"]["annotation_entropy"]) == 0.0 for row in examples
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
            "Training and V10 development are exact-evidence disjoint but share the Climate-FEVER source domain.",
            "Claims inside the training partition may share evidence and are not independent evaluation units.",
            "Zero annotation entropy indicates agreement among available votes, not guaranteed factual correctness.",
            "The next confirmation must use a different untouched dataset.",
        ],
    }
    manifest = {
        "schema_version": "contexttrace-climate-fever-v11-manifest-1.0",
        "experiment": EXPERIMENT,
        "status": "training_data_frozen_before_v11_model_training",
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


def _load_selection(path: Path, field: str) -> dict[str, Any]:
    if not path.is_file():
        raise V11BuildError("A required selection receipt is missing.")
    value = json.loads(path.read_text(encoding="utf-8"))
    selected = value.get(field)
    if not isinstance(selected, dict) or set(selected) != set(LABELS):
        raise V11BuildError("Selection receipt has an invalid label mapping.")
    return value


def _flatten_ids(values: dict[str, list[str]]) -> set[str]:
    return {str(claim_id) for rows in values.values() for claim_id in rows}


def _rendered_hash(evidence: dict[str, Any]) -> str:
    article = str(evidence["article"]).strip()
    text = str(evidence["evidence"]).strip()
    rendered = f"{article}: {text}" if article else text
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
    training, selection, audit, manifest = build(
        args.source, args.consumed_v9_selection, args.v10_selection
    )
    for path, value in (
        (args.training_output, training),
        (args.selection_output, selection),
        (args.audit_output, audit),
        (args.manifest_output, manifest),
    ):
        _write(path, value)
    print(
        json.dumps(
            {
                "training_sha256": manifest["training_sha256"],
                "counts": audit["counts"],
                "checks": audit["checks"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
