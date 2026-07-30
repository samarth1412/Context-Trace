"""Pure deterministic scoring primitives for the sealed evaluation."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Mapping, Sequence


FAILURE_LABELS = [
    "none",
    "retrieval_miss",
    "context_selection_error",
    "citation_mismatch",
    "answer_overreach",
    "contradiction",
    "insufficient_evidence",
    "should_have_abstained",
    "source_condition_failure",
]
CITATION_STATES = [
    "not_applicable",
    "correct",
    "partial",
    "wrong_source",
    "missing",
    "malformed",
]
_TOKEN_RE = re.compile(r"\w+|[^\w\s]", flags=re.UNICODE)


def span_overlap(left: Mapping[str, Any], right: Mapping[str, Any]) -> int:
    return max(
        0,
        min(int(left["end"]), int(right["end"]))
        - max(int(left["start"]), int(right["start"])),
    )


def maximum_weight_pairs(weights: Sequence[Sequence[int]]) -> list[tuple[int, int]]:
    """Return deterministic maximum-weight one-to-one pairs via Hungarian."""

    rows = len(weights)
    columns = max((len(row) for row in weights), default=0)
    size = max(rows, columns)
    if size == 0:
        return []
    maximum = max((max(row, default=0) for row in weights), default=0)
    cost = [
        [
            maximum - (int(weights[i][j]) if i < rows and j < len(weights[i]) else 0)
            for j in range(size)
        ]
        for i in range(size)
    ]
    u = [0] * (size + 1)
    v = [0] * (size + 1)
    p = [0] * (size + 1)
    way = [0] * (size + 1)
    for i in range(1, size + 1):
        p[0] = i
        j0 = 0
        minimum = [math.inf] * (size + 1)
        used = [False] * (size + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = math.inf
            j1 = 0
            for j in range(1, size + 1):
                if used[j]:
                    continue
                current = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if current < minimum[j]:
                    minimum[j] = current
                    way[j] = j0
                if minimum[j] < delta:
                    delta = minimum[j]
                    j1 = j
            for j in range(size + 1):
                if used[j]:
                    u[p[j]] += int(delta)
                    v[j] -= int(delta)
                else:
                    minimum[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    assignment = [(p[j] - 1, j - 1) for j in range(1, size + 1)]
    return sorted(
        (i, j)
        for i, j in assignment
        if i < rows and j < len(weights[i]) and int(weights[i][j]) > 0
    )


def align_claims(
    gold_claims: Sequence[Mapping[str, Any]],
    predicted_claims: Sequence[Mapping[str, Any]],
) -> tuple[list[tuple[Mapping[str, Any], Mapping[str, Any] | None]], list[int]]:
    weights = [
        [
            span_overlap(
                {"start": gold["answer_start"], "end": gold["answer_end"]},
                {"start": pred["start_char"], "end": pred["end_char"]},
            )
            if isinstance(pred.get("start_char"), int)
            and isinstance(pred.get("end_char"), int)
            else 0
            for pred in predicted_claims
        ]
        for gold in gold_claims
    ]
    pair_map = {gold: pred for gold, pred in maximum_weight_pairs(weights)}
    aligned = [
        (gold, predicted_claims[pair_map[index]] if index in pair_map else None)
        for index, gold in enumerate(gold_claims)
    ]
    used = set(pair_map.values())
    return aligned, [
        index for index in range(len(predicted_claims)) if index not in used
    ]


def confusion(
    rows: Sequence[Mapping[str, Any]],
    *,
    gold_field: str,
    pred_field: str,
    classes: Sequence[str],
) -> dict[str, Any]:
    matrix = {
        gold: {pred: 0 for pred in [*classes, "invalid_output"]} for gold in classes
    }
    for row in rows:
        gold = str(row["gold"][gold_field])
        if gold not in matrix:
            continue
        prediction = row.get("prediction")
        predicted = (
            str(prediction.get(pred_field))
            if isinstance(prediction, Mapping)
            else "invalid_output"
        )
        if predicted not in matrix[gold]:
            predicted = "invalid_output"
        matrix[gold][predicted] += 1

    per_class: dict[str, dict[str, Any]] = {}
    included: list[float] = []
    for label in classes:
        support = sum(matrix[label].values())
        predicted_count = sum(matrix[gold][label] for gold in classes)
        tp = matrix[label][label]
        fp = predicted_count - tp
        fn = support - tp
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall
            else 0.0
            if support
            else None
        )
        if support:
            included.append(float(f1 or 0.0))
        per_class[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return {
        "classes": list(classes),
        "matrix": matrix,
        "per_class": per_class,
        "macro_f1": sum(included) / len(included) if included else None,
        "included_classes": [label for label in classes if per_class[label]["support"]],
    }


def binary_f1(
    rows: Sequence[Mapping[str, Any]],
    *,
    gold_positive: Any,
    pred_positive: Any,
) -> dict[str, Any]:
    tp = fp = fn = tn = 0
    for row in rows:
        gold = bool(gold_positive(row["gold"]))
        prediction = row.get("prediction")
        predicted = bool(pred_positive(prediction)) if prediction is not None else False
        if gold and predicted:
            tp += 1
        elif gold:
            fn += 1
        elif predicted:
            fp += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else 0.0
        if tp + fn
        else None
    )
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def _dangerous(gold: Mapping[str, Any]) -> bool:
    citation_error = gold.get("citation_state") in {
        "partial",
        "wrong_source",
        "missing",
        "malformed",
    }
    unsafe_source = gold.get("source_condition") in {
        "current_noncanonical",
        "stale",
        "superseded",
        "low_authority",
        "conflicting_authorities",
    }
    return bool(
        gold.get("claim_verdict")
        in {"partially_supported", "unsupported", "contradicted", "unverifiable"}
        or gold.get("failure_label") != "none"
        or citation_error
        or unsafe_source
        or gold.get("abstention_requirement") == "must_abstain"
    )


def _green(prediction: Mapping[str, Any] | None, threshold: float) -> bool:
    return bool(
        prediction
        and prediction.get("green") is True
        and prediction.get("claim_verdict") == "supported"
        and prediction.get("failure_label") == "none"
        and prediction.get("citation_state") in {"correct", "not_applicable"}
        and prediction.get("source_condition") == "current_canonical"
        and prediction.get("diagnostic_abstention") is False
        and prediction.get("qualification_required") is False
        and isinstance(prediction.get("diagnostic_confidence"), (int, float))
        and float(prediction["diagnostic_confidence"]) >= threshold
    )


def dangerous_false_green(
    rows: Sequence[Mapping[str, Any]], *, threshold: float
) -> dict[str, Any]:
    dangerous = [row for row in rows if _dangerous(row["gold"])]
    false_greens = [
        row for row in dangerous if _green(row.get("prediction"), threshold)
    ]
    dangerous_traces = {row["case_id"] for row in dangerous}
    false_green_traces = {row["case_id"] for row in false_greens}
    return {
        "claim_numerator": len(false_greens),
        "claim_denominator": len(dangerous),
        "claim_rate": len(false_greens) / len(dangerous) if dangerous else None,
        "trace_numerator": len(false_green_traces),
        "trace_denominator": len(dangerous_traces),
        "trace_rate": (
            len(false_green_traces) / len(dangerous_traces)
            if dangerous_traces
            else None
        ),
    }


def root_accuracy(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if row["gold"]["primary_root_cause"] != "none"]
    correct = sum(
        1
        for row in eligible
        if row.get("prediction")
        and row["prediction"].get("primary_root_cause")
        == row["gold"]["primary_root_cause"]
    )
    return {
        "numerator": correct,
        "denominator": len(eligible),
        "accuracy": correct / len(eligible) if eligible else None,
    }


def _span_source(span: Mapping[str, Any], context_sources: Mapping[str, str]) -> str:
    if span.get("source_id"):
        return str(span["source_id"])
    return str(context_sources.get(str(span.get("context_id") or ""), ""))


def evidence_scores(
    gold: Mapping[str, Any],
    prediction: Mapping[str, Any] | None,
    *,
    context_sources: Mapping[str, str],
) -> dict[str, Any] | None:
    gold_spans = list(gold.get("evidence_spans") or [])
    if not gold_spans:
        return None
    predicted_spans = list(prediction.get("evidence_spans") or []) if prediction else []
    weights: list[list[int]] = []
    for gold_span in gold_spans:
        row = []
        for predicted in predicted_spans:
            same_source = _span_source(gold_span, context_sources) == _span_source(
                predicted, context_sources
            )
            if not same_source:
                row.append(0)
                continue
            row.append(
                span_overlap(
                    {"start": gold_span["start"], "end": gold_span["end"]},
                    {
                        "start": predicted.get("start_char", 0),
                        "end": predicted.get("end_char", 0),
                    },
                )
            )
        weights.append(row)
    pairs = maximum_weight_pairs(weights)
    overlap_chars = sum(weights[i][j] for i, j in pairs)
    gold_chars = sum(int(span["end"]) - int(span["start"]) for span in gold_spans)
    predicted_chars = sum(
        max(0, int(span.get("end_char", 0)) - int(span.get("start_char", 0)))
        for span in predicted_spans
    )
    union_chars = gold_chars + predicted_chars - overlap_chars

    gold_tokens = [
        Counter(
            token.casefold() for token in _TOKEN_RE.findall(str(span.get("text") or ""))
        )
        for span in gold_spans
    ]
    predicted_tokens = [
        Counter(
            token.casefold() for token in _TOKEN_RE.findall(str(span.get("text") or ""))
        )
        for span in predicted_spans
    ]
    matched_predicted_indices = {j for _, j in pairs}
    wrong_source = sum(
        1
        for index, span in enumerate(predicted_spans)
        if index not in matched_predicted_indices
        and _span_source(span, context_sources)
        not in {_span_source(gold_span, context_sources) for gold_span in gold_spans}
    )
    token_overlap = sum(
        sum((gold_tokens[i] & predicted_tokens[j]).values()) for i, j in pairs
    )
    predicted_token_mass = sum(sum(tokens.values()) for tokens in predicted_tokens)
    gold_token_mass = sum(sum(tokens.values()) for tokens in gold_tokens)
    precision = token_overlap / predicted_token_mass if predicted_token_mass else 0.0
    recall = token_overlap / gold_token_mass if gold_token_mass else 0.0
    token_f1 = (
        2 * precision * recall / (precision + recall) if precision + recall else 0.0
    )
    exact = bool(
        len(pairs) == len(gold_spans) == len(predicted_spans)
        and all(
            int(gold_spans[i]["start"]) == int(predicted_spans[j].get("start_char", -1))
            and int(gold_spans[i]["end"]) == int(predicted_spans[j].get("end_char", -1))
            for i, j in pairs
        )
    )
    return {
        "character_iou": overlap_chars / union_chars if union_chars else 0.0,
        "token_f1": token_f1,
        "exact_offsets": exact,
        "wrong_source_spans": wrong_source,
        "predicted_span_count": len(predicted_spans),
    }


def equal_mass_ece(
    confidence_correct: Sequence[tuple[float, bool]], *, bins: int = 15
) -> dict[str, Any]:
    if not confidence_correct:
        return {"ece": None, "bins": []}
    ordered = sorted(confidence_correct, key=lambda row: row[0])
    target = max(1, math.ceil(len(ordered) / bins))
    tie_groups: list[list[tuple[float, bool]]] = []
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][0] == ordered[index][0]:
            end += 1
        tie_groups.append(ordered[index:end])
        index = end
    groups: list[list[tuple[float, bool]]] = []
    current: list[tuple[float, bool]] = []
    for tie_group in tie_groups:
        if current and len(current) + len(tie_group) > target:
            groups.append(current)
            current = []
        current.extend(tie_group)
        if len(current) >= target:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    rows = [
        {
            "count": len(group),
            "lower": group[0][0],
            "upper": group[-1][0],
            "mean_confidence": sum(item[0] for item in group) / len(group),
            "accuracy": sum(bool(item[1]) for item in group) / len(group),
        }
        for group in groups
    ]
    ece = sum(
        row["count"] / len(ordered) * abs(row["accuracy"] - row["mean_confidence"])
        for row in rows
    )
    return {"ece": ece, "bins": rows}


def risk_coverage(
    confidence_correct: Sequence[tuple[float, bool, bool]],
) -> dict[str, Any]:
    """Compute tied-block, right-step AURC; tuple is confidence/correct/abstained."""

    total = len(confidence_correct)
    eligible = sorted(
        (row for row in confidence_correct if not row[2]),
        key=lambda row: row[0],
        reverse=True,
    )
    curve: list[dict[str, Any]] = []
    covered = errors = 0
    index = 0
    while index < len(eligible):
        confidence = eligible[index][0]
        block: list[tuple[float, bool, bool]] = []
        while index < len(eligible) and eligible[index][0] == confidence:
            block.append(eligible[index])
            index += 1
        covered += len(block)
        errors += sum(not item[1] for item in block)
        curve.append(
            {
                "threshold": confidence,
                "coverage": covered / total if total else 0.0,
                "risk": errors / covered,
            }
        )
    previous = 0.0
    aurc = 0.0
    for point in curve:
        aurc += (point["coverage"] - previous) * point["risk"]
        previous = point["coverage"]
    return {
        "aurc": aurc if total else None,
        "curve": curve,
        "coverage_at_fixed_error": {
            str(bound): max(
                (point["coverage"] for point in curve if point["risk"] <= bound),
                default=0.0,
            )
            for bound in (0.01, 0.02, 0.05, 0.10)
        },
        "risk_at_coverage": {
            str(target): next(
                (point["risk"] for point in curve if point["coverage"] >= target),
                None,
            )
            for target in (0.50, 0.60, 0.70, 0.80, 0.90)
        },
    }


def aggregate_metrics(
    rows: Sequence[Mapping[str, Any]],
    *,
    green_threshold: float,
    ece_bins: int,
) -> dict[str, Any]:
    failure = confusion(
        rows,
        gold_field="failure_label",
        pred_field="failure_label",
        classes=FAILURE_LABELS,
    )
    unverifiable = binary_f1(
        rows,
        gold_positive=lambda gold: gold["claim_verdict"] == "unverifiable",
        pred_positive=lambda pred: pred.get("claim_verdict") == "unverifiable",
    )
    abstention = binary_f1(
        [
            row
            for row in rows
            if row["gold"]["abstention_requirement"] in {"must_answer", "must_abstain"}
        ],
        gold_positive=lambda gold: gold["abstention_requirement"] == "must_abstain",
        pred_positive=lambda pred: pred.get("diagnostic_abstention") is True,
    )
    citation_rows = [
        row for row in rows if row["gold"]["citation_state"] != "not_applicable"
    ]
    citation_confusion = confusion(
        rows,
        gold_field="citation_state",
        pred_field="citation_state",
        classes=CITATION_STATES,
    )
    citation_error = binary_f1(
        citation_rows,
        gold_positive=lambda gold: (
            gold["citation_state"]
            in {"partial", "wrong_source", "missing", "malformed"}
        ),
        pred_positive=lambda pred: (
            pred.get("citation_state")
            in {"partial", "wrong_source", "missing", "malformed"}
        ),
    )
    resolvable = sum(
        bool(row.get("prediction"))
        and row["prediction"].get("citation_state")
        in {"correct", "partial", "wrong_source"}
        for row in citation_rows
    )
    evidence_rows = [
        (row, score)
        for row in rows
        if (
            score := evidence_scores(
                row["gold"],
                row.get("prediction"),
                context_sources=row.get("context_sources", {}),
            )
        )
        is not None
    ]
    evidence = [score for _, score in evidence_rows]
    family_evidence: dict[str, list[dict[str, Any]]] = {}
    for row, score in evidence_rows:
        family_evidence.setdefault(str(row["source_family"]), []).append(score)
    family_token_f1 = [
        sum(score["token_f1"] for score in scores) / len(scores)
        for scores in family_evidence.values()
    ]
    family_character_iou = [
        sum(score["character_iou"] for score in scores) / len(scores)
        for scores in family_evidence.values()
    ]
    confidence_correct = [
        (
            float(row["prediction"]["diagnostic_confidence"]),
            row["prediction"].get("failure_label") == row["gold"]["failure_label"],
        )
        for row in rows
        if row.get("prediction")
        and isinstance(row["prediction"].get("diagnostic_confidence"), (int, float))
    ]
    risk_input = [
        (
            confidence,
            correct,
            bool(row["prediction"].get("diagnostic_abstention")),
        )
        for row, (confidence, correct) in zip(
            [
                row
                for row in rows
                if row.get("prediction")
                and isinstance(
                    row["prediction"].get("diagnostic_confidence"), (int, float)
                )
            ],
            confidence_correct,
        )
    ]
    nli_count = sum(
        bool(row.get("prediction"))
        and row["prediction"].get("route")
        in {
            "nli",
            "deterministic_nli_agreement",
            "deterministic_nli_disagreement",
        }
        for row in rows
    )
    return {
        "claim_count": len(rows),
        "failure_label": failure,
        "root_cause": root_accuracy(rows),
        "unverifiable": unverifiable,
        "citation": {
            "confusion": citation_confusion,
            "error": citation_error,
            "eligible_claims": len(citation_rows),
            "resolvable_numerator": resolvable,
            "resolvable_rate": (
                resolvable / len(citation_rows) if citation_rows else None
            ),
        },
        "abstention": abstention,
        "diagnostic_coverage": (
            sum(
                bool(row.get("prediction"))
                and row["prediction"].get("diagnostic_abstention") is False
                for row in rows
            )
            / len(rows)
            if rows
            else None
        ),
        "unnecessary_abstention_rate": (
            sum(
                bool(row.get("prediction"))
                and row["prediction"].get("diagnostic_abstention") is True
                for row in rows
                if row["gold"]["abstention_requirement"] == "must_answer"
            )
            / sum(
                row["gold"]["abstention_requirement"] == "must_answer" for row in rows
            )
            if any(
                row["gold"]["abstention_requirement"] == "must_answer" for row in rows
            )
            else None
        ),
        "dangerous_false_green": dangerous_false_green(rows, threshold=green_threshold),
        "evidence": {
            "eligible_claims": len(evidence),
            "mean_token_f1": (
                sum(row["token_f1"] for row in evidence) / len(evidence)
                if evidence
                else None
            ),
            "mean_character_iou": (
                sum(row["character_iou"] for row in evidence) / len(evidence)
                if evidence
                else None
            ),
            "exact_offset_rate": (
                sum(row["exact_offsets"] for row in evidence) / len(evidence)
                if evidence
                else None
            ),
            "source_family_macro_token_f1": (
                sum(family_token_f1) / len(family_token_f1) if family_token_f1 else None
            ),
            "source_family_macro_character_iou": (
                sum(family_character_iou) / len(family_character_iou)
                if family_character_iou
                else None
            ),
            "wrong_source_rate": (
                sum(row["wrong_source_spans"] for row in evidence)
                / sum(row["predicted_span_count"] for row in evidence)
                if sum(row["predicted_span_count"] for row in evidence)
                else None
            ),
        },
        "calibration": equal_mass_ece(confidence_correct, bins=ece_bins),
        "selective_risk": risk_coverage(risk_input),
        "nli_invocation": {
            "numerator": nli_count,
            "denominator": len(rows),
            "rate": nli_count / len(rows) if rows else None,
        },
        "availability": {
            "valid_predictions": sum(row.get("prediction") is not None for row in rows),
            "requested_predictions": len(rows),
        },
    }
