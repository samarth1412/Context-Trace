from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field

import pytest

from benchmarks.jev_claim_verification.experiment import LABELS, ExperimentalJevJudge
from benchmarks.jev_v2_verification.adapter import adapt_ragtruth_case_pack
from benchmarks.jev_v2_verification.cascade import (
    CascadeError,
    calibrate_policy,
    cascade_decision,
    evaluate_frozen,
)
from benchmarks.jev_v2_verification.evidence_ablation import (
    complete_source_input,
    paired_metrics,
    run_evidence_ablation,
)
from benchmarks.jev_v2_verification.extension_analysis import exact_mcnemar, wilson_interval
from benchmarks.jev_v2_verification.minicheck_baseline import (
    MINICHECK_MODELS,
    MINICHECK_MODEL_REVISION,
    MiniCheckOutput,
    _prepare_pinned_model_cache,
    binary_metrics,
    compare_with_five_way_baseline,
    run_minicheck,
)
from benchmarks.jev_v2_verification.run import (
    calibrate_review_threshold,
    metrics,
    run,
    shared_input,
)


@dataclass
class FakeAnswer:
    choice: str
    confidence: float
    probabilities: dict[str, float]


@dataclass
class FakeUsage:
    input_tokens: int = 50
    output_tokens: int = 10


@dataclass
class FakeResponse:
    answers: dict[str, FakeAnswer]
    model: str = "jev-test"
    usage: FakeUsage = field(default_factory=FakeUsage)


class FakeClient:
    def __init__(self) -> None:
        self.states: list[object] = []

    def system_one(self, *, state, questions, model):
        del questions, model
        self.states.append(state)
        probabilities = {label: 0.025 for label in LABELS}
        probabilities["supported"] = 0.9
        return FakeResponse(
            answers={
                "verdict": FakeAnswer(
                    choice="supported",
                    confidence=0.875,
                    probabilities=probabilities,
                )
            }
        )


class FakeMiniCheck:
    model_metadata = {
        "provider": "official_minicheck",
        "resolved_model_revision": "fixture",
    }

    def __init__(self, probabilities):
        self.probabilities = iter(probabilities)
        self.inputs = []

    def score_one(self, *, document, claim):
        self.inputs.append({"document": document, "claim": claim})
        return MiniCheckOutput(
            support_probability=next(self.probabilities),
            latency_ms=10.0,
            input_tokens=20,
            used_chunks=(
                {
                    "text_sha256": "fixture",
                    "characters": len(document),
                    "support_probability": 0.9,
                },
            ),
        )


def _choice(**kwargs):
    return kwargs


def _source_pack(tmp_path):
    path = tmp_path / "ragtruth.json"
    rows = []
    labels = ["no_failure_detected", "partial_support", "contradicted_answer"]
    for index in range(9):
        rows.append(
            {
                "id": "case_%s" % index,
                "query": "What is the refund period?",
                "answer": "Refunds are available for thirty days.",
                "contexts": [{"id": "policy", "text": "The refund period is thirty days."}],
                "expected_labels": [labels[index % len(labels)]],
                "ragtruth_metadata": {"response_id": str(index), "model": "upstream"},
            }
        )
    path.write_text(json.dumps({"dataset": "RAGTruth", "cases": rows}), encoding="utf-8")
    return path


def test_ragtruth_adapter_is_deterministic_and_preserves_upstream_scope(tmp_path) -> None:
    source = _source_pack(tmp_path)
    first = adapt_ragtruth_case_pack(source, split="development", per_label=2)
    second = adapt_ragtruth_case_pack(source, split="development", per_label=2)

    assert first == second
    assert first["independent_source_labels"] is True
    assert first["label_scope"] == "answer_level"
    assert first["label_counts"] == {
        "contradicted": 2,
        "partially_supported": 2,
        "supported": 2,
    }
    assert all(case["label_scope"] == "answer_level" for case in first["cases"])


def test_ragtruth_sentence_projection_uses_upstream_span_offsets(tmp_path) -> None:
    source = tmp_path / "ragtruth_spans.json"
    answer = "The policy lasts thirty days. It also promises free shipping."
    start = answer.index("free shipping")
    source.write_text(
        json.dumps(
            {
                "dataset": "RAGTruth",
                "cases": [
                    {
                        "id": "case",
                        "query": "Summarize the policy.",
                        "answer": answer,
                        "contexts": [{"id": "policy", "text": "The policy lasts thirty days."}],
                        "expected_labels": ["partial_support"],
                        "ragtruth_metadata": {
                            "response_id": "case",
                            "answer_hallucination_spans": [
                                {
                                    "start": start,
                                    "end": start + len("free shipping"),
                                    "label_type": "Evident Baseless Info",
                                }
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = adapt_ragtruth_case_pack(source, split="development", unit="sentence")

    assert [case["expected_verdict"] for case in result["cases"]] == [
        "supported",
        "partially_supported",
    ]
    assert result["independent_source_labels"] is False
    assert result["cases"][1]["overlapping_upstream_annotations"][0]["label_type"] == "Evident Baseless Info"


def test_ragtruth_adapter_excludes_previously_evaluated_case_ids(tmp_path) -> None:
    source = _source_pack(tmp_path)

    result = adapt_ragtruth_case_pack(
        source,
        split="development",
        unit="answer",
        exclude_case_ids={"case_0", "absent_case"},
    )

    assert "case_0" not in {case["id"] for case in result["cases"]}
    assert result["selection"]["available_before_exclusion"] == 9
    assert result["selection"]["excluded_case_id_count"] == 2
    assert result["selection"]["excluded_present_count"] == 1
    assert len(result["selection"]["excluded_case_ids_sha256"]) == 64


def test_extension_analysis_reports_paired_exact_test_and_wilson_interval() -> None:
    paired = exact_mcnemar(
        ["supported", "supported", "not_supported", "not_supported"],
        ["supported", "supported", "not_supported", "not_supported"],
        ["not_supported", "not_supported", "not_supported", "supported"],
    )

    assert paired == {
        "candidate_only_correct": 3,
        "baseline_only_correct": 0,
        "discordant_pairs": 3,
        "exact_two_sided_p": 0.25,
    }
    interval = wilson_interval(8, 10)
    assert interval is not None
    assert interval[0] < 0.8 < interval[1]


def test_shared_input_excludes_gold_and_diagnostic_metadata() -> None:
    case = {
        "id": "case",
        "query": "What is the refund period?",
        "claim": "Refunds are available for thirty days.",
        "contexts": [{"id": "policy", "text": "The refund period is thirty days."}],
        "expected_verdict": "supported",
        "upstream_label": "no_failure_detected",
    }

    contexts, audit = shared_input(case)

    assert contexts
    assert audit["evaluation_label_sent"] is False
    serialized = json.dumps(audit["exact_shared_input"])
    assert "expected_verdict" not in serialized
    assert "upstream_label" not in serialized


def test_complete_source_input_is_explicitly_non_oracle_and_excludes_gold() -> None:
    case = {
        "id": "case",
        "query": "What is the refund period?",
        "claim": "Refunds are available for thirty days.",
        "contexts": [
            {
                "id": "policy",
                "text": "The refund period is thirty days. Shipping is free.",
            }
        ],
        "expected_verdict": "supported",
    }

    contexts, audit = complete_source_input(case)

    assert len(contexts) == 2
    assert audit["is_oracle_evidence"] is False
    assert audit["evaluation_label_sent"] is False
    serialized = json.dumps(audit["exact_input"])
    assert "expected_verdict" not in serialized


def test_evidence_ablation_records_paired_transitions() -> None:
    cases = [
        {
            "id": "case",
            "dataset": "fixture",
            "label_scope": "sentence",
            "query": "What is the refund period?",
            "claim": "The refund period is thirty days.",
            "contexts": [{"id": "policy", "text": "The refund period is thirty days."}],
            "expected_verdict": "supported",
        }
    ]

    result = run_evidence_ablation(cases, split_metadata={"split": "development"})

    assert result["remote_inference"] is False
    assert result["jev_run"] is False
    assert result["stable_defaults_changed"] is False
    assert result["internal_selector_equivalence"] == {
        "identical_cases": 1,
        "total_cases": 1,
        "meaning": (
            "LocalQualityJudge applies its selector internally. Identical cases received the "
            "same ordered span texts in both availability conditions."
        ),
    }
    assert result["metrics"]["stable_semantic"]["paired_transitions"]["both_correct"]["count"] == 1


def test_paired_metrics_identifies_candidate_selector_recovery() -> None:
    prediction = lambda verdict: {  # noqa: E731
        "verdict": verdict,
        "confidence": 0.9,
        "review_required": False,
        "latency_ms": 1.0,
    }
    rows = [
        {
            "case_id": "recovered",
            "expected_verdict": "supported",
            "conditions": {
                "selected_evidence": {"judge": prediction("unsupported")},
                "complete_source_availability": {"judge": prediction("supported")},
            },
        }
    ]

    result = paired_metrics(rows, "judge")

    transition = result["paired_transitions"]["selected_wrong_complete_correct"]
    assert transition == {"count": 1, "case_ids": ["recovered"]}


def test_run_uses_one_shared_input_and_records_real_jev_outputs() -> None:
    case = {
        "id": "case",
        "dataset": "fixture",
        "label_scope": "answer_level",
        "query": "What is the refund period?",
        "claim": "Refunds are available for thirty days.",
        "contexts": [{"id": "policy", "text": "The refund period is thirty days."}],
        "expected_verdict": "supported",
    }
    client = FakeClient()
    judge = ExperimentalJevJudge(client=client, choice_factory=_choice)

    result = run(
        [case],
        split_metadata={"split": "development"},
        jev=judge,
        jev_review_threshold=0.60,
    )

    row = result["rows"][0]
    assert set(row["predictions"]) == {"stable_semantic", "local_deterministic", "jev"}
    assert row["input_audit"]["evaluation_label_sent"] is False
    assert client.states[0]["claim"] == case["claim"]
    assert client.states[0]["selected_evidence"]
    assert row["predictions"]["jev"]["backend"]["resolved_model"] == "jev-test"
    assert row["predictions"]["jev"]["reason"] is None
    assert result["input_equivalence"]["selected_evidence_equal_across_variants"] is True


def test_minicheck_uses_shared_evidence_and_preserves_binary_scope() -> None:
    cases = [
        {
            "id": "supported",
            "dataset": "fixture",
            "label_scope": "sentence",
            "query": "What is the refund period?",
            "claim": "The refund period is thirty days.",
            "contexts": [{"id": "policy", "text": "The refund period is thirty days."}],
            "expected_verdict": "supported",
        },
        {
            "id": "contradicted",
            "dataset": "fixture",
            "label_scope": "sentence",
            "query": "What is the refund period?",
            "claim": "The refund period is ninety days.",
            "contexts": [{"id": "policy", "text": "The refund period is thirty days."}],
            "expected_verdict": "contradicted",
        },
    ]
    scorer = FakeMiniCheck([0.9, 0.1])

    result = run_minicheck(
        cases,
        split_metadata={"split": "development"},
        scorer=scorer,
    )

    assert result["task"]["five_way_comparison_allowed"] is False
    assert result["metrics"]["accuracy"] == 1.0
    assert result["model"]["resolved_model_revision"] == "fixture"
    assert scorer.inputs[0]["claim"] == cases[0]["claim"]
    assert scorer.inputs[0]["document"] == "The refund period is thirty days."
    assert result["rows"][1]["binary_gold"] == "not_supported"
    assert result["rows"][0]["prediction"]["explanation"] is None


def test_minicheck_binary_metrics_reports_dangerous_false_support() -> None:
    rows = [
        {
            "case_id": "unsafe",
            "binary_gold": "not_supported",
            "five_way_gold": "unsupported",
            "prediction": {
                "label": "supported",
                "probabilities": {"supported": 0.8, "not_supported": 0.2},
                "latency_ms": 5.0,
                "input_tokens": 10,
            },
        },
        {
            "case_id": "safe",
            "binary_gold": "supported",
            "five_way_gold": "supported",
            "prediction": {
                "label": "supported",
                "probabilities": {"supported": 0.9, "not_supported": 0.1},
                "latency_ms": 7.0,
                "input_tokens": 12,
            },
        },
    ]

    result = binary_metrics(rows)

    assert result["dangerous_false_support"] == {
        "count": 1,
        "denominator_not_supported": 1,
        "rate": 1.0,
        "case_ids": ["unsafe"],
    }
    assert result["input_tokens"]["total"] == 22
    assert result["by_five_way_gold"]["unsupported"] == {
        "cases": 1,
        "predicted_supported": 1,
        "predicted_supported_rate": 1.0,
    }


def test_minicheck_comparison_requires_and_reports_exact_shared_inputs() -> None:
    minicheck = {
        "rows": [
            {
                "case_id": "case-1",
                "five_way_gold": "contradicted",
                "binary_gold": "not_supported",
                "input_audit": {"input_sha256": "same"},
                "prediction": {"label": "not_supported"},
            }
        ]
    }
    baseline = {
        "rows": [
            {
                "case_id": "case-1",
                "input_audit": {"input_sha256": "same"},
                "predictions": {
                    "stable_semantic": {"verdict": "supported"},
                    "jev": {"verdict": "contradicted"},
                },
            }
        ]
    }

    result = compare_with_five_way_baseline(minicheck, baseline)

    assert result["variants"]["stable_semantic"]["minicheck_only_correct"] == 1
    assert result["variants"]["stable_semantic"]["agreement_rate"] == 0.0
    assert result["variants"]["jev"]["both_correct"] == 1
    assert result["variants"]["jev"]["agreement_rate"] == 1.0


def test_minicheck_cache_preflight_pins_offline_main_ref(tmp_path) -> None:
    repository = tmp_path / "models--lytang--MiniCheck-Flan-T5-Large"
    snapshot = repository / "snapshots" / MINICHECK_MODEL_REVISION
    snapshot.mkdir(parents=True)
    for name in ("config.json", "generation_config.json", "pytorch_model.bin", "tokenizer_config.json"):
        (snapshot / name).touch()

    empty_sha256 = hashlib.sha256(b"").hexdigest()
    _prepare_pinned_model_cache(
        tmp_path,
        expected_weight_bytes=0,
        expected_weight_sha256=empty_sha256,
    )

    assert (repository / "refs" / "main").read_text().strip() == MINICHECK_MODEL_REVISION
    assert not (repository / "refs" / "main").read_bytes().endswith(b"\n")


def test_minicheck_roberta_cache_preflight_uses_its_pinned_repository(tmp_path) -> None:
    model_spec = MINICHECK_MODELS["roberta-large"]
    repository = tmp_path / "models--lytang--MiniCheck-RoBERTa-Large"
    snapshot = repository / "snapshots" / model_spec.revision
    snapshot.mkdir(parents=True)
    for name in model_spec.required_files:
        (snapshot / name).touch()

    _prepare_pinned_model_cache(
        tmp_path,
        model_spec=model_spec,
        expected_weight_bytes=0,
        expected_weight_sha256=hashlib.sha256(b"").hexdigest(),
    )

    assert (repository / "refs" / "main").read_text().strip() == model_spec.revision
    assert not (repository / "refs" / "main").read_bytes().endswith(b"\n")


def test_metrics_report_dangerous_supported_denominator_and_probability_quality() -> None:
    rows = [
        {
            "case_id": "unsafe",
            "expected_verdict": "unsupported",
            "predictions": {
                "jev": {
                    "verdict": "supported",
                    "review_required": False,
                    "latency_ms": 10.0,
                    "probabilities": {label: 0.2 for label in LABELS},
                    "usage": {"input_tokens": 10, "output_tokens": 2},
                }
            },
        },
        {
            "case_id": "good",
            "expected_verdict": "supported",
            "predictions": {
                "jev": {
                    "verdict": "supported",
                    "review_required": False,
                    "latency_ms": 20.0,
                    "probabilities": {
                        label: 1.0 if label == "supported" else 0.0
                        for label in LABELS
                    },
                    "usage": {"input_tokens": 10, "output_tokens": 2},
                }
            },
        },
    ]

    result = metrics(rows, "jev")

    assert result["incorrect_supported"]["count"] == 1
    assert result["incorrect_supported"]["denominator_non_supported"] == 1
    assert result["false_alarms_on_supported"]["denominator_supported"] == 1
    assert result["usage"]["total_tokens"] == 24
    assert "multiclass_brier" in result["probability_quality"]


def test_review_threshold_calibration_uses_development_rows() -> None:
    rows = []
    for index, (probability, correct) in enumerate(((0.95, True), (0.75, True), (0.55, False))):
        verdict = "supported" if correct else "contradicted"
        rows.append(
            {
                "case_id": str(index),
                "expected_verdict": "supported",
                "predictions": {
                    "jev": {
                        "verdict": verdict,
                        "top_probability": probability,
                    }
                },
            }
        )

    calibration = calibrate_review_threshold({"rows": rows}, min_coverage=0.60)

    assert calibration["selection_split"] == "development"
    assert calibration["chosen_threshold"] >= 0.60


def _cascade_result(split: str = "development") -> dict:
    probabilities = {label: 0.0 for label in LABELS}
    probabilities["supported"] = 0.9
    return {
        "split": {"split": split},
        "rows": [
            {
                "case_id": "case",
                "expected_verdict": "supported",
                "predictions": {
                    "stable_semantic": {
                        "verdict": "partially_supported",
                        "confidence": 0.7,
                        "latency_ms": 1.0,
                    },
                    "jev": {
                        "verdict": "supported",
                        "confidence": 0.9,
                        "top_probability": 0.9,
                        "probabilities": probabilities,
                        "latency_ms": 10.0,
                        "usage": {"input_tokens": 20, "output_tokens": 5},
                        "reason": None,
                    },
                },
            }
        ],
    }


def test_cascade_decision_does_not_read_evaluation_label() -> None:
    predictions = _cascade_result()["rows"][0]["predictions"]
    policy = {
        "local_supported_confidence": 0.9,
        "jev_supported_probability": 0.75,
        "review_confidence": 0.8,
        "always_review_supported": True,
    }

    first = cascade_decision(predictions, policy=policy)
    second = cascade_decision(json.loads(json.dumps(predictions)), policy=policy)

    assert first == second
    assert first["remote_called"] is True
    assert first["verdict"] == "supported"
    assert first["review_required"] is True


def test_cascade_support_gate_falls_back_without_generated_explanation() -> None:
    predictions = _cascade_result()["rows"][0]["predictions"]
    predictions["jev"]["probabilities"]["supported"] = 0.7
    predictions["jev"]["top_probability"] = 0.7
    policy = {
        "local_supported_confidence": 0.9,
        "jev_supported_probability": 0.75,
        "review_confidence": 0.8,
        "always_review_supported": True,
    }

    decision = cascade_decision(predictions, policy=policy)

    assert decision["verdict"] == "partially_supported"
    assert decision["decision_source"] == "stable_fallback_after_jev_support_gate"
    assert decision["support_gate_applied"] is True
    assert decision["review_reasons"] == ["jev_confidence_below_threshold"]


def test_cascade_calibration_rejects_heldout_selection() -> None:
    with pytest.raises(CascadeError, match="Expected development result"):
        calibrate_policy(_cascade_result("heldout"), source_sha256="fixture")


def test_frozen_cascade_manifest_is_hash_checked() -> None:
    development = _cascade_result()
    manifest, _analysis = calibrate_policy(development, source_sha256="development")
    manifest["policy"]["jev_supported_probability"] = 0.99

    with pytest.raises(CascadeError, match="policy id"):
        evaluate_frozen(
            _cascade_result("heldout"),
            manifest=manifest,
            expected_split="heldout",
            source_sha256="heldout",
        )
