"""Join sealed gold to frozen predictions inside the custodian's label zone."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from benchmarks.contexttrace_unseen_v1.baselines.contract import (
    build_candidate_input,
    verify_manifest_identity,
)

from .integrity import (
    EvaluationIntegrityError,
    canonical_sha256,
    file_sha256,
    load_json_object,
    verify_phase6_locks,
)
from .scoring import (
    FAILURE_LABELS,
    aggregate_metrics,
    align_claims,
    binary_f1,
    confusion,
    dangerous_false_green,
    root_accuracy,
)
from .statistics import (
    hierarchical_cluster_bootstrap,
    holm_adjust,
    paired_cluster_randomization,
)
from .v1_mapping import map_v1_output


SCORER_VERSION = "contexttrace-unseen-v1-sealed-scorer-1.0"
SEALED_CONFIRMATION = "I_AM_THE_LABEL_CUSTODIAN_IN_THE_PRIVATE_LABEL_ZONE"


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _quantile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    index = max(0, math.ceil(probability * len(ordered)) - 1)
    return ordered[index]


def _safe_trace(
    artifact_root: Path, case: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    root = artifact_root.resolve()
    trace_path = (root / str(case["trace_artifact_path"])).resolve()
    if root not in trace_path.parents:
        raise EvaluationIntegrityError("Trace path escapes artifact root.")
    if file_sha256(trace_path) != case["trace_sha256"]:
        raise EvaluationIntegrityError(f"{case['case_id']}: trace hash mismatch.")
    trace = load_json_object(trace_path)
    candidate = build_candidate_input(case, trace)
    context_sources = {
        str(chunk["chunk_id"]): str(chunk["source_id"])
        for chunk in candidate["retrieved_chunks"]
    }
    return candidate, context_sources


def _candidate_run_identity(record: Mapping[str, Any]) -> str:
    identity = dict(record)
    expected = identity.pop("run_payload_sha256", None)
    outputs = identity.get("outputs")
    if not isinstance(outputs, list):
        raise EvaluationIntegrityError("Candidate run outputs are invalid.")
    identity["outputs"] = [
        {
            **row,
            "profiles": {
                profile_id: {
                    key: item for key, item in value.items() if key != "latency_ms"
                }
                for profile_id, value in row["profiles"].items()
            },
        }
        for row in outputs
    ]
    actual = canonical_sha256(identity)
    if actual != expected:
        raise EvaluationIntegrityError("Candidate run payload hash mismatch.")
    return actual


def _v1_run_identity(record: Mapping[str, Any]) -> str:
    identity = dict(record)
    expected = identity.pop("run_payload_sha256", None)
    outputs = identity.get("outputs")
    if not isinstance(outputs, list):
        raise EvaluationIntegrityError("Predecessor run outputs are invalid.")
    identity["outputs"] = [
        {key: value for key, value in row.items() if key != "latency_ms"}
        for row in outputs
        if isinstance(row, Mapping)
    ]
    actual = canonical_sha256(identity)
    if actual != expected:
        raise EvaluationIntegrityError("Predecessor run payload hash mismatch.")
    return actual


def _load_gold(path: Path, schema_path: Path, expected_hash: str) -> dict[str, Any]:
    if file_sha256(path) != expected_hash:
        raise EvaluationIntegrityError("Sealed-gold file hash mismatch.")
    gold = load_json_object(path)
    schema = load_json_object(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(gold), key=lambda error: tuple(error.absolute_path)
    )
    if errors:
        raise EvaluationIntegrityError(f"Sealed gold is invalid: {errors[0].message}")
    if gold.get("document_kind") != "sealed_gold":
        raise EvaluationIntegrityError("Scorer accepts only sealed_gold.")
    return gold


def _prediction_claims(
    run_row: Mapping[str, Any], profile_id: str
) -> list[Mapping[str, Any]]:
    profile = run_row.get("profiles", {}).get(profile_id)
    if not isinstance(profile, Mapping):
        return []
    prediction = profile.get("prediction")
    if not isinstance(prediction, Mapping):
        return []
    claims = prediction.get("claims")
    return (
        [claim for claim in claims if isinstance(claim, Mapping)]
        if isinstance(claims, list)
        else []
    )


def _make_rows(
    *,
    cases: Sequence[Mapping[str, Any]],
    gold_by_case: Mapping[str, Mapping[str, Any]],
    candidate_by_case: dict[str, dict[str, Any]],
    v1_by_case: Mapping[str, Mapping[str, Any]],
    candidates: Mapping[str, Mapping[str, Any]],
    context_sources: Mapping[str, Mapping[str, str]],
    profile_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_rows: list[dict[str, Any]] = []
    paired_rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["case_id"])
        gold_case = gold_by_case.get(case_id)
        if gold_case is None:
            raise EvaluationIntegrityError(f"Gold is missing case {case_id}.")
        gold_claims = [
            claim
            for claim in gold_case.get("claims", [])
            if isinstance(claim, Mapping) and claim.get("propositional") is True
        ]
        candidate_claims = _prediction_claims(candidate_by_case[case_id], profile_id)
        v1_claims = list(v1_by_case[case_id]["claims"])
        aligned_candidate, candidate_spurious = align_claims(
            gold_claims, candidate_claims
        )
        aligned_v1, v1_spurious = align_claims(gold_claims, v1_claims)
        v1_predictions = [prediction for _, prediction in aligned_v1]
        base = {
            "case_id": case_id,
            "track": case["track"],
            "domain": case["domain_group"],
            "source_family": case["source_family"],
            "retrieval_family": case["retrieval"]["family"],
            "context_sources": context_sources[case_id],
        }
        for index, (gold, prediction) in enumerate(aligned_candidate):
            row = {
                **base,
                "gold": gold,
                "prediction": prediction,
                "candidate_prediction": prediction,
                "predecessor_prediction": v1_predictions[index],
            }
            candidate_rows.append(row)
            paired_rows.append(row)
        candidate_by_case[case_id]["_scoring_counts"] = {
            "gold_claims": len(gold_claims),
            "candidate_spurious": len(candidate_spurious),
            "v1_spurious": len(v1_spurious),
        }
    return candidate_rows, paired_rows


def _failure_macro(rows: Sequence[Mapping[str, Any]]) -> float | None:
    return confusion(
        rows,
        gold_field="failure_label",
        pred_field="failure_label",
        classes=FAILURE_LABELS,
    )["macro_f1"]


def _difference(
    left: Sequence[Mapping[str, Any]], right: Sequence[Mapping[str, Any]]
) -> float | None:
    left_value = _failure_macro(left)
    right_value = _failure_macro(right)
    return (
        left_value - right_value
        if left_value is not None and right_value is not None
        else None
    )


def _root_accuracy_value(rows: Sequence[Mapping[str, Any]]) -> float | None:
    return root_accuracy(rows)["accuracy"]


def _unverifiable_f1_value(rows: Sequence[Mapping[str, Any]]) -> float | None:
    return binary_f1(
        rows,
        gold_positive=lambda gold: gold["claim_verdict"] == "unverifiable",
        pred_positive=lambda pred: pred.get("claim_verdict") == "unverifiable",
    )["f1"]


def _dangerous_false_green_value(
    rows: Sequence[Mapping[str, Any]], threshold: float
) -> float | None:
    return dangerous_false_green(rows, threshold=threshold)["claim_rate"]


def score_sealed(
    *,
    repository_root: Path,
    manifest_path: Path,
    artifact_root: Path,
    candidate_run_path: Path,
    candidate_run_sha256: str,
    v1_run_path: Path,
    v1_run_sha256: str,
    gold_path: Path,
    gold_sha256: str,
    output_directory: Path,
    confirmation: str,
    bootstrap_replicates: int | None = None,
    randomization_replicates: int | None = None,
) -> dict[str, Any]:
    if confirmation != SEALED_CONFIRMATION:
        raise EvaluationIntegrityError("Private sealed-zone confirmation is absent.")
    if output_directory.exists():
        raise EvaluationIntegrityError("Scoring output directory must not exist.")
    locks = verify_phase6_locks(repository_root)
    config = locks["evaluation"]
    manifest = load_json_object(manifest_path)
    if file_sha256(manifest_path) != config["dataset"]["frozen_manifest_file_sha256"]:
        raise EvaluationIntegrityError("Frozen manifest file hash mismatch.")
    cases = verify_manifest_identity(
        manifest,
        expected_payload_sha256=config["dataset"]["frozen_manifest_payload_sha256"],
    )
    gold = _load_gold(
        gold_path,
        repository_root / "benchmarks/contexttrace_unseen_v1/ANNOTATION_SCHEMA.json",
        gold_sha256,
    )
    if (
        gold.get("manifest_sha256")
        != config["dataset"]["frozen_manifest_payload_sha256"]
    ):
        raise EvaluationIntegrityError("Gold and manifest identities disagree.")
    if file_sha256(candidate_run_path) != candidate_run_sha256:
        raise EvaluationIntegrityError("Candidate-run file hash mismatch.")
    candidate_run = load_json_object(candidate_run_path)
    _candidate_run_identity(candidate_run)
    if (
        candidate_run.get("manifest_payload_sha256")
        != config["dataset"]["frozen_manifest_payload_sha256"]
    ):
        raise EvaluationIntegrityError("Candidate run used a different manifest.")
    if (
        candidate_run.get("implementation_source_manifest_sha256")
        != config["candidate_system"]["implementation_source_manifest_sha256"]
    ):
        raise EvaluationIntegrityError("Candidate run used a different implementation.")
    expected_profiles = {
        locks["ablations"]["candidate_profile"]["id"]: locks["ablations"][
            "candidate_profile"
        ]["sha256"],
        **{
            row["profile_id"]: row["profile_sha256"]
            for row in locks["ablations"]["ablations"]
        },
    }
    actual_profiles = {
        row.get("profile_id"): row.get("profile_sha256")
        for row in candidate_run.get("profile_locks", [])
        if isinstance(row, Mapping)
    }
    if actual_profiles != expected_profiles:
        raise EvaluationIntegrityError("Candidate run profile locks differ.")
    if file_sha256(v1_run_path) != v1_run_sha256:
        raise EvaluationIntegrityError("Predecessor-run file hash mismatch.")
    expected_v1_hash = next(
        row["raw_output_file_sha256"]
        for row in locks["baseline_run"]["runs"]
        if row["baseline_id"] == "semantic_v1_calibrated"
    )
    if v1_run_sha256 != expected_v1_hash:
        raise EvaluationIntegrityError("Predecessor run is not the frozen v1 output.")
    v1_run = load_json_object(v1_run_path)
    _v1_run_identity(v1_run)
    if (
        v1_run.get("facts_source_sha256")
        != config["predecessor"]["facts_source_sha256"]
    ):
        raise EvaluationIntegrityError("Predecessor facts-source hash mismatch.")

    candidate_by_case = {
        str(row["case_id"]): row for row in candidate_run.get("outputs", [])
    }
    raw_v1_by_case = {str(row["case_id"]): row for row in v1_run.get("outputs", [])}
    gold_by_case = {str(row["case_id"]): row for row in gold.get("cases", [])}
    expected_ids = [str(case["case_id"]) for case in cases]
    for name, index in (
        ("candidate", candidate_by_case),
        ("predecessor", raw_v1_by_case),
        ("gold", gold_by_case),
    ):
        if set(index) != set(expected_ids):
            raise EvaluationIntegrityError(f"{name} case IDs are incomplete or extra.")

    candidates: dict[str, Mapping[str, Any]] = {}
    context_sources: dict[str, Mapping[str, str]] = {}
    for case in cases:
        case_id = str(case["case_id"])
        candidate, sources = _safe_trace(artifact_root, case)
        if (
            _text_sha256(str(candidate["answer"]))
            != gold_by_case[case_id]["answer_sha256"]
        ):
            raise EvaluationIntegrityError(f"{case_id}: gold answer hash mismatch.")
        if (
            candidate["candidate_input_sha256"]
            != candidate_by_case[case_id]["candidate_input_sha256"]
        ):
            raise EvaluationIntegrityError(f"{case_id}: candidate input mismatch.")
        candidates[case_id] = candidate
        context_sources[case_id] = sources
    v1_by_case = {
        case_id: map_v1_output(raw_v1_by_case[case_id]) for case_id in expected_ids
    }

    statistical = config["statistical_analysis"]
    bootstrap_replicates = (
        statistical["bootstrap_replicates"]
        if bootstrap_replicates is None
        else bootstrap_replicates
    )
    randomization_replicates = (
        statistical["paired_randomization_replicates"]
        if randomization_replicates is None
        else randomization_replicates
    )
    if bootstrap_replicates != statistical["bootstrap_replicates"]:
        raise EvaluationIntegrityError(
            "Production scorer requires exactly 10,000 bootstrap replicates."
        )
    if randomization_replicates != statistical["paired_randomization_replicates"]:
        raise EvaluationIntegrityError(
            "Production scorer requires exactly 100,000 randomization replicates."
        )

    profile_ids = [row["profile_id"] for row in candidate_run["profile_locks"]]
    system_metrics: dict[str, Any] = {}
    private_counts: dict[str, Any] = {}
    primary_rows: list[dict[str, Any]] | None = None
    paired_primary: list[dict[str, Any]] | None = None
    for profile_id in profile_ids:
        rows, paired = _make_rows(
            cases=cases,
            gold_by_case=gold_by_case,
            candidate_by_case=candidate_by_case,
            v1_by_case=v1_by_case,
            candidates=candidates,
            context_sources=context_sources,
            profile_id=profile_id,
        )
        metrics = aggregate_metrics(
            rows,
            green_threshold=config["thresholds"]["green_confidence"],
            ece_bins=statistical["ece_bins"],
        )
        latencies = [
            float(row["profiles"][profile_id]["latency_ms"])
            for row in candidate_run["outputs"]
            if isinstance(row["profiles"][profile_id].get("latency_ms"), (int, float))
        ]
        profile_failures = sum(
            row["profiles"][profile_id].get("status") != "completed"
            for row in candidate_run["outputs"]
        )
        metrics["latency_ms"] = {
            "count": len(latencies),
            "p50": _quantile(latencies, 0.50),
            "p95": _quantile(latencies, 0.95),
            "p99": _quantile(latencies, 0.99),
        }
        metrics["runtime_failures"] = {
            "numerator": profile_failures,
            "denominator": len(candidate_run["outputs"]),
            "rate": profile_failures / len(candidate_run["outputs"]),
        }
        metrics["by_track"] = {
            track: aggregate_metrics(
                [row for row in rows if row["track"] == track],
                green_threshold=config["thresholds"]["green_confidence"],
                ece_bins=statistical["ece_bins"],
            )
            for track in ("natural_ood", "temporal_source_condition")
        }
        metrics["by_domain"] = {
            domain: aggregate_metrics(
                [row for row in rows if row["domain"] == domain],
                green_threshold=config["thresholds"]["green_confidence"],
                ece_bins=statistical["ece_bins"],
            )
            for domain in sorted({str(row["domain"]) for row in rows})
        }
        system_metrics[profile_id] = metrics
        if profile_id == config["candidate_system"]["profile_id"]:
            primary_rows = rows
            paired_primary = paired
            private_counts = {
                case_id: candidate_by_case[case_id].get("_scoring_counts", {})
                for case_id in expected_ids
            }
    if primary_rows is None or paired_primary is None:
        raise EvaluationIntegrityError("Primary candidate profile is absent.")

    predecessor_rows = [
        {**row, "prediction": row["predecessor_prediction"]} for row in paired_primary
    ]
    predecessor_metrics = aggregate_metrics(
        predecessor_rows,
        green_threshold=config["thresholds"]["green_confidence"],
        ece_bins=statistical["ece_bins"],
    )
    predecessor_latencies = [
        float(row["latency_ms"])
        for row in v1_run["outputs"]
        if isinstance(row.get("latency_ms"), (int, float))
    ]
    predecessor_metrics["latency_ms"] = {
        "count": len(predecessor_latencies),
        "p50": _quantile(predecessor_latencies, 0.50),
        "p95": _quantile(predecessor_latencies, 0.95),
        "p99": _quantile(predecessor_latencies, 0.99),
    }
    candidate_macro = _failure_macro(primary_rows)
    predecessor_macro = _failure_macro(predecessor_rows)
    delta = (
        candidate_macro - predecessor_macro
        if candidate_macro is not None and predecessor_macro is not None
        else None
    )
    candidate_macro_bootstrap = hierarchical_cluster_bootstrap(
        primary_rows,
        _failure_macro,
        replicates=bootstrap_replicates,
        seed=statistical["seed"],
    )
    delta_bootstrap = hierarchical_cluster_bootstrap(
        paired_primary,
        lambda sample: _difference(
            [{**row, "prediction": row["candidate_prediction"]} for row in sample],
            [{**row, "prediction": row["predecessor_prediction"]} for row in sample],
        ),
        replicates=bootstrap_replicates,
        seed=statistical["seed"],
        tail_predicate=lambda value: value <= 0.0,
    )
    root_bootstrap = hierarchical_cluster_bootstrap(
        primary_rows,
        _root_accuracy_value,
        replicates=bootstrap_replicates,
        seed=statistical["seed"],
        tail_predicate=lambda value: (
            value < config["success_gates"]["root_cause_accuracy_minimum"]
        ),
    )
    unverifiable_bootstrap = hierarchical_cluster_bootstrap(
        primary_rows,
        _unverifiable_f1_value,
        replicates=bootstrap_replicates,
        seed=statistical["seed"],
        tail_predicate=lambda value: (
            value < config["success_gates"]["unverifiable_f1_minimum"]
        ),
    )
    green_threshold = config["thresholds"]["green_confidence"]
    false_green_bootstrap = hierarchical_cluster_bootstrap(
        primary_rows,
        lambda sample: _dangerous_false_green_value(sample, green_threshold),
        replicates=bootstrap_replicates,
        seed=statistical["seed"],
        tail_predicate=lambda value: (
            value > config["success_gates"]["dangerous_false_green_rate_maximum"]
        ),
    )
    randomization = paired_cluster_randomization(
        paired_primary,
        _difference,
        replicates=randomization_replicates,
        seed=statistical["seed"],
    )
    adjusted = holm_adjust(
        {
            "failure_label_macro_f1_delta": randomization["p_value"],
            "root_cause_accuracy": root_bootstrap["plus_one_tail_probability"],
            "unverifiable_f1": unverifiable_bootstrap["plus_one_tail_probability"],
            "dangerous_false_green_rate": false_green_bootstrap[
                "plus_one_tail_probability"
            ],
        }
    )
    release: dict[str, Any] = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_cain2027_sealed_evaluation_aggregate",
        "scorer_version": SCORER_VERSION,
        "dataset_id": config["dataset"]["id"],
        "manifest_payload_sha256": config["dataset"]["frozen_manifest_payload_sha256"],
        "gold_file_sha256": gold_sha256,
        "candidate_run_file_sha256": candidate_run_sha256,
        "predecessor_run_file_sha256": v1_run_sha256,
        "case_count": len(cases),
        "systems": {
            **system_metrics,
            "semantic_v1_calibrated": predecessor_metrics,
        },
        "confirmatory": {
            "failure_label_macro_f1_delta": {
                "candidate": candidate_macro,
                "predecessor": predecessor_macro,
                "difference": delta,
                "candidate_bootstrap": candidate_macro_bootstrap,
                "difference_bootstrap": delta_bootstrap,
                "paired_randomization": randomization,
                "holm_adjusted_p_value": adjusted["failure_label_macro_f1_delta"],
            },
            "root_cause_accuracy": {
                "point": system_metrics[config["candidate_system"]["profile_id"]][
                    "root_cause"
                ]["accuracy"],
                "bootstrap": root_bootstrap,
                "holm_adjusted_p_value": adjusted["root_cause_accuracy"],
            },
            "unverifiable_f1": {
                "point": system_metrics[config["candidate_system"]["profile_id"]][
                    "unverifiable"
                ]["f1"],
                "bootstrap": unverifiable_bootstrap,
                "holm_adjusted_p_value": adjusted["unverifiable_f1"],
            },
            "dangerous_false_green_rate": {
                "point": system_metrics[config["candidate_system"]["profile_id"]][
                    "dangerous_false_green"
                ]["claim_rate"],
                "bootstrap": false_green_bootstrap,
                "holm_adjusted_p_value": adjusted["dangerous_false_green_rate"],
            },
            "holm_adjusted_p_values": adjusted,
        },
    }
    release["payload_sha256"] = canonical_sha256(release)
    private = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_cain2027_private_scoring_detail",
        "release_payload_sha256": release["payload_sha256"],
        "per_case_alignment_counts": private_counts,
    }
    private["payload_sha256"] = canonical_sha256(private)

    output_directory.mkdir(mode=0o700, parents=True)
    os.chmod(output_directory, 0o700)
    (output_directory / "aggregate-metrics.json").write_text(
        json.dumps(release, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_directory / "private-scoring-detail.json").write_text(
        json.dumps(private, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(output_directory / "private-scoring-detail.json", 0o600)
    return release


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--candidate-run", type=Path, required=True)
    parser.add_argument("--candidate-run-sha256", required=True)
    parser.add_argument("--v1-run", type=Path, required=True)
    parser.add_argument("--v1-run-sha256", required=True)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--gold-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--confirm-sealed-zone", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result = score_sealed(
        repository_root=args.repository_root,
        manifest_path=args.manifest,
        artifact_root=args.artifact_root,
        candidate_run_path=args.candidate_run,
        candidate_run_sha256=args.candidate_run_sha256,
        v1_run_path=args.v1_run,
        v1_run_sha256=args.v1_run_sha256,
        gold_path=args.gold,
        gold_sha256=args.gold_sha256,
        output_directory=args.output_directory,
        confirmation=args.confirm_sealed_zone,
    )
    print(
        json.dumps(
            {
                "case_count": result["case_count"],
                "payload_sha256": result["payload_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
