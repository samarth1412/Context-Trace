"""Diagnose atomic-coverage errors with WiCE gold evidence groups."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

from contexttrace.verify.schema import TraceContext
from contexttrace.verify.semantic_core_v2.nli import build_pinned_nli
from contexttrace.verify.semantic_core_v2.nli import verify_nli_artifact


class AtomicAuditError(RuntimeError):
    """Raised when an atomic failure audit violates its diagnostic contract."""


def load_source_groups(path: str | Path) -> dict[str, list[list[int]]]:
    groups = {}
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            source_id = str((row.get("meta") or {}).get("id") or "")
            if not source_id:
                continue
            values = []
            for group in row.get("supporting_sentences") or []:
                if isinstance(group, list) and group and all(
                    isinstance(index, int) for index in group
                ):
                    values.append(list(dict.fromkeys(group)))
            groups["wice_%s" % source_id] = values
    return groups


def exact_requirement_provenance(claim: str, requirement: str) -> bool:
    return _normalize(requirement).strip(".!?") in _normalize(claim).strip(".!?")


def selected_source_ids(requirements: list[dict[str, Any]]) -> set[str]:
    return {
        str(context_id).rsplit(":", 2)[0]
        for requirement in requirements
        for context_id in requirement.get("evidence_context_ids") or []
    }


def threshold_prediction(requirements: list[dict[str, Any]], threshold: float) -> str:
    complete = bool(requirements) and all(
        float(requirement["nli_scores"]["entailment"]) >= threshold
        for requirement in requirements
    )
    return "supported" if complete else "partially_supported"


def _oracle_groups(
    *,
    case: dict[str, Any],
    groups: list[list[int]],
    requirements: list[dict[str, Any]],
    nli: object,
    threshold: float,
) -> dict[str, Any]:
    contexts = {
        str(item["id"]): str(item["text"])
        for item in case.get("contexts") or []
    }
    rows = []
    for group_number, indexes in enumerate(groups):
        context_ids = ["%s_e%04d" % (case["id"], index) for index in indexes]
        texts = [contexts[context_id] for context_id in context_ids if context_id in contexts]
        if len(texts) != len(context_ids):
            raise AtomicAuditError("Gold evidence group contains an unknown context id.")
        premise = "\n".join(texts)
        requirement_rows = []
        for requirement in requirements:
            started = time.perf_counter()
            verdict = nli.verify_claim(  # type: ignore[attr-defined]
                query="",
                claim=str(requirement["requirement"]),
                contexts=[
                    TraceContext(
                        id="oracle:%s:%d" % (case["id"], group_number),
                        text=premise,
                    )
                ],
            )
            scores = {
                key: float(value)
                for key, value in dict(verdict.raw.get("nli_scores") or {}).items()
            }
            if set(scores) != {"entailment", "contradiction", "neutral"}:
                raise AtomicAuditError("Oracle NLI omitted its full score distribution.")
            requirement_rows.append(
                {
                    "requirement": str(requirement["requirement"]),
                    "nli_scores": scores,
                    "nli_label": str(verdict.raw.get("nli_label") or ""),
                    "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
                }
            )
        rows.append(
            {
                "group_number": group_number,
                "context_ids": context_ids,
                "requirements": requirement_rows,
                "passes_atomic_threshold": bool(requirement_rows)
                and all(
                    row["nli_scores"]["entailment"] >= threshold
                    for row in requirement_rows
                ),
            }
        )
    return {
        "groups": rows,
        "any_group_passes_atomic_threshold": any(
            row["passes_atomic_threshold"] for row in rows
        ),
    }


def audit(
    *,
    case_pack: dict[str, Any],
    run: dict[str, Any],
    source_groups: dict[str, list[list[int]]],
    nli: object,
    threshold: float,
) -> dict[str, Any]:
    cases = {str(case["id"]): case for case in case_pack.get("cases") or []}
    validation_rows = [row for row in run.get("rows") or [] if row["cohort"] == "validation"]
    if set(cases) != {str(row["case_id"]) for row in validation_rows}:
        raise AtomicAuditError("Validation case pack and atomic run do not match.")
    rows = []
    for prediction_row in validation_rows:
        case_id = str(prediction_row["case_id"])
        case = cases[case_id]
        requirements = list(prediction_row["prediction"]["requirements"])
        selected_ids = selected_source_ids(requirements)
        groups = source_groups.get(case_id) or []
        group_context_ids = [
            {"%s_e%04d" % (case_id, index) for index in group} for group in groups
        ]
        complete_group_retrieved = any(group <= selected_ids for group in group_context_ids)
        annotated_ids = set(case.get("upstream_evidence_context_ids") or [])
        oracle = _oracle_groups(
            case=case,
            groups=groups,
            requirements=requirements,
            nli=nli,
            threshold=threshold,
        )
        predicted = threshold_prediction(requirements, threshold)
        provenance = [
            exact_requirement_provenance(str(case["claim"]), row["requirement"])
            for row in requirements
        ]
        rows.append(
            {
                "case_id": case_id,
                "expected_verdict": str(case["expected_verdict"]),
                "atomic_prediction": predicted,
                "correct": predicted == case["expected_verdict"],
                "requirements": [row["requirement"] for row in requirements],
                "all_requirements_have_exact_claim_provenance": all(provenance),
                "requirements_without_exact_claim_provenance": [
                    row["requirement"]
                    for row, exact in zip(requirements, provenance, strict=True)
                    if not exact
                ],
                "selected_source_context_ids": sorted(selected_ids),
                "at_least_one_annotated_context_retrieved": bool(
                    annotated_ids & selected_ids
                ),
                "complete_gold_group_retrieved": complete_group_retrieved,
                "gold_evidence_diagnostic": oracle,
                "diagnostic_only_gold_evidence_used_as_candidate_input": False,
            }
        )
    return _result(rows, threshold=threshold)


def _result(rows: list[dict[str, Any]], *, threshold: float) -> dict[str, Any]:
    supported = [row for row in rows if row["expected_verdict"] == "supported"]
    partial = [row for row in rows if row["expected_verdict"] == "partially_supported"]
    supported_false_negative = [
        row for row in supported if row["atomic_prediction"] != "supported"
    ]
    retrieval_limited = [
        row
        for row in supported_false_negative
        if row["gold_evidence_diagnostic"]["any_group_passes_atomic_threshold"]
        and not row["complete_gold_group_retrieved"]
    ]
    verifier_limited = [
        row
        for row in supported_false_negative
        if not row["gold_evidence_diagnostic"]["any_group_passes_atomic_threshold"]
    ]
    requirement_routing_limited = [
        row
        for row in supported_false_negative
        if row["gold_evidence_diagnostic"]["any_group_passes_atomic_threshold"]
        and row["complete_gold_group_retrieved"]
    ]
    false_support = [
        row for row in partial if row["atomic_prediction"] == "supported"
    ]
    oracle_latencies = [
        requirement["latency_ms"]
        for row in rows
        for group in row["gold_evidence_diagnostic"]["groups"]
        for requirement in group["requirements"]
    ]
    summary = {
        "cases": len(rows),
        "threshold": threshold,
        "requirement_count_distribution": dict(
            sorted(Counter(len(row["requirements"]) for row in rows).items())
        ),
        "cases_with_non_source_requirement": sum(
            not row["all_requirements_have_exact_claim_provenance"] for row in rows
        ),
        "supported_cases": len(supported),
        "supported_predicted_supported": sum(
            row["atomic_prediction"] == "supported" for row in supported
        ),
        "supported_with_any_annotated_retrieval": sum(
            row["at_least_one_annotated_context_retrieved"] for row in supported
        ),
        "supported_with_complete_gold_group_retrieved": sum(
            row["complete_gold_group_retrieved"] for row in supported
        ),
        "supported_passing_with_gold_evidence": sum(
            row["gold_evidence_diagnostic"]["any_group_passes_atomic_threshold"]
            for row in supported
        ),
        "supported_false_negatives": len(supported_false_negative),
        "supported_false_negatives_retrieval_limited": len(retrieval_limited),
        "supported_false_negatives_requirement_routing_limited": len(
            requirement_routing_limited
        ),
        "supported_false_negatives_verifier_or_decomposition_limited": len(
            verifier_limited
        ),
        "partial_cases": len(partial),
        "partial_incorrectly_supported": len(false_support),
        "partial_incorrectly_supported_case_ids": [row["case_id"] for row in false_support],
        "oracle_nli_calls": len(oracle_latencies),
        "oracle_nli_mean_latency_ms": round(statistics.fmean(oracle_latencies), 3)
        if oracle_latencies
        else None,
    }
    return {
        "schema_version": "atomic-coverage-failure-audit-1.0",
        "scope": "fresh_development_validation_only",
        "candidate_run_uses_gold_evidence": False,
        "gold_evidence_use": "post_prediction_diagnostic_only",
        "local_only": True,
        "remote_inference": False,
        "evaluation_labels_sent_to_nli": False,
        "summary": summary,
        "failure_case_ids": {
            "retrieval_limited": [row["case_id"] for row in retrieval_limited],
            "verifier_or_decomposition_limited": [
                row["case_id"] for row in verifier_limited
            ],
            "requirement_routing_limited": [
                row["case_id"] for row in requirement_routing_limited
            ],
            "non_source_requirements": [
                row["case_id"]
                for row in rows
                if not row["all_requirements_have_exact_claim_provenance"]
            ],
        },
        "rows": rows,
    }


def _normalize(value: str) -> str:
    return " ".join(str(value).casefold().split())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    case_path = Path(args.cases)
    run_path = Path(args.run)
    analysis_path = Path(args.analysis)
    source_path = Path(args.source)
    case_pack = json.loads(case_path.read_text(encoding="utf-8"))
    expected_source_hash = str((case_pack.get("source") or {}).get("sha256") or "")
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if source_hash != expected_source_hash:
        raise AtomicAuditError("WiCE source hash does not match the case-pack lock.")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    threshold = float(analysis["policy"]["threshold"])
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    artifact = verify_nli_artifact(args.model_path)
    result = audit(
        case_pack=case_pack,
        run=run,
        source_groups=load_source_groups(source_path),
        nli=build_pinned_nli(args.model_path),
        threshold=threshold,
    )
    result["inputs"] = {
        "case_pack_sha256": hashlib.sha256(case_path.read_bytes()).hexdigest(),
        "candidate_run_sha256": hashlib.sha256(run_path.read_bytes()).hexdigest(),
        "analysis_sha256": hashlib.sha256(analysis_path.read_bytes()).hexdigest(),
        "source_sha256": source_hash,
        "nli_artifact_manifest_sha256": artifact["artifact_manifest_sha256"],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
