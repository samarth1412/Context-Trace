"""Build a balanced, disjoint V21 development set for local verifier work."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmarks.external_fiveway_confirmation.adapter import _wice_cases
from benchmarks.jev_v2_verification.run import shared_input
from benchmarks.requirement_alignment.build_v19_confirmation import (
    AVERITEC_LABELS,
    WICE_SHA256,
    _normalized_claim,
    _prior_examples,
    _require_hash,
    _write,
)
from benchmarks.requirement_alignment.v14_fiveway_policy import LABELS, _sha256_json


EXPERIMENT = "contexttrace_v21_domain_diverse_development"
SPLIT = "external_fiveway_v21_development"
PER_LABEL = 100
SEED = "contexttrace-v21-development-20260928"
AVERITEC_TRAIN_SHA256 = (
    "ae5eda7c42ddf1695ef185a7ba1bc716928f5adf57103e4f78aae5f9afe00f9c"
)


class V21BuildError(RuntimeError):
    """Raised when the V21 development-data contract is violated."""


def build_development(
    averitec_train_path: str | Path,
    wice_path: str | Path,
    *,
    repository_root: str | Path,
    additional_exclusions: list[str | Path] | None = None,
    per_label: int = PER_LABEL,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if per_label < 1:
        raise V21BuildError("per_label must be positive.")
    averitec = Path(averitec_train_path)
    wice = Path(wice_path)
    _require_hash(averitec, AVERITEC_TRAIN_SHA256)
    _require_hash(wice, WICE_SHA256)
    excluded_ids, excluded_claims, exclusion_sources = _prior_examples(
        Path(repository_root), additional_exclusions or []
    )

    wice_candidates = [
        {**row, "source_id": str(row["id"])}
        for row in _wice_cases(wice)
        if row["expected_verdict"] == "partially_supported"
    ]
    candidates = [*_averitec_train_candidates(averitec), *wice_candidates]
    candidates_before = Counter(row["expected_verdict"] for row in candidates)
    disjoint = [
        row
        for row in candidates
        if str(row["id"]) not in excluded_ids
        and _normalized_claim(row["claim"]) not in excluded_claims
    ]
    candidates_after_overlap = Counter(row["expected_verdict"] for row in disjoint)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in disjoint:
        grouped[str(row["expected_verdict"])].append(row)

    selected_rows = []
    evidence_rejections = Counter()
    for label in LABELS:
        ordered = sorted(
            grouped[label], key=lambda row: _stable_rank(label, str(row["id"]))
        )
        accepted = []
        for row in ordered:
            selected, input_audit = shared_input(row, max_spans=8)
            if not selected:
                evidence_rejections[label] += 1
                continue
            accepted.append((row, selected, input_audit))
            if len(accepted) == per_label:
                break
        if len(accepted) < per_label:
            raise V21BuildError(
                "Only %d disjoint %s cases have selected evidence; %d required."
                % (len(accepted), label, per_label)
            )
        selected_rows.extend(accepted)

    examples = []
    selection_rows = []
    for case, selected, input_audit in selected_rows:
        case_id = str(case["id"])
        examples.append(
            {
                "id": case_id,
                "input": {
                    "query": str(case.get("query") or ""),
                    "claim": str(case["claim"]),
                    "evidence": [
                        {"id": context.id, "text": context.text} for context in selected
                    ],
                },
                "target": {"verdict": str(case["expected_verdict"])},
                "source": {
                    "dataset": str(case["dataset"]),
                    "source_split": str(case["source_split"]),
                    "source_id": str(case["source_id"]),
                    "upstream_label": str(case["upstream_label"]),
                    "selected_span_count": len(selected),
                },
            }
        )
        selection_rows.append(
            {
                "case_id": case_id,
                "claim_sha256": hashlib.sha256(
                    str(case["claim"]).encode("utf-8")
                ).hexdigest(),
                "input_sha256": input_audit["input_sha256"],
                "dataset": str(case["dataset"]),
                "source_id": str(case["source_id"]),
                "expected_verdict": str(case["expected_verdict"]),
                "source_context_count": input_audit["source_context_count"],
                "selected_span_count": input_audit["selected_span_count"],
            }
        )
    examples.sort(key=lambda row: row["id"])
    selection_rows.sort(key=lambda row: row["case_id"])
    dataset = {
        "schema_version": "contexttrace-v21-development-dataset-1.0",
        "experiment": EXPERIMENT,
        "split": SPLIT,
        "source": {
            "datasets": ["AVeriTeC", "WiCE"],
            "selected_evidence_only": True,
            "source_text_committed": False,
        },
        "examples": examples,
    }
    selected_ids = {row["id"] for row in examples}
    selected_claims = {_normalized_claim(row["input"]["claim"]) for row in examples}
    counts = Counter(row["target"]["verdict"] for row in examples)
    checks = {
        "balanced_five_way": counts == Counter({label: per_label for label in LABELS}),
        "case_ids_unique": len(selected_ids) == len(examples),
        "case_ids_disjoint_from_prior_artifacts": not bool(selected_ids & excluded_ids),
        "normalized_claims_disjoint_from_prior_artifacts": not bool(
            selected_claims & excluded_claims
        ),
        "model_inputs_exclude_labels": all(
            not ({"label", "target", "verdict", "dataset"} & set(row["input"]))
            for row in examples
        ),
        "selected_evidence_nonempty": all(row["input"]["evidence"] for row in examples),
        "model_outputs_used_for_selection": False,
        "future_confirmation_data_accessed": False,
    }
    if (
        not all(
            value
            for key, value in checks.items()
            if key
            not in {
                "model_outputs_used_for_selection",
                "future_confirmation_data_accessed",
            }
        )
        or checks["model_outputs_used_for_selection"] is not False
        or checks["future_confirmation_data_accessed"] is not False
    ):
        raise V21BuildError("V21 development audit failed: %r" % checks)
    audit = {
        "schema_version": "contexttrace-v21-development-audit-1.0",
        "experiment": EXPERIMENT,
        "valid": True,
        "sources": {
            "averitec": {
                "split": "train",
                "revision": "122e10f4e02168d18eb9e8cdb5abe44f530ce6a7",
                "sha256": AVERITEC_TRAIN_SHA256,
                "license": "CC BY-NC 4.0",
            },
            "wice": {
                "split": "test",
                "revision": "ddeb6c183665e2a20c5f03c5aa07f03888b9870f",
                "sha256": WICE_SHA256,
                "license": "ODC-BY annotations; upstream source-text terms apply",
            },
        },
        "label_mapping": {
            "AVeriTeC.Supported": "supported",
            "WiCE.partially_supported": "partially_supported",
            "AVeriTeC.Refuted": "contradicted",
            "AVeriTeC.Not Enough Evidence": "unsupported",
            "AVeriTeC.Conflicting Evidence/Cherrypicking": "unverifiable",
        },
        "selection": {
            "method": "stable_sha256_stratified_disjoint_without_replacement",
            "seed": SEED,
            "per_label": per_label,
            "maximum_selected_spans": 8,
            "model_outputs_used": False,
            "prior_artifact_sources": exclusion_sources,
            "prior_case_ids": len(excluded_ids),
            "prior_normalized_claims": len(excluded_claims),
            "candidates_before_exclusion": dict(sorted(candidates_before.items())),
            "candidates_after_overlap_exclusion": dict(
                sorted(candidates_after_overlap.items())
            ),
            "evidence_rejections_before_quota": dict(
                sorted(evidence_rejections.items())
            ),
            "rows": selection_rows,
        },
        "counts": {
            "cases": len(examples),
            "labels": dict(sorted(counts.items())),
            "datasets": dict(
                sorted(Counter(row["source"]["dataset"] for row in examples).items())
            ),
            "selected_evidence_spans": sum(
                len(row["input"]["evidence"]) for row in examples
            ),
        },
        "checks": checks,
        "limitations": [
            "This is development data and cannot support a confirmation or state-of-the-art claim.",
            "AVeriTeC and WiCE labels are aligned rather than newly annotated for ContextTrace.",
            "The partial-support class comes only from WiCE, creating source-label correlation.",
            "Public-data pretraining contamination cannot be ruled out.",
            "The benchmark jointly measures label-blind evidence selection and verification.",
        ],
    }
    manifest = {
        "schema_version": "contexttrace-v21-development-manifest-1.0",
        "experiment": EXPERIMENT,
        "status": "development_only_not_confirmation",
        "dataset_sha256": _sha256_json(dataset),
        "audit_sha256": _sha256_json(audit),
        "labels_may_be_used_for_training": True,
        "future_confirmation_data_accessed": False,
        "future_confirmation_retraining_allowed": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
    }
    return dataset, audit, manifest


def _averitec_train_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise V21BuildError("AVeriTeC training source is empty or invalid.")
    output = []
    for index, row in enumerate(payload):
        upstream = str(row.get("label") or "")
        if upstream not in AVERITEC_LABELS:
            raise V21BuildError("Unknown AVeriTeC label: %s" % upstream)
        claim = " ".join(str(row.get("claim") or "").split()).strip()
        contexts = []
        for question_index, question_row in enumerate(row.get("questions") or []):
            question = " ".join(str(question_row.get("question") or "").split())
            for answer_index, answer_row in enumerate(
                question_row.get("answers") or []
            ):
                answer = " ".join(str(answer_row.get("answer") or "").split())
                explanation = " ".join(
                    str(answer_row.get("boolean_explanation") or "").split()
                )
                parts = []
                if question:
                    parts.append("Question: %s" % question)
                if answer:
                    parts.append("Answer: %s" % answer)
                if explanation:
                    parts.append("Explanation: %s" % explanation)
                if parts:
                    contexts.append(
                        {
                            "id": "averitec_train_%04d_q%03d_a%03d"
                            % (index, question_index, answer_index),
                            "text": "\n".join(parts),
                        }
                    )
        if claim and contexts:
            output.append(
                {
                    "id": "averitec_train_%04d" % index,
                    "dataset": "AVeriTeC",
                    "source_split": "train",
                    "source_id": str(index),
                    "query": "",
                    "claim": claim,
                    "contexts": contexts,
                    "expected_verdict": AVERITEC_LABELS[upstream],
                    "upstream_label": upstream,
                }
            )
    return output


def _stable_rank(label: str, case_id: str) -> str:
    return hashlib.sha256(f"{SEED}|{label}|{case_id}".encode()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--averitec-train", required=True)
    parser.add_argument("--wice", required=True)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--exclude-dataset", action="append", default=[])
    parser.add_argument("--per-label", type=int, default=PER_LABEL)
    parser.add_argument("--dataset-output", required=True)
    parser.add_argument("--audit-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    args = parser.parse_args(argv)
    values = build_development(
        args.averitec_train,
        args.wice,
        repository_root=args.repository_root,
        additional_exclusions=args.exclude_dataset,
        per_label=args.per_label,
    )
    for path, value in zip(
        (args.dataset_output, args.audit_output, args.manifest_output),
        values,
        strict=True,
    ):
        _write(path, value)
    print(
        json.dumps(
            {
                "status": values[2]["status"],
                "dataset_sha256": values[2]["dataset_sha256"],
                "counts": values[1]["counts"],
                "checks": values[1]["checks"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
