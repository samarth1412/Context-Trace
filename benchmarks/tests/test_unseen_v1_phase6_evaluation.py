from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.contexttrace_unseen_v1.evaluation.candidate_runner import (
    _source_index,
    prepare_trace,
)
from benchmarks.contexttrace_unseen_v1.evaluation.integrity import (
    EvaluationIntegrityError,
    canonical_sha256,
    require_execution_authorization,
    verify_phase6_locks,
)
from benchmarks.contexttrace_unseen_v1.evaluation.scoring import (
    aggregate_metrics,
    align_claims,
    dangerous_false_green,
    equal_mass_ece,
    evidence_scores,
    maximum_weight_pairs,
    risk_coverage,
)
from benchmarks.contexttrace_unseen_v1.evaluation.sealed_scorer import score_sealed
from benchmarks.contexttrace_unseen_v1.evaluation.statistics import (
    hierarchical_cluster_bootstrap,
    holm_adjust,
    paired_cluster_randomization,
)
from benchmarks.contexttrace_unseen_v1.evaluation.v1_mapping import (
    map_v1_claim,
    map_v1_output,
)


ROOT = Path(__file__).resolve().parents[2]


def _gold(
    *,
    verdict: str = "supported",
    failure: str = "none",
    root: str = "none",
    citation: str = "correct",
    source: str = "current_canonical",
    abstention: str = "must_answer",
    spans: list[dict] | None = None,
) -> dict:
    return {
        "claim_id": "gold-1",
        "claim_text": "Alpha is enabled",
        "answer_start": 0,
        "answer_end": 16,
        "propositional": True,
        "claim_verdict": verdict,
        "failure_label": failure,
        "primary_root_cause": root,
        "citation_state": citation,
        "source_condition": source,
        "abstention_requirement": abstention,
        "evidence_spans": spans or [],
    }


def _prediction(**overrides: object) -> dict:
    value = {
        "claim_id": "claim_1",
        "text": "Alpha is enabled",
        "start_char": 0,
        "end_char": 16,
        "claim_verdict": "supported",
        "failure_label": "none",
        "primary_root_cause": "none",
        "citation_state": "correct",
        "source_condition": "current_canonical",
        "abstention_requirement": "must_answer",
        "diagnostic_abstention": False,
        "diagnostic_confidence": 0.95,
        "route": "deterministic",
        "green": True,
        "qualification_required": False,
        "evidence_spans": [],
    }
    value.update(overrides)
    return value


def _row(
    gold: dict,
    prediction: dict | None,
    *,
    case_id: str = "case-1",
    family: str = "family-1",
    track: str = "natural_ood",
    domain: str = "policy_regulatory",
) -> dict:
    return {
        "case_id": case_id,
        "source_family": family,
        "track": track,
        "domain": domain,
        "gold": gold,
        "prediction": prediction,
        "context_sources": {"chunk-1": "source-1", "chunk-2": "source-2"},
    }


def test_current_phase6_locks_and_implementation_sources_verify():
    locks = verify_phase6_locks(ROOT)

    assert locks["evaluation"]["dataset"]["case_count"] == 493
    assert locks["evaluation"]["execution"]["one_time_sealed_run"] is True


def test_execution_authorization_is_exact_and_fail_closed(tmp_path: Path):
    locks = verify_phase6_locks(ROOT)
    config = locks["evaluation"]
    ablations = locks["ablations"]
    authorization = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_cain2027_phase6_execution_authorization",
        "authorized": True,
        "one_time_sealed_run": True,
        "dataset_id": config["dataset"]["id"],
        "manifest_payload_sha256": config["dataset"]["frozen_manifest_payload_sha256"],
        "case_count": config["dataset"]["case_count"],
        "implementation_source_manifest_sha256": config["candidate_system"][
            "implementation_source_manifest_sha256"
        ],
        "candidate_profile_sha256": config["candidate_system"]["profile_sha256"],
        "ablation_config_payload_sha256": ablations["payload_sha256"],
        "source_manifest_file_sha256": locks["dataset_freeze"]["artifact_chain"][
            "combined_source_manifest_file_sha256"
        ],
    }
    authorization["payload_sha256"] = canonical_sha256(authorization)
    path = tmp_path / "authorization.json"
    path.write_text(json.dumps(authorization), encoding="utf-8")

    assert (
        require_execution_authorization(
            path,
            config,
            ablations,
            expected_source_manifest_sha256=locks["dataset_freeze"]["artifact_chain"][
                "combined_source_manifest_file_sha256"
            ],
        )["authorized"]
        is True
    )
    authorization["case_count"] = 492
    path.write_text(json.dumps(authorization), encoding="utf-8")
    with pytest.raises(EvaluationIntegrityError, match="case_count"):
        require_execution_authorization(
            path,
            config,
            ablations,
            expected_source_manifest_sha256=locks["dataset_freeze"]["artifact_chain"][
                "combined_source_manifest_file_sha256"
            ],
        )


def test_candidate_adapter_preserves_source_and_citation_observables():
    source_manifest = {
        "sources": [
            {
                "source_id": "source-1",
                "snapshot_sha256": "a" * 64,
                "published_at": "2024-01-01T00:00:00Z",
                "authority_basis": "Official archive.",
                "source_url": "https://example.test/alpha",
                "source_conditions": ["archived", "canonical"],
            }
        ]
    }
    candidate = {
        "dataset_id": "ContextTrace-Unseen-v1",
        "case_id": "case-1",
        "track": "temporal_source_condition",
        "candidate_input_sha256": "b" * 64,
        "query": "Is alpha enabled?",
        "answer": "Alpha is enabled [source-1].",
        "selected_contexts": [
            {
                "chunk_id": "chunk-1",
                "source_id": "source-1",
                "text": "Alpha is enabled.",
            }
        ],
    }
    trace = prepare_trace(
        candidate,
        _source_index(source_manifest),
        case={
            "citation_format": "source_id",
            "retrieval": {"family": "hybrid"},
            "reranking": {"enabled": True},
            "chunking": {"size": 512},
        },
    )

    assert trace.contexts[0].metadata["source_condition"] == "stale"
    assert trace.citations[0].source_id == "chunk-1"
    assert trace.metadata["citation_required"] is True
    assert trace.metadata["reranking_enabled"] is True


def test_candidate_adapter_resolves_numeric_and_url_citations():
    source_manifest = {
        "sources": [
            {
                "source_id": "source-1",
                "snapshot_sha256": "a" * 64,
                "published_at": "2026-01-01T00:00:00Z",
                "authority_basis": "Official.",
                "source_url": "https://example.test/alpha",
                "source_conditions": ["current", "canonical"],
            }
        ]
    }
    base = {
        "dataset_id": "ContextTrace-Unseen-v1",
        "case_id": "case-1",
        "track": "natural_ood",
        "candidate_input_sha256": "b" * 64,
        "query": "Alpha?",
        "selected_contexts": [
            {
                "chunk_id": "chunk-1",
                "source_id": "source-1",
                "text": "Alpha.",
            }
        ],
    }
    numeric = prepare_trace(
        {**base, "answer": "Alpha [1]."},
        _source_index(source_manifest),
        case={"citation_format": "inline_numeric"},
    )
    url = prepare_trace(
        {**base, "answer": "Alpha https://example.test/alpha."},
        _source_index(source_manifest),
        case={"citation_format": "url"},
    )

    assert numeric.citations[0].source_id == "chunk-1"
    assert url.citations[0].source_id == "chunk-1"


@pytest.mark.parametrize(
    ("v1_root", "mapped"),
    [
        ("no_failure_detected", "none"),
        ("partial_context_support", "insufficient_selected_context"),
        ("wrong_source_cited", "citation_mismatch"),
        ("stale_context", "stale_or_superseded_source"),
        ("not-a-real-label", "not_observable"),
    ],
)
def test_v1_root_mapping_is_frozen(v1_root: str, mapped: str):
    result = map_v1_claim(
        {
            "claim_id": "claim_1",
            "claim": "Alpha is enabled.",
            "verdict": "supported",
            "citation_status": "citation_ok",
            "source_status": "grounded_by_current_canonical_source",
            "root_cause": {"label": v1_root},
        }
    )

    assert result["primary_root_cause"] == mapped


def test_v1_claim_offsets_are_recovered_without_reusing_prior_text():
    output = {
        "case_id": "case-1",
        "raw_output": {
            "answer": "Alpha works. Alpha works.",
            "abstention": {"should_abstain": False},
            "claims": [
                {
                    "claim_id": "claim_1",
                    "claim": "Alpha works.",
                    "verdict": "supported",
                    "root_cause": {"label": "no_failure_detected"},
                },
                {
                    "claim_id": "claim_2",
                    "claim": "Alpha works.",
                    "verdict": "supported",
                    "root_cause": {"label": "no_failure_detected"},
                },
            ],
        },
    }

    mapped = map_v1_output(output)

    assert [(row["start_char"], row["end_char"]) for row in mapped["claims"]] == [
        (0, 12),
        (13, 25),
    ]


def test_maximum_weight_matching_uses_global_not_greedy_optimum():
    assert maximum_weight_pairs([[9, 8], [8, 0]]) == [(0, 1), (1, 0)]


def test_claim_alignment_is_one_to_one_and_reports_spurious_predictions():
    gold = [
        {**_gold(), "claim_id": "g1", "answer_start": 0, "answer_end": 10},
        {**_gold(), "claim_id": "g2", "answer_start": 10, "answer_end": 20},
    ]
    predictions = [
        _prediction(start_char=0, end_char=20),
        _prediction(start_char=30, end_char=40),
    ]

    aligned, spurious = align_claims(gold, predictions)

    assert sum(prediction is not None for _, prediction in aligned) == 1
    assert spurious == [1]


def test_invalid_output_is_conservative_and_absent_classes_are_na():
    rows = [
        _row(_gold(), _prediction()),
        _row(
            _gold(
                verdict="unsupported",
                failure="answer_overreach",
                root="answer_overreach",
                abstention="must_abstain",
            ),
            None,
            case_id="case-2",
        ),
    ]

    metrics = aggregate_metrics(rows, green_threshold=0.9, ece_bins=15)

    assert metrics["failure_label"]["per_class"]["answer_overreach"]["fn"] == 1
    assert metrics["failure_label"]["per_class"]["contradiction"]["f1"] is None
    assert metrics["availability"] == {
        "valid_predictions": 1,
        "requested_predictions": 2,
    }


def test_dangerous_false_green_requires_every_green_condition():
    dangerous = _gold(
        verdict="unsupported",
        failure="answer_overreach",
        root="answer_overreach",
        abstention="must_abstain",
    )
    rows = [
        _row(dangerous, _prediction(), case_id="case-1"),
        _row(
            dangerous,
            _prediction(qualification_required=True),
            case_id="case-2",
        ),
        _row(dangerous, None, case_id="case-3"),
    ]

    result = dangerous_false_green(rows, threshold=0.9)

    assert result["claim_numerator"] == 1
    assert result["claim_denominator"] == 3
    assert result["trace_numerator"] == 1


def test_multi_span_evidence_requires_matching_source_ids():
    gold = _gold(
        spans=[
            {
                "source_id": "source-1",
                "source_snapshot_id": "snap-1",
                "chunk_id": "chunk-1",
                "start": 0,
                "end": 5,
                "text": "alpha",
                "role": "supporting",
            },
            {
                "source_id": "source-2",
                "source_snapshot_id": "snap-2",
                "chunk_id": "chunk-2",
                "start": 10,
                "end": 14,
                "text": "beta",
                "role": "supporting",
            },
        ]
    )
    prediction = _prediction(
        evidence_spans=[
            {
                "context_id": "chunk-1",
                "start_char": 0,
                "end_char": 5,
                "text": "alpha",
            },
            {
                "context_id": "wrong-chunk",
                "start_char": 10,
                "end_char": 14,
                "text": "beta",
            },
        ]
    )

    score = evidence_scores(
        gold,
        prediction,
        context_sources={
            "chunk-1": "source-1",
            "chunk-2": "source-2",
            "wrong-chunk": "source-3",
        },
    )

    assert score is not None
    assert score["token_f1"] == pytest.approx(0.5)
    assert score["character_iou"] == pytest.approx(5 / 13)
    assert score["wrong_source_spans"] == 1


def test_calibration_and_risk_keep_confidence_ties_together():
    calibration = equal_mass_ece(
        [(0.2, False), (0.8, True), (0.8, False), (0.8, True)],
        bins=3,
    )
    risk = risk_coverage([(0.9, True, False), (0.9, False, False), (0.2, True, False)])

    assert [row["count"] for row in calibration["bins"]] == [1, 3]
    assert risk["curve"][0]["coverage"] == pytest.approx(2 / 3)
    assert risk["curve"][0]["risk"] == 0.5


def test_cluster_bootstrap_and_randomization_are_reproducible():
    rows = [
        {
            **_row(
                _gold(),
                _prediction(),
                case_id=f"case-{index}",
                family=f"family-{index % 2}",
            ),
            "value": float(index),
            "candidate_prediction": _prediction(),
            "predecessor_prediction": _prediction(failure_label="answer_overreach"),
        }
        for index in range(6)
    ]

    def estimator(sample):
        return sum(float(row["value"]) for row in sample) / len(sample)

    first = hierarchical_cluster_bootstrap(
        rows, estimator, replicates=50, seed=20271030
    )
    second = hierarchical_cluster_bootstrap(
        rows, estimator, replicates=50, seed=20271030
    )

    def difference(left, right):
        return sum(row["prediction"]["failure_label"] == "none" for row in left) - sum(
            row["prediction"]["failure_label"] == "none" for row in right
        )

    random_first = paired_cluster_randomization(
        rows, difference, replicates=50, seed=20271030
    )
    random_second = paired_cluster_randomization(
        rows, difference, replicates=50, seed=20271030
    )

    assert first == second
    assert random_first == random_second
    assert holm_adjust({"a": 0.01, "b": 0.04, "c": None}) == {
        "a": 0.02,
        "b": 0.04,
        "c": None,
    }


def test_sealed_scorer_refuses_to_open_files_without_custodian_confirmation(
    tmp_path: Path,
):
    with pytest.raises(EvaluationIntegrityError, match="confirmation"):
        score_sealed(
            repository_root=ROOT,
            manifest_path=tmp_path / "manifest.json",
            artifact_root=tmp_path,
            candidate_run_path=tmp_path / "candidate.json",
            candidate_run_sha256="a" * 64,
            v1_run_path=tmp_path / "v1.json",
            v1_run_sha256="b" * 64,
            gold_path=tmp_path / "gold.json",
            gold_sha256="c" * 64,
            output_directory=tmp_path / "output",
            confirmation="not-the-custodian-confirmation",
        )
