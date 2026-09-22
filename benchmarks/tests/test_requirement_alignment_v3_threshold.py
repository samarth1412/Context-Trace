from __future__ import annotations

from benchmarks.requirement_alignment.diagnose_v3_threshold import (
    fine_threshold_diagnostic,
)


def _row(identifier: str, label: str) -> dict:
    return {
        "id": identifier,
        "target": {"label": label},
        "source": {
            "relation": "Entailment" if label == "covered" else "NotMentioned",
            "hypothesis_id": "nda-1",
            "hypothesis_description": "Example",
            "evidence_span_indexes": [1],
        },
    }


def test_fine_threshold_diagnostic_does_not_relabel_promotion_result() -> None:
    contract = [_row("n", "missing"), _row("p", "covered")]
    wice = [_row("wn", "missing"), _row("wp", "covered")]

    report = fine_threshold_diagnostic(
        contract,
        [0.1, 0.91],
        wice,
        [0.1, 0.91],
    )

    assert report["best_eligible"]["contract_development"]["positive_recall"] == 1.0
    assert report["contract_recall_target_met"] is True
    assert "cannot satisfy" in report["warning"]
