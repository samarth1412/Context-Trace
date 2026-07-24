from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from benchmarks.contexttrace_unseen_v1.AGREEMENT_ANALYSIS import (
    AgreementError,
    analyze_agreement,
    cohen_kappa,
    evidence_character_iou,
    evidence_token_f1,
    krippendorff_alpha_nominal,
    load_json,
    main,
    render_markdown,
    validate_annotation,
)


HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "contexttrace_unseen_v1"
    / "ANNOTATION_SCHEMA.json"
)


def _confidence() -> dict:
    return {
        "claim_boundary": 4,
        "claim_verdict": 4,
        "failure_label": 4,
        "primary_root_cause": 4,
        "citation_state": 4,
        "source_condition": 4,
        "abstention_requirement": 4,
        "evidence_spans": 4,
        "overall": 4,
    }


def _span(
    *,
    source_id: str = "source-1",
    start: int = 0,
    end: int = 10,
    text: str = "Feature on",
    role: str = "supporting",
) -> dict:
    return {
        "source_id": source_id,
        "source_snapshot_id": "snapshot-1",
        "chunk_id": "chunk-1",
        "start": start,
        "end": end,
        "text": text,
        "role": role,
    }


def _claim(
    claim_id: str,
    *,
    start: int,
    end: int,
    verdict: str,
    failure: str,
    root: str,
    citation: str,
    abstention: str,
    evidence: list[dict],
) -> dict:
    return {
        "claim_id": claim_id,
        "claim_text": f"Claim {claim_id}",
        "answer_start": start,
        "answer_end": end,
        "propositional": True,
        "claim_verdict": verdict,
        "failure_label": failure,
        "secondary_failure_labels": [],
        "primary_root_cause": root,
        "secondary_root_causes": [],
        "citation_state": citation,
        "source_condition": "current_canonical",
        "source_condition_basis": {
            "snapshot_ids": ["snapshot-1"],
            "effective_dates": ["2026-07-01T00:00:00+00:00"],
            "authority_rule": "Official source.",
            "rationale": "The official current snapshot applies.",
        },
        "abstention_requirement": abstention,
        "evidence_spans": evidence,
        "ambiguity_flags": [],
        "field_confidence": _confidence(),
        "rationale": "The supplied evidence determines the annotation.",
        "notes": "",
    }


def _document(annotator_id: str) -> dict:
    claims = [
        _claim(
            "claim-1",
            start=0,
            end=10,
            verdict="supported",
            failure="none",
            root="none",
            citation="correct",
            abstention="must_answer",
            evidence=[_span()],
        ),
        _claim(
            "claim-2",
            start=11,
            end=20,
            verdict="unsupported",
            failure="answer_overreach",
            root="answer_overreach",
            citation="missing",
            abstention="must_abstain",
            evidence=[],
        ),
    ]
    return {
        "schema_version": "1.0",
        "document_kind": "independent_annotation",
        "dataset_id": "ContextTrace-Unseen-v1",
        "manifest_sha256": HASH_A,
        "guide_version": "1.0",
        "claim_policy_version": "1.0",
        "created_at": "2026-08-20T12:00:00+00:00",
        "annotator_id": annotator_id,
        "assignment_id": f"assignment-{annotator_id}",
        "assignment_sha256": HASH_B,
        "independence_attestation": {
            "worked_independently": True,
            "no_system_predictions_seen": True,
            "no_other_annotations_seen": True,
            "all_assistance_disclosed": True,
            "signed_at": "2026-08-20T12:00:00+00:00",
        },
        "model_assistance": {"used": False},
        "cases": [
            {
                "case_id": "blind-case-1",
                "answer_sha256": HASH_B,
                "claims": claims,
                "completed_at": "2026-08-20T11:00:00+00:00",
                "case_notes": "",
            }
        ],
    }


def test_annotation_schema_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(load_json(SCHEMA_PATH))


def test_independent_annotation_fixture_validates():
    validate_annotation(_document("annotator-a"))


def test_schema_validates_adjudication_ledger_and_sealed_gold():
    validator = Draft202012Validator(
        load_json(SCHEMA_PATH),
        format_checker=FormatChecker(),
    )
    common = {
        "schema_version": "1.0",
        "dataset_id": "ContextTrace-Unseen-v1",
        "manifest_sha256": HASH_A,
        "guide_version": "1.0",
        "claim_policy_version": "1.0",
        "created_at": "2026-08-21T12:00:00+00:00",
    }
    ledger = {
        **common,
        "document_kind": "adjudication_ledger",
        "ledger_id": "ledger-1",
        "events": [
            {
                "event_id": "event-1",
                "case_id": "blind-case-1",
                "claim_id": "claim-1",
                "field": "claim_verdict",
                "annotator_values": [
                    {"annotator_id": "annotator-a", "value": "supported"},
                    {"annotator_id": "annotator-b", "value": "unsupported"},
                ],
                "selected_value": "supported",
                "disagreement_type": "evidentiary",
                "evidence_considered": ["source-1:0-10"],
                "rationale": "The complete relation is directly stated.",
                "adjudicator_id": "adjudicator-a",
                "adjudicated_at": "2026-08-21T11:00:00+00:00",
                "source_annotation_sha256s": [HASH_A, HASH_B],
            }
        ],
    }
    gold = {
        **common,
        "document_kind": "sealed_gold",
        "gold_version": "1.0",
        "raw_annotation_sha256s": [HASH_A, HASH_B],
        "adjudication_ledger_sha256": HASH_C,
        "cases": _document("annotator-a")["cases"],
    }

    assert list(validator.iter_errors(ledger)) == []
    assert list(validator.iter_errors(gold)) == []


def test_fully_disclosed_model_assistance_is_schema_valid():
    document = _document("annotator-a")
    document["model_assistance"] = {
        "used": True,
        "provider": "example-provider",
        "model": "example-model",
        "revision": "immutable-revision",
        "prompt_sha256": HASH_C,
        "affected_fields": ["claim_verdict"],
        "human_verification": True,
        "shown_before_human_decision": True,
    }

    validate_annotation(document)


def test_perfect_pairwise_agreement_is_reported_per_field():
    report = analyze_agreement([_document("annotator-a"), _document("annotator-b")])
    pair = report["pairwise"][0]

    assert pair["claim_boundaries"]["exact_f1"] == 1.0
    assert pair["claim_boundaries"]["overlap_f1"] == 1.0
    assert pair["categorical_fields"]["claim_verdict"]["exact_agreement"] == 1.0
    assert pair["categorical_fields"]["claim_verdict"]["cohen_kappa"] == 1.0
    assert pair["evidence_spans"]["mean_token_f1"] == 1.0
    assert pair["evidence_spans"]["mean_character_iou"] == 1.0
    assert report["krippendorff_alpha_nominal"]["claim_verdict"] == 1.0
    assert "combined" in report["policy"].lower()


def test_categorical_disagreement_is_not_hidden_by_prevalence():
    left = _document("annotator-a")
    right = _document("annotator-b")
    right_claims = right["cases"][0]["claims"]
    right_claims[0]["claim_verdict"] = "unsupported"
    right_claims[1]["claim_verdict"] = "supported"

    result = analyze_agreement([left, right])["pairwise"][0]["categorical_fields"][
        "claim_verdict"
    ]

    assert result["exact_agreement"] == 0.0
    assert result["cohen_kappa"] == -1.0
    assert result["prevalence_left"] == {
        "supported": 0.5,
        "unsupported": 0.5,
    }


def test_partial_boundary_overlap_is_separate_from_exact_match():
    left = _document("annotator-a")
    right = _document("annotator-b")
    right["cases"][0]["claims"][0]["answer_end"] = 9

    boundaries = analyze_agreement([left, right])["pairwise"][0]["claim_boundaries"]

    assert boundaries["exact_f1"] == 0.5
    assert boundaries["overlap_f1"] > boundaries["exact_f1"]
    assert (
        analyze_agreement([left, right])["pairwise"][0]["exact_boundary_aligned_claims"]
        == 1
    )


def test_wrong_source_evidence_receives_zero_span_credit():
    left = [_span(source_id="source-a")]
    right = [_span(source_id="source-b")]

    assert evidence_token_f1(left, right) == 0.0
    assert evidence_character_iou(left, right) == 0.0


def test_empty_spans_are_ineligible_not_perfect():
    assert evidence_token_f1([], []) is None
    assert evidence_character_iou([], []) is None


def test_cohen_kappa_is_undefined_for_constant_labels():
    assert cohen_kappa(["same", "same"], ["same", "same"]) is None


def test_krippendorff_alpha_handles_missing_assignments():
    assert (
        krippendorff_alpha_nominal(
            [
                ["supported", "supported", "supported"],
                ["unsupported", "unsupported"],
                ["supported"],
            ]
        )
        == 1.0
    )


def test_analysis_requires_two_distinct_annotators():
    document = _document("annotator-a")
    with pytest.raises(AgreementError, match="At least two"):
        analyze_agreement([document])
    with pytest.raises(AgreementError, match="distinct annotator IDs"):
        analyze_agreement([document, copy.deepcopy(document)])


def test_analysis_rejects_different_manifest_hashes():
    left = _document("annotator-a")
    right = _document("annotator-b")
    right["manifest_sha256"] = HASH_B

    with pytest.raises(AgreementError, match="different dataset manifests"):
        analyze_agreement([left, right])


def test_analysis_rejects_duplicate_cases():
    document = _document("annotator-a")
    document["cases"].append(copy.deepcopy(document["cases"][0]))

    with pytest.raises(AgreementError, match="Duplicate case_id"):
        validate_annotation(document)


def test_analysis_rejects_overlapping_claims():
    document = _document("annotator-a")
    document["cases"][0]["claims"][1]["answer_start"] = 9

    with pytest.raises(AgreementError, match="overlap"):
        validate_annotation(document)


def test_analysis_rejects_primary_label_repeated_as_secondary():
    document = _document("annotator-a")
    claim = document["cases"][0]["claims"][1]
    claim["secondary_root_causes"] = [claim["primary_root_cause"]]

    with pytest.raises(AgreementError, match="repeats its primary root cause"):
        validate_annotation(document)


def test_analysis_rejects_inconsistent_none_failure_and_root():
    document = _document("annotator-a")
    document["cases"][0]["claims"][0]["primary_root_cause"] = "not_observable"

    with pytest.raises(AgreementError, match="inconsistent none"):
        validate_annotation(document)


def test_nonpropositional_text_cannot_carry_diagnostic_labels():
    document = _document("annotator-a")
    claim = document["cases"][0]["claims"][0]
    claim["propositional"] = False
    claim["exclusion_reason"] = "non_verifiable_text"

    with pytest.raises(AgreementError, match="Non-propositional claim"):
        validate_annotation(document)


def test_model_assistance_must_be_fully_disclosed():
    document = _document("annotator-a")
    document["model_assistance"] = {"used": True}

    with pytest.raises(AgreementError, match="schema violation"):
        validate_annotation(document)


def test_adjudicated_artifact_cannot_enter_raw_agreement():
    document = _document("annotator-a")
    document["document_kind"] = "sealed_gold"

    with pytest.raises(AgreementError, match="schema violation"):
        validate_annotation(document)


def test_markdown_reports_every_field_without_combined_kappa():
    report = analyze_agreement([_document("annotator-a"), _document("annotator-b")])
    rendered = render_markdown(report)

    for field in (
        "claim_verdict",
        "failure_label",
        "primary_root_cause",
        "citation_state",
        "source_condition",
        "abstention_requirement",
    ):
        assert field in rendered
    assert "combined kappa or alpha is intentionally not reported" in rendered


def test_cli_writes_json_and_markdown_reports(tmp_path):
    annotation_paths = []
    for annotator in ("annotator-a", "annotator-b"):
        path = tmp_path / f"{annotator}.json"
        path.write_text(json.dumps(_document(annotator)), encoding="utf-8")
        annotation_paths.append(path)
    output_json = tmp_path / "agreement.json"
    output_markdown = tmp_path / "agreement.md"

    result = main(
        [
            "--annotations",
            *(str(path) for path in annotation_paths),
            "--output-json",
            str(output_json),
            "--output-markdown",
            str(output_markdown),
        ]
    )

    assert result == 0
    assert load_json(output_json)["status"] == "pre_adjudication_human_agreement"
    assert "No adjudicated labels" in output_markdown.read_text(encoding="utf-8")
