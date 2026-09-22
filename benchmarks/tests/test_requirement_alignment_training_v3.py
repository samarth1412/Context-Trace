from __future__ import annotations

from benchmarks.requirement_alignment.train_v3 import select_dual_threshold


def test_dual_threshold_enforces_both_false_positive_caps() -> None:
    contract_targets = [0] * 20 + [1] * 4
    contract_probabilities = [0.4] * 19 + [0.86] + [0.86] * 3 + [0.2]
    wice_targets = [0] * 20 + [1] * 4
    wice_probabilities = [0.4] * 20 + [0.86] * 2 + [0.2] * 2

    policy = select_dual_threshold(
        contract_targets,
        contract_probabilities,
        wice_targets,
        wice_probabilities,
    )
    selected = policy["selected"]

    assert selected["threshold"] == 0.85
    assert selected["contract_development"]["false_positive_rate"] == 0.05
    assert selected["wice_internal"]["false_positive_rate"] == 0.0
    assert selected["promotion_gates_met"] is True


def test_dual_threshold_reports_when_recall_gate_is_not_met() -> None:
    targets = [0, 0, 1, 1]
    probabilities = [0.1, 0.2, 0.1, 0.2]

    selected = select_dual_threshold(
        targets, probabilities, targets, probabilities
    )["selected"]

    assert selected["contract_development"]["false_positive_rate"] == 0.0
    assert selected["wice_internal"]["false_positive_rate"] == 0.0
    assert selected["contract_development"]["positive_recall"] == 0.0
    assert selected["promotion_gates_met"] is False
