"""Build disjoint calibration and evaluation cases for the v6 verifier cascade."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.build_development import RELATION_TARGET
from benchmarks.requirement_alignment.build_development import _annotations
from benchmarks.requirement_alignment.build_development import _example
from benchmarks.requirement_alignment.build_development import _round_robin_sample
from benchmarks.requirement_alignment.build_development import _selected_evidence
from benchmarks.requirement_alignment.build_v3_training import SOURCE_MEMBER
from benchmarks.requirement_alignment.build_v3_training import SOURCE_MEMBER_SHA256
from benchmarks.requirement_alignment.build_v3_training import SOURCE_ZIP_SHA256


SEED = 20261002
CASES_PER_RELATION_PER_SPLIT = 30
SPLITS = ("cascade_calibration", "cascade_evaluation")


class V6CaseBuildError(RuntimeError):
    """Raised when v6 case isolation or provenance checks fail."""


def build_v6_cases(
    contract_payload: dict[str, Any],
    training_payload: dict[str, Any],
    *,
    cases_per_relation_per_split: int = CASES_PER_RELATION_PER_SPLIT,
    seed: int = SEED,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if cases_per_relation_per_split < 1:
        raise V6CaseBuildError("cases_per_relation_per_split must be positive.")
    labels = contract_payload.get("labels") or {}
    documents = contract_payload.get("documents") or []
    training_rows = list(training_payload.get("examples") or [])
    training_ids = {
        str(row["id"])
        for row in training_rows
        if row.get("source", {}).get("dataset") == "ContractNLI"
    }
    training_document_ids = {
        str(row["source"]["document_id"])
        for row in training_rows
        if row.get("source", {}).get("dataset") == "ContractNLI"
    }
    if not labels or not documents or not training_ids:
        raise V6CaseBuildError("ContractNLI source or v3 training exclusions are empty.")

    unseen: dict[str, list[dict[str, Any]]] = defaultdict(list)
    candidate_counts = Counter()
    exclusions = Counter()
    for document in documents:
        for hypothesis_id, annotation in sorted(_annotations(document).items()):
            relation = str(annotation.get("choice") or "")
            if relation not in RELATION_TARGET or hypothesis_id not in labels:
                exclusions["unknown_relation_or_hypothesis"] += 1
                continue
            candidate_counts[relation] += 1
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
            if row["id"] in training_ids:
                exclusions["used_by_v3_v5_training"] += 1
                continue
            unseen[relation].append(row)

    selected_by_split: dict[str, list[dict[str, Any]]] = {name: [] for name in SPLITS}
    required = cases_per_relation_per_split * len(SPLITS)
    for relation in RELATION_TARGET:
        available = list(unseen.get(relation) or [])
        if len(available) < required:
            raise V6CaseBuildError(
                "%s has only %d unseen cases; %d required."
                % (relation, len(available), required)
            )
        calibration = _round_robin_sample(
            available,
            size=cases_per_relation_per_split,
            seed=seed,
            relation="%s:calibration" % relation,
        )
        calibration_ids = {str(row["id"]) for row in calibration}
        evaluation = _round_robin_sample(
            [row for row in available if str(row["id"]) not in calibration_ids],
            size=cases_per_relation_per_split,
            seed=seed + 1,
            relation="%s:evaluation" % relation,
        )
        selected_by_split["cascade_calibration"].extend(calibration)
        selected_by_split["cascade_evaluation"].extend(evaluation)

    datasets: dict[str, dict[str, Any]] = {}
    for split_name, rows in selected_by_split.items():
        examples = []
        for original in sorted(rows, key=lambda row: str(row["id"])):
            row = dict(original)
            row["split"] = split_name
            row["source"] = {**row["source"], "v6_partition": split_name}
            examples.append(row)
        datasets[split_name] = {
            "schema_version": "contexttrace-requirement-v6-cascade-cases-1.0",
            "dataset": "ContractNLI unseen-pair v6 cascade cases",
            "source": {
                "dataset": "ContractNLI",
                "split": "train",
                "archive_sha256": SOURCE_ZIP_SHA256,
                "member": SOURCE_MEMBER,
                "member_sha256": SOURCE_MEMBER_SHA256,
            },
            "construction": {
                "seed": seed,
                "partition": split_name,
                "cases_per_relation": cases_per_relation_per_split,
                "excluded_v3_v5_training_example_ids": True,
                "claim_evidence_pairs_seen_in_training": False,
                "source_document_overlap_with_training_possible": True,
                "contractnli_dev_or_test_used": False,
                "model_or_api_labels_used": False,
            },
            "examples": examples,
        }

    calibration_ids = {row["id"] for row in datasets[SPLITS[0]]["examples"]}
    evaluation_ids = {row["id"] for row in datasets[SPLITS[1]]["examples"]}
    all_rows = [row for value in datasets.values() for row in value["examples"]]
    relation_counts = {
        split_name: dict(
            sorted(Counter(row["source"]["relation"] for row in rows).items())
        )
        for split_name, rows in (
            (name, datasets[name]["examples"]) for name in SPLITS
        )
    }
    input_has_target = any(
        any(key in row["input"] for key in ("label", "target", "relation"))
        for row in all_rows
    )
    if (
        calibration_ids & evaluation_ids
        or (calibration_ids | evaluation_ids) & training_ids
        or input_has_target
        or any(
            set(counts) != set(RELATION_TARGET)
            or len(set(counts.values())) != 1
            for counts in relation_counts.values()
        )
    ):
        raise V6CaseBuildError("V6 cascade cases failed isolation or balance checks.")
    selected_documents = {str(row["source"]["document_id"]) for row in all_rows}
    audit = {
        "schema_version": "contexttrace-requirement-v6-cascade-audit-1.0",
        "valid": True,
        "examples": len(all_rows),
        "examples_per_split": {
            name: len(datasets[name]["examples"]) for name in SPLITS
        },
        "relation_counts": relation_counts,
        "eligible_unseen_counts": {
            key: len(value) for key, value in sorted(unseen.items())
        },
        "source_candidate_counts": dict(sorted(candidate_counts.items())),
        "exclusions": dict(sorted(exclusions.items())),
        "selected_documents": len(selected_documents),
        "selected_documents_overlapping_training": len(
            selected_documents & training_document_ids
        ),
        "integrity": {
            "calibration_evaluation_ids_disjoint": True,
            "v3_v5_training_example_ids_excluded": True,
            "targets_absent_from_model_inputs": True,
            "contractnli_development_or_test_used": False,
            "model_or_api_labels_used": False,
        },
        "limitations": [
            "Cases are unused ContractNLI train claim-evidence pairs, not an official held-out split.",
            "Source documents can overlap documents seen during v3/v5 training.",
            "The 17 legal hypotheses recur across training, calibration, and evaluation.",
            "NotMentioned evidence uses deterministic lexical selection.",
        ],
    }
    return datasets, audit


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract-source-zip", required=True)
    parser.add_argument("--v3-training-dataset", required=True)
    parser.add_argument("--calibration-output", required=True)
    parser.add_argument("--evaluation-output", required=True)
    parser.add_argument("--audit-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument(
        "--cases-per-relation-per-split",
        type=int,
        default=CASES_PER_RELATION_PER_SPLIT,
    )
    args = parser.parse_args(argv)
    archive_path = Path(args.contract_source_zip)
    if _sha256(archive_path) != SOURCE_ZIP_SHA256:
        raise V6CaseBuildError("ContractNLI archive does not match its pin.")
    with zipfile.ZipFile(archive_path) as archive:
        raw = archive.read(SOURCE_MEMBER)
    if hashlib.sha256(raw).hexdigest() != SOURCE_MEMBER_SHA256:
        raise V6CaseBuildError("ContractNLI training member does not match its pin.")
    training_path = Path(args.v3_training_dataset)
    datasets, audit = build_v6_cases(
        json.loads(raw),
        json.loads(training_path.read_text(encoding="utf-8")),
        cases_per_relation_per_split=args.cases_per_relation_per_split,
    )
    calibration_path = Path(args.calibration_output)
    evaluation_path = Path(args.evaluation_output)
    audit_path = Path(args.audit_output)
    _write(calibration_path, datasets["cascade_calibration"])
    _write(evaluation_path, datasets["cascade_evaluation"])
    _write(audit_path, audit)
    manifest = {
        "schema_version": "contexttrace-requirement-v6-cascade-manifest-1.0",
        "source_archive_sha256": SOURCE_ZIP_SHA256,
        "source_member": SOURCE_MEMBER,
        "source_member_sha256": SOURCE_MEMBER_SHA256,
        "v3_training_dataset_sha256": _sha256(training_path),
        "calibration_dataset_sha256": _sha256(calibration_path),
        "evaluation_dataset_sha256": _sha256(evaluation_path),
        "audit_sha256": _sha256(audit_path),
        "calibration_examples": audit["examples_per_split"]["cascade_calibration"],
        "evaluation_examples": audit["examples_per_split"]["cascade_evaluation"],
        "contractnli_development_or_test_used": False,
    }
    _write(Path(args.manifest_output), manifest)
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
