from __future__ import annotations

from benchmarks.external_fiveway_confirmation.atomic_failure_audit import (
    exact_requirement_provenance,
)
from benchmarks.external_fiveway_confirmation.atomic_failure_audit import (
    selected_source_ids,
)
from benchmarks.external_fiveway_confirmation.atomic_failure_audit import (
    threshold_prediction,
)


def test_exact_requirement_provenance_rejects_reconstructed_claim() -> None:
    claim = "Mad Love's reputation has grown, and it is viewed positively."

    assert exact_requirement_provenance(claim, "Mad Love's reputation has grown.")
    assert not exact_requirement_provenance(
        claim, "Mad Love's reputation has it is viewed positively."
    )


def test_selected_source_ids_strip_span_offsets() -> None:
    requirements = [
        {
            "evidence_context_ids": [
                "wice_dev00001_e0003:0:42",
                "wice_dev00001_e0007:3:55",
            ]
        }
    ]

    assert selected_source_ids(requirements) == {
        "wice_dev00001_e0003",
        "wice_dev00001_e0007",
    }


def test_threshold_prediction_requires_every_requirement() -> None:
    requirements = [
        {"nli_scores": {"entailment": 0.9}},
        {"nli_scores": {"entailment": 0.1}},
    ]

    assert threshold_prediction(requirements, 0.15) == "partially_supported"
