"""Freeze a license-safe Climate-FEVER holdout before any model scoring."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


DATASET_URL = (
    "https://www.sustainablefinance.uzh.ch/dam/"
    "jcr%3Adf02e448-baa1-4db8-921a-58507be4838e/"
    "climate-fever-dataset-r1.jsonl"
)
DATASET_SHA256 = "8a4b9032d861be482ffb49dddfd283ffa6089e654f1e968040011882c5eb6e0b"
LABELS = ("SUPPORTS", "REFUTES", "NOT_ENOUGH_INFO", "DISPUTED")
LABEL_SPEC = {
    "SUPPORTS": {"relation": "Entailment", "target": "covered"},
    "REFUTES": {"relation": "Contradiction", "target": "missing"},
    "NOT_ENOUGH_INFO": {"relation": "NotMentioned", "target": "missing"},
    "DISPUTED": {"relation": "Disputed", "target": "review"},
}
EXPERIMENT = "contexttrace_v9_climate_fever_holdout"
SPLIT = "climate_fever_evaluation"


class V9BuildError(RuntimeError):
    """Raised when the Climate-FEVER source or freeze contract is invalid."""


def build(
    source_path: str | Path,
    *,
    per_label: int = 60,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    source_file = Path(source_path)
    if not source_file.is_file():
        raise V9BuildError("Climate-FEVER source JSONL is missing.")
    if _sha256_file(source_file) != DATASET_SHA256:
        raise V9BuildError("Climate-FEVER source does not match the frozen SHA-256.")
    if per_label < 1:
        raise V9BuildError("per_label must be positive.")
    rows = _read_jsonl(source_file)
    _validate_source(rows)

    candidates: dict[str, list[dict[str, Any]]] = {label: [] for label in LABELS}
    for row in rows:
        label = str(row["claim_label"])
        candidates[label].append(row)

    selected_source: list[dict[str, Any]] = []
    selected_ids: dict[str, list[str]] = {}
    for label in LABELS:
        ordered = sorted(
            candidates[label],
            key=lambda row: _selection_digest(label, str(row["claim_id"])),
        )
        if len(ordered) < per_label:
            raise V9BuildError(
                "%s has %d candidates; %d required." % (label, len(ordered), per_label)
            )
        selected = ordered[:per_label]
        selected_source.extend(selected)
        selected_ids[label] = sorted(str(row["claim_id"]) for row in selected)

    examples = sorted(
        (_example(row) for row in selected_source), key=lambda row: row["id"]
    )
    evaluation = {
        "schema_version": "contexttrace-climate-fever-v9-dataset-1.0",
        "experiment": EXPERIMENT,
        "split": SPLIT,
        "source": _source_record(source_file),
        "examples": examples,
    }
    selection = {
        "schema_version": "contexttrace-climate-fever-v9-selection-1.0",
        "experiment": EXPERIMENT,
        "split": SPLIT,
        "algorithm": "sha256_order_v1",
        "seed_material": "contexttrace-climate-fever-v9|claim_label|claim_id",
        "per_label": per_label,
        "selected_claim_ids": selected_ids,
        "selected_claim_ids_sha256": _sha256_json(selected_ids),
        "model_outputs_used": False,
        "source_text_included": False,
    }
    audit = _audit(rows, examples, selection, source_file)
    manifest = {
        "schema_version": "contexttrace-climate-fever-v9-manifest-1.0",
        "experiment": EXPERIMENT,
        "status": "frozen_before_model_scoring",
        "source_sha256": DATASET_SHA256,
        "evaluation_sha256": _sha256_json(evaluation),
        "selection_sha256": _sha256_json(selection),
        "audit_sha256": _sha256_json(audit),
        "frozen_policy": (
            "benchmarks/requirement_alignment/results/v8_scifact_guard_policy.json"
        ),
        "evaluation_used_for_policy_selection": False,
        "model_outputs_accessed": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
    }
    return evaluation, selection, audit, manifest


def _validate_source(rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise V9BuildError("Climate-FEVER source is empty.")
    claim_ids = [str(row.get("claim_id", "")) for row in rows]
    if any(not value for value in claim_ids) or len(set(claim_ids)) != len(claim_ids):
        raise V9BuildError("Climate-FEVER claim IDs must be non-empty and unique.")
    for row in rows:
        label = str(row.get("claim_label", ""))
        if label not in LABELS:
            raise V9BuildError("Unknown Climate-FEVER claim label: %r." % label)
        if not str(row.get("claim", "")).strip():
            raise V9BuildError("Climate-FEVER claim text must be non-empty.")
        evidence = list(row.get("evidences") or [])
        if len(evidence) != 5:
            raise V9BuildError("Each Climate-FEVER claim must have five evidences.")
        evidence_ids = [str(item.get("evidence_id", "")) for item in evidence]
        if any(not value for value in evidence_ids) or len(set(evidence_ids)) != 5:
            raise V9BuildError("Evidence IDs must be non-empty and unique per claim.")
        micro_labels = [str(item.get("evidence_label", "")) for item in evidence]
        if any(value not in LABELS[:3] for value in micro_labels):
            raise V9BuildError("Unknown Climate-FEVER evidence label.")
        if any(not str(item.get("evidence", "")).strip() for item in evidence):
            raise V9BuildError("Climate-FEVER evidence text must be non-empty.")
        _validate_macro_label(label, micro_labels)


def _validate_macro_label(label: str, micro_labels: list[str]) -> None:
    has_support = "SUPPORTS" in micro_labels
    has_refute = "REFUTES" in micro_labels
    expected = (
        "DISPUTED"
        if has_support and has_refute
        else "SUPPORTS"
        if has_support
        else "REFUTES"
        if has_refute
        else "NOT_ENOUGH_INFO"
    )
    if label != expected:
        raise V9BuildError(
            "Claim label %s is inconsistent with evidence labels (%s)."
            % (label, expected)
        )


def _example(row: dict[str, Any]) -> dict[str, Any]:
    claim_id = str(row["claim_id"])
    label = str(row["claim_label"])
    spec = LABEL_SPEC[label]
    claim = str(row["claim"])
    evidence = []
    evidence_audit = []
    for index, item in enumerate(row["evidences"]):
        article = str(item["article"]).strip()
        sentence = str(item["evidence"]).strip()
        text = "%s: %s" % (article, sentence) if article else sentence
        evidence.append(
            {
                "id": "climate_fever_%s_e%02d" % (claim_id, index),
                "text": text,
            }
        )
        evidence_audit.append(
            {
                "upstream_evidence_id": str(item["evidence_id"]),
                "evidence_label": str(item["evidence_label"]),
                "entropy": float(item["entropy"]),
                "votes": list(item["votes"]),
                "rendered_text_sha256": hashlib.sha256(
                    text.encode("utf-8")
                ).hexdigest(),
            }
        )
    return {
        "id": "climate_fever_%s_%s" % (claim_id, label.lower()),
        "task": "cross_domain_claim_verification",
        "split": SPLIT,
        "input": {
            "claim": claim,
            "requirement": {
                "id": "r00",
                "text": claim,
                "start_char": 0,
                "end_char": len(claim),
            },
            "evidence": evidence,
        },
        "target": {"label": str(spec["target"])},
        "source": {
            "dataset": "Climate-FEVER",
            "claim_id": claim_id,
            "claim_label": label,
            "relation": str(spec["relation"]),
            "evidence_selection": "all_five_upstream_retrieved_and_annotated_sentences",
            "evidence_audit": evidence_audit,
        },
    }


def _audit(
    source_rows: list[dict[str, Any]],
    examples: list[dict[str, Any]],
    selection: dict[str, Any],
    source_file: Path,
) -> dict[str, Any]:
    source_labels = Counter(str(row["claim_label"]) for row in source_rows)
    selected_labels = Counter(str(row["source"]["claim_label"]) for row in examples)
    relations = Counter(str(row["source"]["relation"]) for row in examples)
    targets = Counter(str(row["target"]["label"]) for row in examples)
    evidence_labels = Counter(
        str(item["evidence_label"])
        for row in examples
        for item in row["source"]["evidence_audit"]
    )
    return {
        "schema_version": "contexttrace-climate-fever-v9-audit-1.0",
        "experiment": EXPERIMENT,
        "source": _source_record(source_file),
        "source_counts": {
            "claims": len(source_rows),
            "claim_labels": dict(sorted(source_labels.items())),
            "evidence_sentences": sum(len(row["evidences"]) for row in source_rows),
        },
        "evaluation": {
            "cases": len(examples),
            "claim_labels": dict(sorted(selected_labels.items())),
            "relations": dict(sorted(relations.items())),
            "targets": dict(sorted(targets.items())),
            "evidence_labels": dict(sorted(evidence_labels.items())),
            "evidence_sentences": sum(
                len(row["input"]["evidence"]) for row in examples
            ),
        },
        "selection": selection,
        "checks": {
            "source_hash_verified": True,
            "claim_ids_unique": len(examples)
            == len({row["source"]["claim_id"] for row in examples}),
            "balanced_by_claim_label": len(set(selected_labels.values())) == 1,
            "five_evidence_sentences_per_case": all(
                len(row["input"]["evidence"]) == 5 for row in examples
            ),
            "labels_absent_from_inputs": all(
                not ({"label", "target", "relation"} & set(row["input"]))
                for row in examples
            ),
            "synthetic_claims_used": False,
            "synthetic_evidence_used": False,
            "model_outputs_used_for_selection": False,
            "v8_policy_frozen_before_evaluation": True,
        },
        "redistribution": {
            "official_page_calls_dataset_publicly_available": True,
            "explicit_license_on_official_page_found": False,
            "source_text_committed": False,
            "committed_selection_contains_only_ids_and_aggregates": True,
        },
        "limitations": [
            "Climate-FEVER provides a single public collection rather than official train and test splits.",
            "Foundation-model pretraining contamination cannot be ruled out.",
            "Evidence candidates come from Wikipedia and were retrieved upstream, so this evaluates verification over supplied evidence rather than retrieval.",
            "Disputed cases are a review/abstention challenge and are excluded from binary support metrics.",
            "The official dataset page does not state an explicit redistribution license, so source claim and evidence text are not committed.",
        ],
    }


def _source_record(source_file: Path) -> dict[str, Any]:
    return {
        "dataset": "Climate-FEVER",
        "official_page": (
            "https://www.sustainablefinance.uzh.ch/en/research/climate-fever.html"
        ),
        "paper": "https://arxiv.org/abs/2012.00614",
        "download_url": DATASET_URL,
        "source_file": source_file.name,
        "source_sha256": DATASET_SHA256,
        "license": "not stated on official dataset page",
        "redistribution_policy": "source text remains external",
    }


def _selection_digest(label: str, claim_id: str) -> str:
    value = "contexttrace-climate-fever-v9|%s|%s" % (label, claim_id)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise V9BuildError("Line %d must contain a JSON object." % line_number)
        rows.append(value)
    return rows


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--evaluation-output", required=True)
    parser.add_argument("--selection-output", required=True)
    parser.add_argument("--audit-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--per-label", type=int, default=60)
    args = parser.parse_args(argv)
    evaluation, selection, audit, manifest = build(
        args.source, per_label=args.per_label
    )
    _write(Path(args.evaluation_output), evaluation)
    _write(Path(args.selection_output), selection)
    _write(Path(args.audit_output), audit)
    _write(Path(args.manifest_output), manifest)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "evaluation_cases": audit["evaluation"]["cases"],
                "claim_labels": audit["evaluation"]["claim_labels"],
                "evaluation_sha256": manifest["evaluation_sha256"],
                "source_text_committed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
