"""Build a disjoint five-way V19 confirmation set before model scoring."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmarks.external_fiveway_confirmation.adapter import _wice_cases
from benchmarks.jev_v2_verification.run import shared_input
from benchmarks.requirement_alignment.v14_fiveway_policy import LABELS, _sha256_json


EXPERIMENT = "contexttrace_v19_untouched_confirmation"
SPLIT = "external_fiveway_v19_confirmation"
PER_LABEL = 25
SEED = "contexttrace-v19-confirmation-20260927"
AVERITEC_SHA256 = "499793726b4a5406780928a3d9dedc48d6dd53de778f22437d129cacdb08e300"
WICE_SHA256 = "4c91b9e9590cfcd8f8a0f7288b5ff315af8ade946d7bf26f50fbd671bb86dbe8"
V18_ARTIFACT_SHA256 = "bcc5f0d2e66edbb5a400c5c54bb59a31a39ac1a6ce02ff38602b5f0af6288009"
AVERITEC_LABELS = {
    "Supported": "supported",
    "Refuted": "contradicted",
    "Not Enough Evidence": "unsupported",
    "Conflicting Evidence/Cherrypicking": "unverifiable",
}


class V19BuildError(RuntimeError):
    """Raised when the V19 confirmation freeze contract is violated."""


def build_confirmation(
    averitec_path: str | Path,
    wice_path: str | Path,
    *,
    repository_root: str | Path,
    additional_exclusions: list[str | Path] | None = None,
    per_label: int = PER_LABEL,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if per_label < 1:
        raise V19BuildError("per_label must be positive.")
    averitec = Path(averitec_path)
    wice = Path(wice_path)
    _require_hash(averitec, AVERITEC_SHA256)
    _require_hash(wice, WICE_SHA256)
    excluded_ids, excluded_claims, exclusion_sources = _prior_examples(
        Path(repository_root), additional_exclusions or []
    )
    wice_candidates = []
    for row in _wice_cases(wice):
        if row["expected_verdict"] == "partially_supported":
            wice_candidates.append({**row, "source_id": str(row["id"])})
    candidates = [*_averitec_candidates(averitec), *wice_candidates]
    candidates_before = Counter(row["expected_verdict"] for row in candidates)
    disjoint = [
        row
        for row in candidates
        if str(row["id"]) not in excluded_ids
        and _normalized_claim(row["claim"]) not in excluded_claims
    ]
    candidates_after_overlap = Counter(row["expected_verdict"] for row in disjoint)
    selected_input_rows = []
    for row in disjoint:
        selected, input_audit = shared_input(row, max_spans=8)
        if not selected:
            continue
        selected_input_rows.append((row, selected, input_audit))
    candidates_after_evidence = Counter(
        row["expected_verdict"] for row, _, _ in selected_input_rows
    )
    grouped: dict[str, list[tuple[dict[str, Any], Any, dict[str, Any]]]] = defaultdict(
        list
    )
    for values in selected_input_rows:
        grouped[str(values[0]["expected_verdict"])].append(values)
    selected_rows = []
    for label in LABELS:
        ordered = sorted(
            grouped[label],
            key=lambda values: _stable_rank(label, str(values[0]["id"])),
        )
        if len(ordered) < per_label:
            raise V19BuildError(
                "Only %d disjoint %s cases have selected evidence; %d required."
                % (len(ordered), label, per_label)
            )
        selected_rows.extend(ordered[:per_label])

    examples = []
    selection_rows = []
    for case, selected, input_audit in selected_rows:
        case_id = str(case["id"])
        model_input = {
            "query": str(case.get("query") or ""),
            "claim": str(case["claim"]),
            "evidence": [
                {"id": context.id, "text": context.text} for context in selected
            ],
        }
        examples.append(
            {
                "id": case_id,
                "input": model_input,
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
        "schema_version": "contexttrace-v19-confirmation-dataset-1.0",
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
        "predictions_used_for_selection": False,
        "v18_artifact_frozen_before_source_access": True,
    }
    if (
        not all(
            value
            for key, value in checks.items()
            if key != "predictions_used_for_selection"
        )
        or checks["predictions_used_for_selection"] is not False
    ):
        raise V19BuildError("V19 confirmation audit failed: %r" % checks)
    audit = {
        "schema_version": "contexttrace-v19-confirmation-audit-1.0",
        "experiment": EXPERIMENT,
        "valid": True,
        "sources": {
            "averitec": {
                "split": "dev",
                "revision": "122e10f4e02168d18eb9e8cdb5abe44f530ce6a7",
                "sha256": AVERITEC_SHA256,
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
            "model_outputs_used": False,
            "maximum_selected_spans": 8,
            "prior_artifact_sources": exclusion_sources,
            "prior_case_ids": len(excluded_ids),
            "prior_normalized_claims": len(excluded_claims),
            "candidates_before_exclusion": dict(sorted(candidates_before.items())),
            "candidates_after_overlap_exclusion": dict(
                sorted(candidates_after_overlap.items())
            ),
            "candidates_after_evidence_filter": dict(
                sorted(candidates_after_evidence.items())
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
            "AVeriTeC development labels are public, so base-model pretraining contamination cannot be ruled out.",
            "AVeriTeC Not Enough Evidence is conservatively mapped to unsupported rather than ambiguity.",
            "The partially-supported slice uses previously unselected WiCE test cases because AVeriTeC has no partial-support label.",
            "Labels are aligned from upstream tasks rather than newly annotated for ContextTrace.",
            "The benchmark jointly measures label-blind evidence selection and verification.",
        ],
    }
    manifest = {
        "schema_version": "contexttrace-v19-confirmation-manifest-1.0",
        "experiment": EXPERIMENT,
        "status": "frozen_before_v18_candidate_scoring",
        "dataset_sha256": _sha256_json(dataset),
        "audit_sha256": _sha256_json(audit),
        "v18_artifact_sha256": V18_ARTIFACT_SHA256,
        "candidate_or_policy_changed_after_v18": False,
        "confirmation_predictions_generated": False,
        "confirmation_predictions_inspected": False,
        "confirmation_labels_used_for_selection": False,
        "retraining_allowed": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
    }
    return dataset, audit, manifest


def _averitec_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise V19BuildError("AVeriTeC development source is empty or invalid.")
    output = []
    for index, row in enumerate(payload):
        upstream = str(row.get("label") or "")
        if upstream not in AVERITEC_LABELS:
            raise V19BuildError("Unknown AVeriTeC label: %s" % upstream)
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
                            "id": "averitec_dev_%04d_q%03d_a%03d"
                            % (index, question_index, answer_index),
                            "text": "\n".join(parts),
                        }
                    )
        if claim and contexts:
            output.append(
                {
                    "id": "averitec_dev_%04d" % index,
                    "dataset": "AVeriTeC",
                    "source_split": "dev",
                    "source_id": str(index),
                    "query": "",
                    "claim": claim,
                    "contexts": contexts,
                    "expected_verdict": AVERITEC_LABELS[upstream],
                    "upstream_label": upstream,
                }
            )
    return output


def _prior_examples(
    repository_root: Path, additional: list[str | Path]
) -> tuple[set[str], set[str], list[dict[str, Any]]]:
    paths = sorted(repository_root.glob("benchmarks/**/*.json")) + [
        Path(value) for value in additional
    ]
    ids: set[str] = set()
    claims: set[str] = set()
    sources = []
    seen_paths = set()
    for path in paths:
        resolved = str(path.resolve())
        if resolved in seen_paths or not path.is_file():
            continue
        seen_paths.add(resolved)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        rows = payload.get("cases") or payload.get("examples") or []
        found = 0
        for row in rows if isinstance(rows, list) else []:
            case_id = str(row.get("id") or row.get("case_id") or "")
            claim = row.get("claim")
            if claim is None and isinstance(row.get("input"), dict):
                claim = row["input"].get("claim")
            if case_id:
                ids.add(case_id)
            if claim:
                claims.add(_normalized_claim(str(claim)))
                found += 1
        if found:
            sources.append(
                {
                    "path": str(path.relative_to(repository_root))
                    if path.is_relative_to(repository_root)
                    else str(path),
                    "sha256": _sha256_file(path),
                    "claims": found,
                }
            )
    return ids, claims, sources


def _normalized_claim(value: str) -> str:
    return " ".join(str(value).casefold().split())


def _stable_rank(label: str, case_id: str) -> str:
    return hashlib.sha256(f"{SEED}|{label}|{case_id}".encode()).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_hash(path: Path, expected: str) -> None:
    if not path.is_file() or _sha256_file(path) != expected:
        raise V19BuildError("Source does not match its frozen hash: %s" % path)


def _write(path: str | Path, value: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--averitec", required=True)
    parser.add_argument("--wice", required=True)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--exclude-dataset", action="append", default=[])
    parser.add_argument("--per-label", type=int, default=PER_LABEL)
    parser.add_argument("--dataset-output", required=True)
    parser.add_argument("--audit-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    args = parser.parse_args(argv)
    values = build_confirmation(
        args.averitec,
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
