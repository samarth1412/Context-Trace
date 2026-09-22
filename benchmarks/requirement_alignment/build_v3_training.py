"""Build the fixed mixed-relation training artifact for v3."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.build_development import RELATION_TARGET
from benchmarks.requirement_alignment.build_development import _annotations
from benchmarks.requirement_alignment.build_development import _example
from benchmarks.requirement_alignment.build_development import _round_robin_sample
from benchmarks.requirement_alignment.build_development import _selected_evidence


SOURCE_ZIP_SHA256 = "e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b"
SOURCE_MEMBER = "contract-nli/train.json"
SOURCE_MEMBER_SHA256 = "dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5"
WICE_DATASET_SHA256 = "7d02d8792eda61b319638acdb05ad7c989df464e0a48027f6415ad1874db7038"
SEED = 20260929
CASES_PER_RELATION = 700
RELATION_LABEL = {
    "Entailment": "entailment",
    "Contradiction": "contradiction",
    "NotMentioned": "neutral",
}


class V3TrainingDataError(RuntimeError):
    """Raised when v3 training-data construction violates its contract."""


def build_v3_training_data(
    contract_payload: dict[str, Any],
    wice_payload: dict[str, Any],
    *,
    cases_per_relation: int = CASES_PER_RELATION,
    seed: int = SEED,
) -> tuple[dict[str, Any], dict[str, Any]]:
    labels = contract_payload.get("labels") or {}
    documents = contract_payload.get("documents") or []
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exclusions = Counter()
    for document in documents:
        for hypothesis_id, annotation in sorted(_annotations(document).items()):
            relation = str(annotation.get("choice") or "")
            if relation not in RELATION_TARGET or hypothesis_id not in labels:
                exclusions["unknown_relation_or_hypothesis"] += 1
                continue
            hypothesis = " ".join(
                str(labels[hypothesis_id].get("hypothesis") or "").split()
            )
            evidence, indexes, selection = _selected_evidence(
                document,
                hypothesis=hypothesis,
                relation=relation,
                annotated_indexes=annotation.get("spans") or [],
                source_split="train",
            )
            if not evidence:
                exclusions["no_evidence_within_budget"] += 1
                continue
            row = _example(
                document=document,
                hypothesis_id=hypothesis_id,
                hypothesis=hypothesis,
                description=str(labels[hypothesis_id].get("short_description") or ""),
                relation=relation,
                evidence=evidence,
                evidence_indexes=indexes,
                evidence_selection=selection,
                source_split="train",
            )
            row["split"] = "training"
            row["target"] = {"label": RELATION_LABEL[relation]}
            candidates[relation].append(row)

    contract_rows = []
    for relation in RELATION_TARGET:
        available = candidates.get(relation) or []
        if len(available) < cases_per_relation:
            raise V3TrainingDataError(
                "%s has only %d eligible cases; %d required."
                % (relation, len(available), cases_per_relation)
            )
        contract_rows.extend(
            _round_robin_sample(
                available,
                size=cases_per_relation,
                seed=seed,
                relation=relation,
            )
        )

    wice_rows = []
    for original in wice_payload.get("examples") or []:
        if original.get("split") != "training":
            continue
        row = deepcopy(original)
        original_label = str(row["target"]["label"])
        row["target"] = {
            "label": (
                "entailment"
                if original_label in {"complete", "covered"}
                else "neutral"
            )
        }
        row["source"]["v3_original_target"] = original_label
        row["source"]["v3_relation_mapping"] = (
            "positive_to_entailment"
            if row["target"]["label"] == "entailment"
            else "incomplete_to_neutral"
        )
        wice_rows.append(row)

    examples = sorted(contract_rows + wice_rows, key=lambda row: str(row["id"]))
    dataset = {
        "schema_version": "contexttrace-requirement-v3-training-1.0",
        "dataset": "Mixed WiCE and ContractNLI relation training",
        "sources": {
            "contractnli": {
                "split": "train",
                "archive_sha256": SOURCE_ZIP_SHA256,
                "member": SOURCE_MEMBER,
                "member_sha256": SOURCE_MEMBER_SHA256,
            },
            "wice": {
                "split": "train-derived training partition",
                "dataset_sha256": WICE_DATASET_SHA256,
            },
        },
        "construction": {
            "seed": seed,
            "contract_cases_per_relation": cases_per_relation,
            "contract_relation_mapping": RELATION_LABEL,
            "wice_positive_mapping": "entailment",
            "wice_incomplete_mapping": "neutral",
            "contractnli_dev_or_test_used": False,
            "model_or_api_labels_used": False,
        },
        "examples": examples,
    }
    audit = audit_v3_training_data(
        dataset,
        contract_candidate_counts={key: len(value) for key, value in candidates.items()},
        contract_exclusions=dict(sorted(exclusions.items())),
    )
    return dataset, audit


def audit_v3_training_data(
    dataset: dict[str, Any],
    *,
    contract_candidate_counts: dict[str, int],
    contract_exclusions: dict[str, int],
) -> dict[str, Any]:
    rows = list(dataset.get("examples") or [])
    ids = [str(row["id"]) for row in rows]
    relation_counts = Counter(str(row["target"]["label"]) for row in rows)
    source_counts = Counter(str(row["source"]["dataset"]) for row in rows)
    input_has_target = any(
        any(key in row["input"] for key in ("label", "target", "relation"))
        for row in rows
    )
    contract_splits = {
        str(row["source"]["source_split"])
        for row in rows
        if row["source"]["dataset"] == "ContractNLI"
    }
    valid = bool(
        rows
        and len(ids) == len(set(ids))
        and set(relation_counts) == {"contradiction", "entailment", "neutral"}
        and contract_splits == {"train"}
        and not input_has_target
    )
    if not valid:
        raise V3TrainingDataError("V3 training data failed its audit.")
    return {
        "schema_version": "contexttrace-requirement-v3-training-audit-1.0",
        "valid": True,
        "examples": len(rows),
        "source_counts": dict(sorted(source_counts.items())),
        "relation_counts": dict(sorted(relation_counts.items())),
        "contract_candidate_counts": dict(sorted(contract_candidate_counts.items())),
        "contract_exclusions": contract_exclusions,
        "contract_documents": len(
            {
                str(row["source"]["document_id"])
                for row in rows
                if row["source"]["dataset"] == "ContractNLI"
            }
        ),
        "integrity": {
            "unique_example_ids": True,
            "contract_training_split_only": True,
            "contract_development_or_test_used": False,
            "targets_absent_from_model_inputs": True,
            "model_or_api_labels_used": False,
        },
        "limitations": [
            "WiCE incomplete examples map to neutral and do not add contradiction supervision.",
            "ContractNLI contains 17 recurring legal hypotheses.",
            "NotMentioned examples use deterministic lexical evidence selection.",
        ],
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract-source-zip", required=True)
    parser.add_argument("--wice-dataset", required=True)
    parser.add_argument("--dataset-output", required=True)
    parser.add_argument("--audit-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--cases-per-relation", type=int, default=CASES_PER_RELATION)
    args = parser.parse_args(argv)

    source = Path(args.contract_source_zip)
    if hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_ZIP_SHA256:
        raise V3TrainingDataError("ContractNLI archive does not match its pin.")
    with zipfile.ZipFile(source) as archive:
        raw = archive.read(SOURCE_MEMBER)
    if hashlib.sha256(raw).hexdigest() != SOURCE_MEMBER_SHA256:
        raise V3TrainingDataError("ContractNLI training member does not match its pin.")
    wice_path = Path(args.wice_dataset)
    if hashlib.sha256(wice_path.read_bytes()).hexdigest() != WICE_DATASET_SHA256:
        raise V3TrainingDataError("WiCE training dataset does not match its pin.")
    dataset, audit = build_v3_training_data(
        json.loads(raw),
        json.loads(wice_path.read_text(encoding="utf-8")),
        cases_per_relation=args.cases_per_relation,
    )
    dataset_path = Path(args.dataset_output)
    audit_path = Path(args.audit_output)
    _write(dataset_path, dataset)
    _write(audit_path, audit)
    manifest = {
        "schema_version": "contexttrace-requirement-v3-training-manifest-1.0",
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
        "audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        "contract_source_member_sha256": SOURCE_MEMBER_SHA256,
        "wice_source_dataset_sha256": WICE_DATASET_SHA256,
        "examples": audit["examples"],
        "contract_development_or_test_used": False,
    }
    _write(Path(args.manifest_output), manifest)
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
