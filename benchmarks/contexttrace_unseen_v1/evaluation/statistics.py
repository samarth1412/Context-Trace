"""Deterministic resampling and multiplicity procedures from the frozen SAP."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Any, Callable, Mapping, Sequence


Estimator = Callable[[Sequence[Mapping[str, Any]]], float | None]


def percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value.")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def hierarchical_cluster_bootstrap(
    rows: Sequence[Mapping[str, Any]],
    estimator: Estimator,
    *,
    replicates: int,
    seed: int,
    tail_predicate: Callable[[float], bool] | None = None,
) -> dict[str, Any]:
    strata: dict[tuple[str, str], dict[str, list[Mapping[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in rows:
        strata[(str(row["track"]), str(row["domain"]))][
            str(row["source_family"])
        ].append(row)
    if not strata:
        raise ValueError("Bootstrap requires at least one stratum.")
    rng = random.Random(seed)
    estimates: list[float] = []
    invalid = 0
    tail_count = 0
    ordered_strata = sorted(strata)
    for _ in range(replicates):
        sample: list[Mapping[str, Any]] = []
        for stratum in ordered_strata:
            clusters = strata[stratum]
            names = sorted(clusters)
            for _draw in names:
                selected = names[rng.randrange(len(names))]
                sample.extend(clusters[selected])
        estimate = estimator(sample)
        if estimate is None or not math.isfinite(float(estimate)):
            invalid += 1
        else:
            numeric = float(estimate)
            estimates.append(numeric)
            if tail_predicate is not None and tail_predicate(numeric):
                tail_count += 1
    return {
        "replicates": replicates,
        "valid_replicates": len(estimates),
        "invalid_replicates": invalid,
        "lower_95": percentile(estimates, 0.025) if estimates else None,
        "upper_95": percentile(estimates, 0.975) if estimates else None,
        "unstable": len(estimates) < math.ceil(replicates * 0.95),
        "tail_count": tail_count if tail_predicate is not None else None,
        "plus_one_tail_probability": (
            (tail_count + 1) / (len(estimates) + 1)
            if tail_predicate is not None and estimates
            else None
        ),
    }


def paired_cluster_randomization(
    rows: Sequence[Mapping[str, Any]],
    difference_estimator: Callable[
        [Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]]], float | None
    ],
    *,
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    """Swap complete candidate/predecessor bundles within source families."""

    clusters: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        clusters[str(row["source_family"])].append(row)
    candidate = [{**row, "prediction": row.get("candidate_prediction")} for row in rows]
    predecessor = [
        {**row, "prediction": row.get("predecessor_prediction")} for row in rows
    ]
    observed = difference_estimator(candidate, predecessor)
    if observed is None:
        return {
            "observed_difference": None,
            "replicates": replicates,
            "p_value": None,
        }
    rng = random.Random(seed)
    extreme = 0
    cluster_names = sorted(clusters)
    for _ in range(replicates):
        left: list[Mapping[str, Any]] = []
        right: list[Mapping[str, Any]] = []
        for cluster in cluster_names:
            swap = bool(rng.getrandbits(1))
            for row in clusters[cluster]:
                candidate_prediction = row.get("candidate_prediction")
                predecessor_prediction = row.get("predecessor_prediction")
                left.append(
                    {
                        **row,
                        "prediction": (
                            predecessor_prediction if swap else candidate_prediction
                        ),
                    }
                )
                right.append(
                    {
                        **row,
                        "prediction": (
                            candidate_prediction if swap else predecessor_prediction
                        ),
                    }
                )
        estimate = difference_estimator(left, right)
        if estimate is not None and abs(float(estimate)) >= abs(float(observed)):
            extreme += 1
    return {
        "observed_difference": float(observed),
        "replicates": replicates,
        "extreme_replicates": extreme,
        "p_value": (extreme + 1) / (replicates + 1),
    }


def holm_adjust(p_values: Mapping[str, float | None]) -> dict[str, float | None]:
    valid = sorted(
        ((name, float(value)) for name, value in p_values.items() if value is not None),
        key=lambda item: (item[1], item[0]),
    )
    adjusted: dict[str, float | None] = {name: None for name in p_values}
    running = 0.0
    count = len(valid)
    for rank, (name, value) in enumerate(valid):
        running = max(running, min(1.0, (count - rank) * value))
        adjusted[name] = running
    return adjusted
