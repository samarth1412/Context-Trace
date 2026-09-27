"""Build leakage-controlled V10 Climate-FEVER training and development sets."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.build_v9_climate_fever import (
    DATASET_SHA256,
    LABELS,
    _example,
    _read_jsonl,
    _sha256_file,
    _validate_source,
)


EXPERIMENT = "contexttrace_v10_climate_development"
TRAINING_SPLIT = "climate_fever_v10_training"
DEVELOPMENT_SPLIT = "climate_fever_v10_development"
SEED_MATERIAL = "contexttrace-climate-fever-v10|split|claim_label|claim_id"


class V10BuildError(RuntimeError):
    """Raised when V10 data violates its exclusion or split contract."""


def build(
    source_path: str | Path,
    consumed_selection_path: str | Path,
    *,
    training_per_label: int = 75,
    development_per_label: int = 15,
) -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]
]:
    source_file = Path(source_path)
    selection_file = Path(consumed_selection_path)
    if not source_file.is_file() or _sha256_file(source_file) != DATASET_SHA256:
        raise V10BuildError("Climate-FEVER source does not match its frozen SHA-256.")
    if training_per_label < 1 or development_per_label < 1:
        raise V10BuildError("Per-label split sizes must be positive.")
    rows = _read_jsonl(source_file)
    _validate_source(rows)
    consumed_selection = _load_selection(selection_file)
    consumed_ids = {
        str(claim_id)
        for values in consumed_selection["selected_claim_ids"].values()
        for claim_id in values
    }
    source_ids = {str(row["claim_id"]) for row in rows}
    if not consumed_ids or not consumed_ids <= source_ids:
        raise V10BuildError("Consumed holdout IDs do not match the source dataset.")
    remaining = [row for row in rows if str(row["claim_id"]) not in consumed_ids]
    component_by_id, components = _evidence_components(remaining)
    largest_component = max(components, key=lambda key: len(components[key]))

    development, development_components = _select_development(
        remaining,
        component_by_id,
        largest_component=largest_component,
        per_label=development_per_label,
    )
    training = _select_training(
        remaining,
        component_by_id,
        excluded_components=development_components,
        per_label=training_per_label,
    )
    training_ids = {str(row["claim_id"]) for row in training}
    development_ids = {str(row["claim_id"]) for row in development}
    if (
        training_ids & development_ids
        or (training_ids | development_ids) & consumed_ids
    ):
        raise V10BuildError("Training, development, and consumed IDs must be disjoint.")
    training_evidence = _evidence_hashes(training)
    development_evidence = _evidence_hashes(development)
    if training_evidence & development_evidence:
        raise V10BuildError("Training and development evidence must be disjoint.")

    training_payload = _dataset_payload(
        training, source_file=source_file, split=TRAINING_SPLIT
    )
    development_payload = _dataset_payload(
        development, source_file=source_file, split=DEVELOPMENT_SPLIT
    )
    selection = {
        "schema_version": "contexttrace-climate-fever-v10-selection-1.0",
        "experiment": EXPERIMENT,
        "algorithm": "sha256_order_with_evidence_component_exclusion_v1",
        "seed_material": SEED_MATERIAL,
        "training_per_label": training_per_label,
        "development_per_label": development_per_label,
        "consumed_v9_selection_sha256": _sha256_json(consumed_selection),
        "consumed_claim_ids_sha256": _sha256_json(sorted(consumed_ids)),
        "training_claim_ids": _ids_by_label(training),
        "development_claim_ids": _ids_by_label(development),
        "model_outputs_used": False,
        "source_text_included": False,
    }
    consumed_rows = [row for row in rows if str(row["claim_id"]) in consumed_ids]
    audit = {
        "schema_version": "contexttrace-climate-fever-v10-audit-1.0",
        "experiment": EXPERIMENT,
        "source": {
            "dataset": "Climate-FEVER",
            "source_file": source_file.name,
            "source_sha256": DATASET_SHA256,
            "license": "not stated on official dataset page",
            "redistribution_policy": "source text remains external",
        },
        "counts": {
            "source": _label_counts(rows),
            "consumed_v9_holdout": _label_counts(consumed_rows),
            "remaining_after_claim_exclusion": _label_counts(remaining),
            "training": _label_counts(training),
            "development": _label_counts(development),
            "evidence_components": len(components),
            "largest_evidence_component_claims": len(components[largest_component]),
            "development_components": len(development_components),
        },
        "checks": {
            "source_hash_verified": True,
            "all_consumed_v9_claim_ids_excluded": not bool(
                (training_ids | development_ids) & consumed_ids
            ),
            "training_development_claim_ids_disjoint": not bool(
                training_ids & development_ids
            ),
            "training_development_exact_evidence_disjoint": not bool(
                training_evidence & development_evidence
            ),
            "development_uses_one_claim_per_evidence_component": len(development)
            == len(development_components),
            "balanced_training_labels": len(_label_counts(training)["labels"]) == 4
            and len(set(_label_counts(training)["labels"].values())) == 1,
            "balanced_development_labels": len(_label_counts(development)["labels"])
            == 4
            and len(set(_label_counts(development)["labels"].values())) == 1,
            "labels_absent_from_inputs": all(
                not ({"label", "target", "relation"} & set(example["input"]))
                for example in training_payload["examples"]
                + development_payload["examples"]
            ),
            "model_outputs_used_for_selection": False,
            "synthetic_claims_used": False,
            "synthetic_evidence_used": False,
        },
        "holdout_boundary": {
            "v9_claim_ids_excluded": len(consumed_ids),
            "v9_is_consumed_and_will_not_be_reused_for_selection_or_confirmation": True,
            "future_confirmation_must_use_a_different_dataset": True,
            "exact_evidence_overlap_with_consumed_v9": {
                "training": len(training_evidence & _evidence_hashes(consumed_rows)),
                "development": len(
                    development_evidence & _evidence_hashes(consumed_rows)
                ),
                "permitted_because_v9_will_not_be_reused": True,
            },
        },
        "redistribution": {
            "source_text_committed": False,
            "committed_selection_contains_only_ids_and_aggregates": True,
        },
        "limitations": [
            "Climate-FEVER has one public collection rather than official train and development splits.",
            "Exact evidence is disjoint between V10 training and development, but broad topics and articles may overlap.",
            "Some selected evidence may overlap the consumed V9 holdout; V9 is never reused for tuning or confirmation.",
            "The future confirmation set must come from a different dataset and remain untouched until policy freeze.",
            "The official page does not state a redistribution license, so generated text-bearing datasets stay external.",
        ],
    }
    manifest = {
        "schema_version": "contexttrace-climate-fever-v10-manifest-1.0",
        "experiment": EXPERIMENT,
        "status": "development_data_frozen_before_model_training",
        "source_sha256": DATASET_SHA256,
        "consumed_v9_selection_sha256": _sha256_json(consumed_selection),
        "training_sha256": _sha256_json(training_payload),
        "development_sha256": _sha256_json(development_payload),
        "selection_sha256": _sha256_json(selection),
        "audit_sha256": _sha256_json(audit),
        "model_outputs_accessed": False,
        "v9_holdout_reused": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
    }
    return training_payload, development_payload, selection, audit, manifest


def _select_development(
    rows: list[dict[str, Any]],
    component_by_id: dict[str, str],
    *,
    largest_component: str,
    per_label: int,
) -> tuple[list[dict[str, Any]], set[str]]:
    selected: list[dict[str, Any]] = []
    used_components: set[str] = set()
    for label in ("DISPUTED", "REFUTES", "NOT_ENOUGH_INFO", "SUPPORTS"):
        candidates = sorted(
            (row for row in rows if row["claim_label"] == label),
            key=lambda row: _selection_digest(
                "development", label, str(row["claim_id"])
            ),
        )
        label_rows = []
        for row in candidates:
            component = component_by_id[str(row["claim_id"])]
            if component == largest_component or component in used_components:
                continue
            label_rows.append(row)
            used_components.add(component)
            if len(label_rows) == per_label:
                break
        if len(label_rows) != per_label:
            raise V10BuildError(
                f"Only {len(label_rows)} evidence-disjoint development cases available for {label}."
            )
        selected.extend(label_rows)
    return sorted(selected, key=lambda row: str(row["claim_id"])), used_components


def _select_training(
    rows: list[dict[str, Any]],
    component_by_id: dict[str, str],
    *,
    excluded_components: set[str],
    per_label: int,
) -> list[dict[str, Any]]:
    selected = []
    for label in LABELS:
        candidates = sorted(
            (
                row
                for row in rows
                if row["claim_label"] == label
                and component_by_id[str(row["claim_id"])] not in excluded_components
            ),
            key=lambda row: _selection_digest("training", label, str(row["claim_id"])),
        )
        if len(candidates) < per_label:
            raise V10BuildError(
                f"Only {len(candidates)} training cases available for {label}."
            )
        selected.extend(candidates[:per_label])
    return sorted(selected, key=lambda row: str(row["claim_id"]))


def _evidence_components(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, list[str]]]:
    parent = list(range(len(rows)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    owner: dict[str, int] = {}
    for index, row in enumerate(rows):
        for evidence_hash in _row_evidence_hashes(row):
            if evidence_hash in owner:
                union(index, owner[evidence_hash])
            else:
                owner[evidence_hash] = index
    raw_components: dict[int, list[str]] = defaultdict(list)
    for index, row in enumerate(rows):
        raw_components[find(index)].append(str(row["claim_id"]))
    components = {
        _sha256_json(sorted(claim_ids)): sorted(claim_ids)
        for claim_ids in raw_components.values()
    }
    component_by_id = {
        claim_id: component
        for component, claim_ids in components.items()
        for claim_id in claim_ids
    }
    return component_by_id, components


def _dataset_payload(
    rows: list[dict[str, Any]], *, source_file: Path, split: str
) -> dict[str, Any]:
    examples = []
    for row in rows:
        example = _example(row)
        example["split"] = split
        example["source"]["v10_source_partition"] = split
        examples.append(example)
    return {
        "schema_version": "contexttrace-climate-fever-v10-dataset-1.0",
        "experiment": EXPERIMENT,
        "split": split,
        "source": {
            "dataset": "Climate-FEVER",
            "source_file": source_file.name,
            "source_sha256": DATASET_SHA256,
            "license": "not stated on official dataset page",
            "redistribution_policy": "source text remains external",
        },
        "examples": sorted(examples, key=lambda example: example["id"]),
    }


def _load_selection(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise V10BuildError("Consumed V9 selection is missing.")
    value = json.loads(path.read_text(encoding="utf-8"))
    selected = value.get("selected_claim_ids")
    if not isinstance(selected, dict) or set(selected) != set(LABELS):
        raise V10BuildError("Consumed V9 selection has an invalid label mapping.")
    if value.get("selected_claim_ids_sha256") != _sha256_json(selected):
        raise V10BuildError("Consumed V9 selection hash is invalid.")
    return value


def _ids_by_label(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        label: sorted(
            str(row["claim_id"]) for row in rows if row["claim_label"] == label
        )
        for label in LABELS
    }


def _label_counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cases": len(rows),
        "labels": dict(
            sorted(Counter(str(row["claim_label"]) for row in rows).items())
        ),
        "evidence_sentences": sum(len(row["evidences"]) for row in rows),
    }


def _row_evidence_hashes(row: dict[str, Any]) -> set[str]:
    return {
        hashlib.sha256(
            (
                f"{str(item['article']).strip()}: {str(item['evidence']).strip()}"
                if str(item["article"]).strip()
                else str(item["evidence"]).strip()
            ).encode("utf-8")
        ).hexdigest()
        for item in row["evidences"]
    }


def _evidence_hashes(rows: list[dict[str, Any]]) -> set[str]:
    return {value for row in rows for value in _row_evidence_hashes(row)}


def _selection_digest(split: str, label: str, claim_id: str) -> str:
    value = f"contexttrace-climate-fever-v10|{split}|{label}|{claim_id}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
    parser.add_argument("--training-output", required=True)
    parser.add_argument("--development-output", required=True)
    parser.add_argument("--selection-output", required=True)
    parser.add_argument("--audit-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--training-per-label", type=int, default=75)
    parser.add_argument("--development-per-label", type=int, default=15)
    args = parser.parse_args(argv)
    training, development, selection, audit, manifest = build(
        args.source,
        args.consumed_v9_selection,
        training_per_label=args.training_per_label,
        development_per_label=args.development_per_label,
    )
    _write(args.training_output, training)
    _write(args.development_output, development)
    _write(args.selection_output, selection)
    _write(args.audit_output, audit)
    _write(args.manifest_output, manifest)
    print(
        json.dumps(
            {
                "training_cases": len(training["examples"]),
                "development_cases": len(development["examples"]),
                "training_sha256": manifest["training_sha256"],
                "development_sha256": manifest["development_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
