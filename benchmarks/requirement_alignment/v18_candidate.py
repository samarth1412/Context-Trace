"""Load and apply the frozen V18 form of the V17 development candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.v14_fiveway_policy import (
    LABELS,
    _sha256_json,
    feature_vector,
)
from benchmarks.requirement_alignment.v15_atomic_completeness import (
    TARGET_LABELS,
    atomic_feature_vector,
)
from benchmarks.requirement_alignment.v17_multispan_completeness import (
    multispan_feature_vector,
)


class V18CandidateError(RuntimeError):
    """Raised when frozen-candidate inputs or artifacts violate their contract."""


def load_frozen_candidate(
    artifact_path: str | Path, manifest_path: str | Path
) -> dict[str, Any]:
    import joblib

    artifact = Path(artifact_path)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if actual != manifest.get("artifact", {}).get("sha256"):
        raise V18CandidateError(
            "Frozen candidate artifact does not match its manifest."
        )
    bundle = joblib.load(artifact)
    if bundle.get("schema_version") != "contexttrace-v18-frozen-candidate-1.0":
        raise V18CandidateError("Frozen candidate has an unknown schema.")
    return bundle


def predict_candidate(
    bundle: dict[str, Any],
    dataset: dict[str, Any],
    relation_scores: dict[str, Any],
    atomic_scores: dict[str, Any],
    multispan_scores: dict[str, Any],
) -> list[dict[str, Any]]:
    aligned = _aligned_rows(dataset, relation_scores, atomic_scores, multispan_scores)
    v14_matrix = []
    v14_names: list[str] | None = None
    for example, relation in zip(
        aligned["examples"], aligned["relations"], strict=True
    ):
        names, values = feature_vector(example, relation)
        if v14_names is None:
            v14_names = names
        elif names != v14_names:
            raise V18CandidateError("V14 confirmation feature schemas differ.")
        v14_matrix.append(values)
    if v14_names != bundle["v14"]["feature_names"]:
        raise V18CandidateError("V14 confirmation features do not match the freeze.")
    v14_probabilities = _ordered_probabilities(
        bundle["v14"]["model"], v14_matrix, labels=LABELS
    )
    v14_predictions = [
        _v14_route(values, bundle["v14"]["policy"]) for values in v14_probabilities
    ]

    v15_matrix = []
    v15_names: list[str] | None = None
    minimum_single_span_entailments = []
    for example, relation, atomic, multispan, probabilities in zip(
        aligned["examples"],
        aligned["relations"],
        aligned["atomic"],
        aligned["multispan"],
        v14_probabilities,
        strict=True,
    ):
        atomic_names, atomic_values = atomic_feature_vector(atomic)
        relation_names, relation_values = feature_vector(example, relation)
        names = (
            atomic_names
            + [f"v14.probability.{label}" for label in LABELS]
            + relation_names
        )
        values = atomic_values + probabilities + relation_values
        if v15_names is None:
            v15_names = names
        elif names != v15_names:
            raise V18CandidateError("V15 confirmation feature schemas differ.")
        v15_matrix.append(values)
        multispan_feature_vector(multispan)
        minimum_single_span_entailments.append(
            min(
                float(requirement["summary"]["best_single_entailment"])
                for requirement in multispan["requirements"]
            )
        )
    if v15_names != bundle["v15"]["feature_names"]:
        raise V18CandidateError("V15 confirmation features do not match the freeze.")
    completeness = _positive_probabilities(bundle["v15"]["model"], v15_matrix)
    v15_predictions = [
        _v15_route(base, values, probability, bundle["v15"]["policy"])
        for base, values, probability in zip(
            v14_predictions, v14_probabilities, completeness, strict=True
        )
    ]
    final_predictions = [
        _v17_rescue(
            v15_prediction,
            v14_prediction,
            minimum_entailment,
            bundle["v17"]["policy"],
        )
        for v15_prediction, v14_prediction, minimum_entailment in zip(
            v15_predictions,
            v14_predictions,
            minimum_single_span_entailments,
            strict=True,
        )
    ]
    return [
        {
            "case_id": case_id,
            "v14_probabilities": {
                label: round(float(value), 8)
                for label, value in zip(LABELS, probabilities, strict=True)
            },
            "v14_prediction": v14_prediction,
            "complete_support_probability": round(float(complete), 8),
            "v15_prediction": v15_prediction,
            "minimum_single_span_entailment": round(float(minimum), 4),
            "prediction": prediction,
        }
        for case_id, probabilities, v14_prediction, complete, v15_prediction, minimum, prediction in zip(
            aligned["case_ids"],
            v14_probabilities,
            v14_predictions,
            completeness,
            v15_predictions,
            minimum_single_span_entailments,
            final_predictions,
            strict=True,
        )
    ]


def _v14_route(probabilities: list[float], policy: dict[str, Any]) -> str:
    indexes = {label: LABELS.index(label) for label in LABELS}
    review_risk = (
        probabilities[indexes["partially_supported"]]
        + probabilities[indexes["unverifiable"]]
    )
    if (
        probabilities[indexes["supported"]]
        >= float(policy["support_probability_minimum"])
        and probabilities[indexes["contradicted"]]
        <= float(policy["contradiction_probability_maximum"])
        and review_risk <= float(policy["partial_or_ambiguous_probability_maximum"])
    ):
        return "supported"
    return max(
        (label for label in LABELS if label != "supported"),
        key=lambda label: probabilities[indexes[label]],
    )


def _v15_route(
    v14_prediction: str,
    v14_probabilities: list[float],
    completeness: float,
    policy: dict[str, Any],
) -> str:
    if v14_prediction not in TARGET_LABELS:
        return v14_prediction
    indexes = {label: LABELS.index(label) for label in LABELS}
    if (
        completeness >= float(policy["complete_support_probability_minimum"])
        and v14_probabilities[indexes["contradicted"]]
        <= float(policy["contradiction_probability_maximum"])
        and v14_probabilities[indexes["unverifiable"]]
        <= float(policy["unverifiable_probability_maximum"])
    ):
        return "supported"
    return "partially_supported"


def _v17_rescue(
    v15_prediction: str,
    v14_prediction: str,
    minimum_single_span_entailment: float,
    policy: dict[str, Any],
) -> str:
    if (
        v15_prediction != "supported"
        and v14_prediction == "supported"
        and minimum_single_span_entailment
        >= float(policy["minimum_single_span_entailment"])
    ):
        return "supported"
    return v15_prediction


def _ordered_probabilities(
    model: Any, matrix: list[list[float]], *, labels: tuple[str, ...]
) -> list[list[float]]:
    probabilities = model.predict_proba(matrix)
    indexes = {str(label): index for index, label in enumerate(model.classes_)}
    if set(indexes) != set(labels):
        raise V18CandidateError("Frozen model classes do not match the verdict schema.")
    return [[float(row[indexes[label]]) for label in labels] for row in probabilities]


def _positive_probabilities(model: Any, matrix: list[list[float]]) -> list[float]:
    indexes = {bool(label): index for index, label in enumerate(model.classes_)}
    if set(indexes) != {False, True}:
        raise V18CandidateError("Completeness model does not expose binary classes.")
    return [float(row[indexes[True]]) for row in model.predict_proba(matrix)]


def _aligned_rows(
    dataset: dict[str, Any],
    relation_scores: dict[str, Any],
    atomic_scores: dict[str, Any],
    multispan_scores: dict[str, Any],
) -> dict[str, Any]:
    split = str(dataset.get("split") or "")
    if not split or any(
        artifact.get("split") != split
        for artifact in (relation_scores, atomic_scores, multispan_scores)
    ):
        raise V18CandidateError("Candidate inputs do not share one named split.")
    dataset_hash = _sha256_json(dataset)
    if any(
        artifact.get("dataset_sha256") != dataset_hash
        for artifact in (relation_scores, atomic_scores, multispan_scores)
    ):
        raise V18CandidateError("Candidate score artifacts do not match the dataset.")
    if (
        relation_scores.get("remote_inference_used") is not False
        or relation_scores.get("evaluation_labels_sent") is not False
        or atomic_scores.get("remote_inference_used") is not False
        or atomic_scores.get("input_contract", {}).get("evaluation_labels_sent")
        is not False
        or multispan_scores.get("remote_inference_used") is not False
        or multispan_scores.get("input_contract", {}).get("evaluation_labels_sent")
        is not False
    ):
        raise V18CandidateError("Candidate inputs must be local and label-blind.")
    examples = {str(row["id"]): row for row in dataset.get("examples") or []}
    relations = {str(row["case_id"]): row for row in relation_scores.get("rows") or []}
    atomic = {str(row["case_id"]): row for row in atomic_scores.get("rows") or []}
    multispan = {str(row["case_id"]): row for row in multispan_scores.get("rows") or []}
    if not examples or not set(examples) == set(relations) == set(atomic) == set(
        multispan
    ):
        raise V18CandidateError("Candidate case IDs are empty or misaligned.")
    if any(
        {"label", "target", "verdict", "dataset"} & set(row["input"])
        for row in examples.values()
    ):
        raise V18CandidateError("Evaluation labels or metadata appear in model inputs.")
    case_ids = sorted(examples)
    return {
        "case_ids": case_ids,
        "examples": [examples[case_id] for case_id in case_ids],
        "relations": [relations[case_id] for case_id in case_ids],
        "atomic": [atomic[case_id] for case_id in case_ids],
        "multispan": [multispan[case_id] for case_id in case_ids],
    }
