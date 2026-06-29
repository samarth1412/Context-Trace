from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "packages" / "contexttrace"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

try:
    from benchmarks.contexttrace_bench.arr_annotation import SAFE_CONTEXT_METADATA, load_annotation_records
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from arr_annotation import SAFE_CONTEXT_METADATA, load_annotation_records  # type: ignore

from contexttrace.verify.runner import FULL_VERIFICATION_PROFILE, VerificationProfile, verify_trace
from contexttrace.verify.schema import load_trace


DEFAULT_OUTPUT_DIR = Path(__file__).with_name("out") / "arr_actionability"
DEFAULT_SPEC_PATH = Path(__file__).with_name("ARR_EXPERIMENTS.json")
DEFAULT_SEED = 20260629
DEFAULT_BOOTSTRAP_SAMPLES = 2000
FULL_STUDY_CASES = 40
CONDITION_EVIDENCE = "evidence_chain"
CONDITION_CORE = "semantic_core"
OPTION_NAMES = ("option_1", "option_2")
PREFERENCE_VALUES = {*OPTION_NAMES, "tie", "neither"}
REVIEW_KINDS = {"independent", "pilot_author"}
CORE_PROFILE = VerificationProfile(
    citation_alignment=False,
    abstention_logic=False,
    source_assessment=False,
    root_cause_inference=False,
    evidence_span_localization=False,
)


def build_actionability_artifacts(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    spec_path: str | Path = DEFAULT_SPEC_PATH,
    case_set: str | None = None,
    case_pack_path: str | Path | None = None,
    seed: int | None = None,
    sample_size: int | None = None,
    quick: bool = False,
) -> dict[str, str]:
    study_config = load_actionability_spec(spec_path)
    case_set = str(case_set or study_config["case_set"])
    seed = int(seed if seed is not None else study_config["seed"])
    sample_size = int(sample_size if sample_size is not None else study_config["sample_size"])
    records = load_annotation_records(case_set=case_set, case_pack_path=case_pack_path)
    eligible = [record for record in records if _is_failure_case(record)]
    requested = min(int(study_config["quick_sample_size"]), sample_size) if quick else sample_size
    if not quick and len(eligible) < requested:
        raise ValueError(
            "Actionability study requested %s failure cases but only %s are available."
            % (requested, len(eligible))
        )
    selected = _stratified_sample(eligible, sample_size=requested, seed=seed)
    if not selected:
        raise ValueError("Actionability study requires at least one labeled failure case.")

    rng = random.Random(seed + 1)
    rng.shuffle(selected)
    evidence_first = bool(rng.randrange(2))
    packet_cases: list[dict[str, Any]] = []
    key_cases: list[dict[str, Any]] = []
    for index, record in enumerate(selected, start=1):
        blind_id = "ACT-%04d" % index
        trace = load_trace(record["input"], source=str(record.get("id") or blind_id))
        full_result = verify_trace(trace, mode="semantic", profile=FULL_VERIFICATION_PROFILE)
        core_result = verify_trace(trace, mode="semantic", profile=CORE_PROFILE)
        evidence_option = OPTION_NAMES[0] if (index % 2 == 1) == evidence_first else OPTION_NAMES[1]
        core_option = OPTION_NAMES[1] if evidence_option == OPTION_NAMES[0] else OPTION_NAMES[0]
        outputs = {
            evidence_option: _evidence_chain_output(full_result),
            core_option: _semantic_core_output(core_result),
        }
        packet_cases.append(
            {
                "blind_id": blind_id,
                "query": trace.query,
                "answer": trace.answer,
                "contexts": [_public_context(context.to_dict()) for context in trace.contexts],
                "citations": [
                    {"claim": citation.claim, "source_id": citation.source_id}
                    for citation in trace.citations
                ],
                "option_1": outputs["option_1"],
                "option_2": outputs["option_2"],
                "review": _review_template(),
            }
        )
        key_cases.append(
            {
                "blind_id": blind_id,
                "original_id": record["id"],
                "condition_by_option": {
                    evidence_option: CONDITION_EVIDENCE,
                    core_option: CONDITION_CORE,
                },
                **record["expected"],
            }
        )

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    dataset = _dataset_name(case_set=case_set, case_pack_path=case_pack_path)
    packet = {
        "schema_version": 1,
        "packet_type": "blinded_diagnosis_actionability",
        "dataset": dataset,
        "quick": quick,
        "paper_result_eligible": False,
        "seed": seed,
        "generated_at": generated_at,
        "case_count": len(packet_cases),
        "reviewer": "",
        "review_kind": "",
        "instructions": [
            "Judge each option only from the supplied trace; do not access the private key.",
            "Rate diagnosis correctness, repair actionability, repair specificity, and evidence sufficiency for both options.",
            "Choose the option more useful for repair, or select tie/neither.",
            "Record uncertainty in the rationale and confidence fields.",
        ],
        "scales": {
            "repair_specificity": "1=generic, 5=specific and implementable",
            "evidence_sufficiency": "1=insufficient, 5=enough to verify the diagnosis",
            "confidence": "1=low, 5=high",
        },
        "cases": packet_cases,
    }
    key = {
        "schema_version": 1,
        "packet_type": "private_actionability_condition_key",
        "dataset": dataset,
        "quick": quick,
        "seed": seed,
        "generated_at": generated_at,
        "commit": _git_commit(),
        "case_count": len(key_cases),
        "study_config": study_config,
        "cases": key_cases,
    }
    validation = validate_actionability_packet(packet)
    if validation["status"] != "passed":
        raise ValueError("Generated actionability packet failed validation: %s" % validation["errors"])

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    packet_path = destination / "actionability_packet.json"
    key_path = destination / "condition_key.private.json"
    validation_path = destination / "actionability_packet_validation.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    key_path.write_text(json.dumps(key, indent=2, sort_keys=True), encoding="utf-8")
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "packet": str(packet_path),
        "private_key": str(key_path),
        "validation": str(validation_path),
    }


def validate_actionability_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    cases = packet.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append({"name": "cases", "message": "Packet must contain cases."})
        cases = []
    ids = [str(case.get("blind_id") or "") for case in cases if isinstance(case, dict)]
    if any(not blind_id for blind_id in ids) or len(ids) != len(set(ids)):
        errors.append({"name": "blind_ids", "message": "Blind IDs must be non-empty and unique."})
    forbidden = {
        "original_id",
        "condition_by_option",
        "expected",
        "expected_labels",
        "expected_primary_root_cause",
        "benchmark_note",
        "note",
    }
    for case in cases:
        if not isinstance(case, dict):
            errors.append({"name": "case_type"})
            continue
        leaked = sorted(_nested_keys(case).intersection(forbidden))
        if leaked:
            errors.append({"name": "condition_leakage", "blind_id": case.get("blind_id"), "keys": leaked})
        for option in OPTION_NAMES:
            if not isinstance(case.get(option), dict):
                errors.append({"name": "missing_option", "blind_id": case.get("blind_id"), "option": option})
        if not isinstance(case.get("review"), dict):
            errors.append({"name": "review_template", "blind_id": case.get("blind_id")})
    return {
        "status": "passed" if not errors else "failed",
        "case_count": len(cases),
        "errors": errors,
    }


def score_actionability_responses(
    *,
    key_path: str | Path,
    response_paths: list[str | Path],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    bootstrap_samples: int | None = None,
    bootstrap_seed: int | None = None,
) -> dict[str, Any]:
    if not response_paths:
        raise ValueError("At least one completed actionability response is required.")
    key = json.loads(Path(key_path).read_text(encoding="utf-8-sig"))
    study_config = dict(key.get("study_config") or {})
    bootstrap_samples = int(
        bootstrap_samples
        if bootstrap_samples is not None
        else study_config.get("bootstrap_samples") or DEFAULT_BOOTSTRAP_SAMPLES
    )
    bootstrap_seed = int(
        bootstrap_seed if bootstrap_seed is not None else key.get("seed") or DEFAULT_SEED
    )
    if bootstrap_samples <= 0:
        raise ValueError("bootstrap_samples must be positive.")
    key_index = {str(case["blind_id"]): case for case in key.get("cases") or []}
    reviewers = [_load_response(path, key_index) for path in response_paths]
    reviewer_ids = [reviewer["reviewer"] for reviewer in reviewers]
    if len(reviewer_ids) != len(set(reviewer_ids)):
        raise ValueError("Actionability response files must use distinct reviewer IDs.")
    reviewer_reports = [
        _score_reviewer(
            reviewer,
            key_index,
            bootstrap_samples=bootstrap_samples,
            bootstrap_seed=bootstrap_seed + index,
        )
        for index, reviewer in enumerate(reviewers)
    ]
    pairwise = [
        _pairwise_agreement(reviewers[left], reviewers[right], key_index)
        for left in range(len(reviewers))
        for right in range(left + 1, len(reviewers))
    ]
    disagreements = _disagreements(reviewers, key_index)
    independent_complete = [
        row
        for row in reviewer_reports
        if row["review_kind"] == "independent" and row["completed_cases"] == len(key_index)
    ]
    eligibility_gates = {
        "non_quick_packet": not bool(key.get("quick")),
        "target_case_count_met": len(key_index) >= int(study_config.get("sample_size") or FULL_STUDY_CASES),
        "minimum_independent_reviewers_met": len(independent_complete)
        >= int(study_config.get("minimum_independent_reviewers") or 3),
    }
    report = {
        "schema_version": 1,
        "dataset": key.get("dataset"),
        "quick": bool(key.get("quick")),
        "paper_result_eligible": all(eligibility_gates.values()),
        "eligibility_gates": eligibility_gates,
        "case_count": len(key_index),
        "reviewers": reviewer_reports,
        "pairwise_preference_agreement": pairwise,
        "disagreement_cases": len(disagreements),
        "primary_outcome": "evidence-chain preference among decisive choices",
        "inference_note": (
            "Per-reviewer paired results are primary. Pooled reviewer-case observations are descriptive "
            "because repeated judgments are not independent."
        ),
    }
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / "actionability_report.json"
    markdown_path = destination / "actionability_report.md"
    disagreements_path = destination / "actionability_disagreements.jsonl"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_actionability_report(report), encoding="utf-8")
    disagreements_path.write_text(_jsonl(disagreements), encoding="utf-8")
    return {
        **report,
        "outputs": {
            "report": str(report_path),
            "markdown": str(markdown_path),
            "disagreements": str(disagreements_path),
        },
    }


def render_actionability_report(report: dict[str, Any]) -> str:
    lines = [
        "# ARR Diagnosis-Actionability Report",
        "",
        "Dataset: `%s`; cases: `%s`; quick: `%s`."
        % (report.get("dataset"), report.get("case_count"), report.get("quick")),
        "",
        "| Reviewer | Kind | Complete | Evidence wins | Core wins | Ties | Evidence preference [95% CI] | Exact p | Actionability delta [95% CI] |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report.get("reviewers") or []:
        preference = row.get("evidence_preference") or {}
        delta = (row.get("paired_deltas") or {}).get("repair_actionable") or {}
        lines.append(
            "| %s | %s | %s/%s | %s | %s | %s | %s | %s | %s |"
            % (
                row.get("reviewer"),
                row.get("review_kind"),
                row.get("completed_cases"),
                row.get("case_count"),
                row.get("evidence_wins"),
                row.get("core_wins"),
                row.get("ties"),
                _interval(preference),
                _p_value(row.get("exact_binomial_p")),
                _interval(delta),
            )
        )
    lines.extend(
        [
            "",
            "Pairwise preference disagreements requiring inspection: `%s`." % report.get("disagreement_cases"),
            "",
            str(report.get("inference_note") or ""),
            "",
        ]
    )
    return "\n".join(lines)


def load_actionability_spec(path: str | Path = DEFAULT_SPEC_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    config = payload.get("actionability") if isinstance(payload, dict) else None
    if not isinstance(config, dict):
        raise ValueError("ARR experiment spec must define actionability configuration.")
    required_positive = (
        "sample_size",
        "quick_sample_size",
        "minimum_independent_reviewers",
        "seed",
        "bootstrap_samples",
    )
    for key in required_positive:
        if int(config.get(key) or 0) <= 0:
            raise ValueError("Actionability configuration %s must be positive." % key)
    if int(config["quick_sample_size"]) > int(config["sample_size"]):
        raise ValueError("quick_sample_size cannot exceed sample_size.")
    return dict(config)


def _evidence_chain_output(result: dict[str, Any]) -> dict[str, Any]:
    claims = []
    for claim in result.get("claims") or []:
        root = claim.get("root_cause") if isinstance(claim.get("root_cause"), dict) else {}
        span = claim.get("evidence_span") if isinstance(claim.get("evidence_span"), dict) else None
        claims.append(
            {
                "claim": claim.get("claim"),
                "verdict": claim.get("verdict"),
                "confidence": claim.get("confidence"),
                "citation_status": claim.get("citation_status"),
                "evidence_span": (
                    {
                        "context_id": span.get("context_id"),
                        "text": span.get("text"),
                    }
                    if span
                    else None
                ),
                "root_cause": root.get("label"),
                "reason": root.get("reason") or claim.get("reason"),
                "suggested_fix": root.get("suggested_fix"),
            }
        )
    summary = result.get("summary") or {}
    return {
        "overall": {
            "failure_types": summary.get("failure_types") or [],
            "primary_root_cause": summary.get("primary_root_cause"),
            "should_abstain": (result.get("abstention") or {}).get("should_abstain"),
            "suggested_fix": summary.get("suggested_fix"),
        },
        "claims": claims,
    }


def _semantic_core_output(result: dict[str, Any]) -> dict[str, Any]:
    summary = result.get("summary") or {}
    return {
        "overall": {
            "support_score": summary.get("support_rate"),
            "unsupported_claim_rate": summary.get("unsupported_claim_rate"),
            "claim_counts": {
                key: summary.get(key)
                for key in ("supported", "partially_supported", "unsupported", "contradicted", "unverifiable")
            },
        },
        "claims": [
            {
                "claim": claim.get("claim"),
                "verdict": claim.get("verdict"),
                "confidence": claim.get("confidence"),
            }
            for claim in result.get("claims") or []
        ],
    }


def _review_template() -> dict[str, Any]:
    rating = {
        "diagnosis_correct": None,
        "repair_actionable": None,
        "repair_specificity": None,
        "evidence_sufficiency": None,
    }
    return {
        "option_1": dict(rating),
        "option_2": dict(rating),
        "preferred_option": "",
        "decision_time_seconds": None,
        "confidence": None,
        "rationale": "",
    }


def _public_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(context.get("id") or ""),
        "text": str(context.get("text") or ""),
        "metadata": {
            key: value
            for key, value in dict(context.get("metadata") or {}).items()
            if key in SAFE_CONTEXT_METADATA
        },
    }


def _nested_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(value)
        for item in value.values():
            keys.update(_nested_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_nested_keys(item))
    return keys


def _is_failure_case(record: dict[str, Any]) -> bool:
    labels = set((record.get("expected") or {}).get("expected_labels") or [])
    return bool(labels) and labels != {"no_failure_detected"}


def _stratified_sample(records: list[dict[str, Any]], *, sample_size: int, seed: int) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        root = str((record.get("expected") or {}).get("expected_primary_root_cause") or "unknown")
        groups[root].append(record)
    rng = random.Random(seed)
    for rows in groups.values():
        rng.shuffle(rows)
    selected: list[dict[str, Any]] = []
    keys = sorted(groups)
    while len(selected) < min(sample_size, len(records)):
        progressed = False
        for key in keys:
            if groups[key] and len(selected) < sample_size:
                selected.append(groups[key].pop())
                progressed = True
        if not progressed:
            break
    return selected


def _load_response(path: str | Path, key_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    reviewer = str(payload.get("reviewer") or "").strip()
    kind = str(payload.get("review_kind") or "").strip()
    if not reviewer:
        raise ValueError("Actionability response must name a reviewer.")
    if kind not in REVIEW_KINDS:
        raise ValueError("review_kind must be independent or pilot_author.")
    cases: dict[str, dict[str, Any]] = {}
    for item in payload.get("cases") or []:
        blind_id = str(item.get("blind_id") or "")
        if blind_id not in key_index:
            raise ValueError("Unknown actionability blind ID: %s" % blind_id)
        if blind_id in cases:
            raise ValueError("Repeated actionability blind ID: %s" % blind_id)
        cases[blind_id] = dict(item.get("review") or {})
    return {"reviewer": reviewer, "review_kind": kind, "cases": cases, "path": str(path)}


def _score_reviewer(
    reviewer: dict[str, Any],
    key_index: dict[str, dict[str, Any]],
    *,
    bootstrap_samples: int,
    bootstrap_seed: int,
) -> dict[str, Any]:
    completed = []
    for blind_id, key in key_index.items():
        review = reviewer["cases"].get(blind_id) or {}
        if not _review_complete(review):
            continue
        mapping = key["condition_by_option"]
        preference = str(review.get("preferred_option"))
        preferred_condition = mapping.get(preference, preference)
        evidence_option = _option_for_condition(mapping, CONDITION_EVIDENCE)
        core_option = _option_for_condition(mapping, CONDITION_CORE)
        completed.append(
            {
                "blind_id": blind_id,
                "preferred_condition": preferred_condition,
                "evidence_position": evidence_option,
                CONDITION_EVIDENCE: dict(review[evidence_option]),
                CONDITION_CORE: dict(review[core_option]),
                "decision_time_seconds": float(review["decision_time_seconds"]),
                "confidence": int(review["confidence"]),
            }
        )
    evidence_wins = sum(row["preferred_condition"] == CONDITION_EVIDENCE for row in completed)
    core_wins = sum(row["preferred_condition"] == CONDITION_CORE for row in completed)
    ties = sum(row["preferred_condition"] == "tie" for row in completed)
    neither = sum(row["preferred_condition"] == "neither" for row in completed)
    decisive = evidence_wins + core_wins
    deltas = {
        metric: _paired_delta(
            completed,
            metric,
            samples=bootstrap_samples,
            seed=bootstrap_seed + index,
        )
        for index, metric in enumerate(
            ("diagnosis_correct", "repair_actionable", "repair_specificity", "evidence_sufficiency")
        )
    }
    return {
        "reviewer": reviewer["reviewer"],
        "review_kind": reviewer["review_kind"],
        "case_count": len(key_index),
        "completed_cases": len(completed),
        "evidence_wins": evidence_wins,
        "core_wins": core_wins,
        "ties": ties,
        "neither": neither,
        "decisive_preferences": decisive,
        "evidence_preference": _wilson(evidence_wins, decisive),
        "exact_binomial_p": _exact_binomial_two_sided(evidence_wins, decisive),
        "condition_means": {
            condition: {
                metric: _average(_numeric(row[condition].get(metric)) for row in completed)
                for metric in ("diagnosis_correct", "repair_actionable", "repair_specificity", "evidence_sufficiency")
            }
            for condition in (CONDITION_EVIDENCE, CONDITION_CORE)
        },
        "paired_deltas": deltas,
        "mean_decision_time_seconds": _average(row["decision_time_seconds"] for row in completed),
        "mean_confidence": _average(row["confidence"] for row in completed),
        "order_breakdown": {
            option: {
                "cases": sum(row["evidence_position"] == option for row in completed),
                "evidence_wins": sum(
                    row["evidence_position"] == option and row["preferred_condition"] == CONDITION_EVIDENCE
                    for row in completed
                ),
            }
            for option in OPTION_NAMES
        },
    }


def _review_complete(review: dict[str, Any]) -> bool:
    if str(review.get("preferred_option") or "") not in PREFERENCE_VALUES:
        return False
    if not _rating_complete(review.get("option_1")) or not _rating_complete(review.get("option_2")):
        return False
    return _scale(review.get("confidence")) is not None and _positive_number(review.get("decision_time_seconds"))


def _rating_complete(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if not isinstance(value.get("diagnosis_correct"), bool) or not isinstance(value.get("repair_actionable"), bool):
        return False
    return _scale(value.get("repair_specificity")) is not None and _scale(value.get("evidence_sufficiency")) is not None


def _paired_delta(rows: list[dict[str, Any]], metric: str, *, samples: int, seed: int) -> dict[str, Any]:
    values = [
        _numeric(row[CONDITION_EVIDENCE].get(metric))
        - _numeric(row[CONDITION_CORE].get(metric))
        for row in rows
    ]
    if not values:
        return {"estimate": None, "low": None, "high": None, "cases": 0, "samples": samples}
    estimate = sum(values) / len(values)
    rng = random.Random(seed)
    boot = [
        sum(values[rng.randrange(len(values))] for _ in values) / len(values)
        for _ in range(samples)
    ]
    boot.sort()
    return {
        "estimate": round(estimate, 3),
        "low": round(_percentile(boot, 2.5), 3),
        "high": round(_percentile(boot, 97.5), 3),
        "cases": len(values),
        "samples": samples,
        "seed": seed,
    }


def _wilson(successes: int, total: int) -> dict[str, Any]:
    if total <= 0:
        return {"estimate": None, "low": None, "high": None, "decisive": 0}
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return {
        "estimate": round(proportion, 3),
        "low": round(max(0.0, center - margin), 3),
        "high": round(min(1.0, center + margin), 3),
        "decisive": total,
    }


def _exact_binomial_two_sided(successes: int, total: int) -> float | None:
    if total <= 0:
        return None
    observed_probability = math.comb(total, successes) * (0.5 ** total)
    probability = sum(
        math.comb(total, value) * (0.5 ** total)
        for value in range(total + 1)
        if math.comb(total, value) * (0.5 ** total) <= observed_probability + 1e-15
    )
    return min(1.0, probability)


def _pairwise_agreement(
    left: dict[str, Any],
    right: dict[str, Any],
    key_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    shared = []
    for blind_id in sorted(set(left["cases"]).intersection(right["cases"])):
        left_review = left["cases"][blind_id]
        right_review = right["cases"][blind_id]
        if not _review_complete(left_review) or not _review_complete(right_review):
            continue
        mapping = key_index[blind_id]["condition_by_option"]
        shared.append(
            (
                mapping.get(left_review["preferred_option"], left_review["preferred_option"]),
                mapping.get(right_review["preferred_option"], right_review["preferred_option"]),
            )
        )
    return {
        "reviewer_a": left["reviewer"],
        "reviewer_b": right["reviewer"],
        "shared_completed_cases": len(shared),
        "preference_exact_agreement": _average(a == b for a, b in shared),
    }


def _disagreements(reviewers: list[dict[str, Any]], key_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for blind_id, key in key_index.items():
        preferences = []
        for reviewer in reviewers:
            review = reviewer["cases"].get(blind_id) or {}
            if not _review_complete(review):
                continue
            raw = review["preferred_option"]
            preferences.append(
                {
                    "reviewer": reviewer["reviewer"],
                    "preference": key["condition_by_option"].get(raw, raw),
                    "rationale": review.get("rationale"),
                }
            )
        if len({row["preference"] for row in preferences}) > 1:
            rows.append({"blind_id": blind_id, "original_id": key.get("original_id"), "preferences": preferences})
    return rows


def _option_for_condition(mapping: dict[str, str], condition: str) -> str:
    return next(option for option, value in mapping.items() if value == condition)


def _scale(value: Any) -> int | None:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None
    return numeric if 1 <= numeric <= 5 else None


def _positive_number(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _numeric(value: Any) -> float:
    return float(int(value)) if isinstance(value, bool) else float(value)


def _average(values: Any) -> float | None:
    items = [float(value) for value in values]
    return round(sum(items) / len(items), 3) if items else None


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    position = (len(values) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower
    return values[lower] * (1 - fraction) + values[upper] * fraction


def _interval(value: dict[str, Any]) -> str:
    if value.get("estimate") is None:
        return "N/A"
    return "%s [%s, %s]" % (_metric(value.get("estimate")), _metric(value.get("low")), _metric(value.get("high")))


def _metric(value: Any) -> str:
    return "N/A" if value is None else "%.3f" % float(value)


def _p_value(value: Any) -> str:
    if value is None:
        return "N/A"
    numeric = float(value)
    return "<0.001" if numeric < 0.001 else "%.3f" % numeric


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


def _dataset_name(*, case_set: str, case_pack_path: str | Path | None) -> str:
    if not case_pack_path:
        return case_set
    payload = json.loads(Path(case_pack_path).read_text(encoding="utf-8-sig"))
    return str(payload.get("dataset") or Path(case_pack_path).stem)


def _git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and score the blinded ARR actionability study.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    build.add_argument("--spec", default=str(DEFAULT_SPEC_PATH))
    build.add_argument("--case-set", default=None, choices=["contexttrace", "external", "public_holdout", "all"])
    build.add_argument("--case-pack", default=None)
    build.add_argument("--seed", type=int, default=None)
    build.add_argument("--sample-size", type=int, default=None)
    build.add_argument("--quick", action="store_true")
    score = subparsers.add_parser("score")
    score.add_argument("--key", required=True)
    score.add_argument("--responses", nargs="+", required=True)
    score.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    score.add_argument("--bootstrap-samples", type=int, default=None)
    score.add_argument("--bootstrap-seed", type=int, default=None)
    args = parser.parse_args(argv)
    if args.command == "build":
        paths = build_actionability_artifacts(
            output_dir=args.output_dir,
            spec_path=args.spec,
            case_set=args.case_set,
            case_pack_path=args.case_pack,
            seed=args.seed,
            sample_size=args.sample_size,
            quick=args.quick,
        )
        print("Packet: %s" % paths["packet"])
        print("Private key: %s" % paths["private_key"])
        print("Validation: %s" % paths["validation"])
        return 0
    result = score_actionability_responses(
        key_path=args.key,
        response_paths=args.responses,
        output_dir=args.output_dir,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_seed=args.bootstrap_seed,
    )
    print("Reviewers: %s" % len(result["reviewers"]))
    print("Disagreements: %s" % result["disagreement_cases"])
    print("Report: %s" % result["outputs"]["report"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
