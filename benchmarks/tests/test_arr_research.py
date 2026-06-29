from __future__ import annotations

import json
from pathlib import Path

from benchmarks.contexttrace_bench.arr_ablation import (
    load_experiment_spec,
    reported_summary,
    run_arr_ablations,
)
from benchmarks.contexttrace_bench.arr_annotation import (
    build_blinded_annotation_artifacts,
    score_annotation_files,
    validate_blinded_packet,
)


def test_frozen_ablation_profiles_are_unique_and_cumulative():
    profiles = load_experiment_spec()["ablation"]["profiles"]

    assert [profile["id"] for profile in profiles] == [
        "a0_lexical_core",
        "a1_semantic_core",
        "a2_citation_alignment",
        "a3_diagnostic_inference",
        "a4_span_localization",
        "a5_full",
    ]
    enabled = [
        {
            key
            for key in (
                "citation_alignment",
                "abstention_logic",
                "source_assessment",
                "root_cause_inference",
                "evidence_span_localization",
            )
            if profile[key]
        }
        for profile in profiles
    ]
    assert all(left <= right for left, right in zip(enabled, enabled[1:]))


def test_reported_summary_masks_outputs_disabled_by_profile():
    summary = {
        "citation_error_precision": 1.0,
        "citation_error_recall": 1.0,
        "citation_error_f1": 1.0,
        "root_cause_accuracy": 1.0,
        "evidence_span_overlap": 1.0,
    }
    profile = load_experiment_spec()["ablation"]["profiles"][0]

    reported = reported_summary(summary, profile)

    assert reported["citation_error_f1"] is None
    assert reported["root_cause_accuracy"] is None
    assert reported["evidence_span_overlap"] is None


def test_quick_ablation_run_uses_identical_cases_and_is_not_paper_eligible(tmp_path):
    result = run_arr_ablations(
        output_dir=tmp_path,
        case_set="contexttrace",
        quick=True,
    )

    assert result["paper_result_eligible"] is False
    assert result["bootstrap_samples"] == 50
    assert result["case_count"] > 0
    assert len(result["profiles"]) == 6
    assert len(result["case_ids_sha256"]) == 64
    assert result["profiles"][0]["reported_summary"]["citation_error_f1"] is None
    assert result["profiles"][-1]["reported_summary"]["citation_error_f1"] is not None
    assert (tmp_path / "ablation_results.json").is_file()
    assert "Quick runs validate the harness" in (tmp_path / "ablation_table.md").read_text(
        encoding="utf-8"
    )


def test_blinded_packet_is_deterministic_and_contains_no_labels(tmp_path):
    first = build_blinded_annotation_artifacts(
        output_dir=tmp_path / "first",
        case_set="contexttrace",
        seed=17,
    )
    second = build_blinded_annotation_artifacts(
        output_dir=tmp_path / "second",
        case_set="contexttrace",
        seed=17,
    )
    packet = _read(first["packet"])
    second_packet = _read(second["packet"])
    private_key = _read(first["private_key"])

    assert validate_blinded_packet(packet)["status"] == "passed"
    assert [case["blind_id"] for case in packet["cases"]] == [
        case["blind_id"] for case in second_packet["cases"]
    ]
    assert [case["original_id"] for case in private_key["cases"]] == [
        case["original_id"] for case in _read(second["private_key"])["cases"]
    ]
    public_text = json.dumps(packet)
    assert "expected_labels" not in public_text
    assert "original_id" not in public_text
    assert "diagnosis_correct" not in public_text
    assert all(case["blind_id"].startswith("ARR-") for case in packet["cases"])


def test_annotation_scoring_reports_pairwise_agreement(tmp_path):
    key_path = tmp_path / "key.json"
    key_path.write_text(
        json.dumps(
            {
                "dataset": "fixture",
                "cases": [
                    {
                        "blind_id": "ARR-0001",
                        "original_id": "case-1",
                        "expected_labels": ["no_failure_detected"],
                        "expected_primary_root_cause": "no_failure_detected",
                        "expected_should_abstain": False,
                        "expected_evidence_spans": [{"text": "refunds within 30 days"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    annotation = {
        "review_kind": "independent",
        "cases": [
            {
                "blind_id": "ARR-0001",
                "annotation": {
                    "failure_labels": ["no_failure_detected"],
                    "primary_root_cause": "no_failure_detected",
                    "should_abstain": False,
                    "evidence_spans": [{"text": "refunds within 30 days"}],
                },
            }
        ],
    }
    paths = []
    for reviewer in ("reviewer-a", "reviewer-b"):
        path = tmp_path / (reviewer + ".json")
        path.write_text(json.dumps({**annotation, "reviewer": reviewer}), encoding="utf-8")
        paths.append(path)

    report = score_annotation_files(
        key_path=key_path,
        annotation_paths=paths,
        output_dir=tmp_path / "scored",
    )

    assert report["reviewers"][0]["failure_label_exact_match"] == 1.0
    assert report["pairwise_agreement"][0]["primary_root_cause_kappa"] == 1.0
    assert report["disagreement_cases"] == 0
    assert Path(report["outputs"]["report"]).is_file()


def _read(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
