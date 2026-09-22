from __future__ import annotations

from benchmarks.external_fiveway_confirmation.atomic_coverage_experiment import analyze
from benchmarks.external_fiveway_confirmation.atomic_coverage_experiment import metrics


def _row(case_id: str, cohort: str, expected: str, entailment: float) -> dict:
    return {
        "case_id": case_id,
        "cohort": cohort,
        "expected_verdict": expected,
        "prediction": {
            "requirements": [
                {
                    "nli_scores": {
                        "entailment": entailment,
                        "contradiction": 0.01,
                        "neutral": 0.99 - entailment,
                    }
                }
            ]
        },
    }


def test_metrics_counts_partial_predictions_as_false_support() -> None:
    rows = [
        _row("s", "calibration", "supported", 0.8),
        _row("p", "calibration", "partially_supported", 0.7),
    ]

    result = metrics(rows, threshold=0.75)

    assert result["accuracy"] == 1.0
    assert result["partial_incorrectly_supported_rate"] == 0.0


def test_analysis_selects_on_calibration_and_reports_validation() -> None:
    rows = [
        _row("cs", "calibration", "supported", 0.9),
        _row("cp", "calibration", "partially_supported", 0.4),
        _row("vs", "validation", "supported", 0.9),
        _row("vp", "validation", "partially_supported", 0.4),
    ]

    result = analyze(rows)

    assert result["policy"]["selection_cohort"] == "calibration"
    assert result["validation_metrics"]["accuracy"] == 1.0
    assert result["meets_prespecified_success_requirements"] is True
    assert result["heldout_queried"] is False
