"""Fit and freeze the already-selected V14/V15/V17 development candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.v14_fiveway_policy import (
    LABELS,
    _candidates as v14_candidates,
    _matrix,
    _sha256_json,
)
from benchmarks.requirement_alignment.v15_atomic_completeness import (
    TARGET_LABELS,
    _aligned_inputs as v15_aligned_inputs,
    _candidates as v15_candidates,
    _feature_sets as v15_feature_sets,
)


class V18FreezeError(RuntimeError):
    """Raised when the selected development configuration cannot be frozen."""


def freeze_candidate(
    development: dict[str, Any],
    relation_scores: dict[str, Any],
    v14_report: dict[str, Any],
    atomic_scores: dict[str, Any],
    v15_report: dict[str, Any],
    v17_report: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    import joblib
    import numpy as np
    import sklearn

    v14_matrix, targets, case_ids, v14_feature_names = _matrix(
        development, relation_scores
    )
    v14_name = str(v14_report["selected"]["candidate"])
    v14_model = _named_estimator(v14_candidates(), v14_name)
    v14_model.fit(np.asarray(v14_matrix, dtype=float), np.asarray(targets))

    v15_inputs = v15_aligned_inputs(
        development, relation_scores, v14_report, atomic_scores
    )
    feature_set_name = str(v15_report["selected"]["feature_set"])
    feature_sets = {
        name: (matrix, names) for name, matrix, names in v15_feature_sets(v15_inputs)
    }
    if feature_set_name not in feature_sets:
        raise V18FreezeError("Selected V15 feature set is unavailable.")
    v15_matrix, v15_feature_names = feature_sets[feature_set_name]
    v15_name = str(v15_report["selected"]["estimator"])
    v15_model = _named_estimator(v15_candidates(), v15_name)
    binary_indexes = [
        index for index, target in enumerate(targets) if target in TARGET_LABELS
    ]
    binary_targets = np.asarray(
        [targets[index] == "supported" for index in binary_indexes]
    )
    v15_model.fit(np.asarray(v15_matrix, dtype=float)[binary_indexes], binary_targets)

    v14_policy = _policy_fields(
        v14_report["selected"]["policy"],
        (
            "support_probability_minimum",
            "contradiction_probability_maximum",
            "partial_or_ambiguous_probability_maximum",
        ),
    )
    v15_policy = _policy_fields(
        v15_report["selected"]["policy"],
        (
            "complete_support_probability_minimum",
            "contradiction_probability_maximum",
            "unverifiable_probability_maximum",
        ),
    )
    v17_policy = {
        "route_requirement": str(v17_report["selected"]["route_requirement"]),
        "minimum_single_span_entailment": float(
            v17_report["selected"]["minimum_single_span_entailment"]
        ),
        "threshold_source": str(v17_report["selected"]["threshold_source"]),
    }
    bundle = {
        "schema_version": "contexttrace-v18-frozen-candidate-1.0",
        "v14": {
            "candidate": v14_name,
            "labels": list(LABELS),
            "feature_names": v14_feature_names,
            "policy": v14_policy,
            "model": v14_model,
        },
        "v15": {
            "candidate": str(v15_report["selected"]["candidate"]),
            "estimator": v15_name,
            "feature_set": feature_set_name,
            "feature_names": v15_feature_names,
            "policy": v15_policy,
            "model": v15_model,
        },
        "v17": {
            "candidate": str(v17_report["selected"]["candidate"]),
            "policy": v17_policy,
        },
    }
    manifest = {
        "schema_version": "contexttrace-v18-frozen-candidate-manifest-1.0",
        "experiment": "contexttrace_v18_frozen_candidate",
        "status": "frozen_before_new_confirmation_data_access",
        "training": {
            "split": str(development["split"]),
            "cases": len(case_ids),
            "five_way_label_counts": {label: targets.count(label) for label in LABELS},
            "binary_completeness_cases": len(binary_indexes),
            "development_sha256": _sha256_json(development),
            "relation_rows_sha256": _sha256_json(relation_scores["rows"]),
            "atomic_rows_sha256": _sha256_json(
                [
                    {key: value for key, value in row.items() if key != "latency_ms"}
                    for row in atomic_scores["rows"]
                ]
            ),
        },
        "selection_reports": {
            "v14_rows_sha256": _sha256_json(v14_report["rows"]),
            "v15_rows_sha256": _sha256_json(v15_report["rows"]),
            "v17_rows_sha256": _sha256_json(v17_report["rows"]),
        },
        "candidate": {
            "v14": {
                "estimator": v14_name,
                "feature_count": len(v14_feature_names),
                "feature_names_sha256": _sha256_json(v14_feature_names),
                "policy": v14_policy,
            },
            "v15": {
                "estimator": v15_name,
                "feature_set": feature_set_name,
                "feature_count": len(v15_feature_names),
                "feature_names_sha256": _sha256_json(v15_feature_names),
                "policy": v15_policy,
            },
            "v17": v17_policy,
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
        },
        "protocol": {
            "configuration_changed_after_v17": False,
            "development_fitted_once": True,
            "confirmation_data_loaded": False,
            "confirmation_labels_loaded": False,
            "confirmation_predictions_inspected": False,
            "future_confirmation_retraining_allowed": False,
            "evaluation_labels_in_model_features": False,
        },
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }
    return bundle, manifest


def _named_estimator(candidates: list[tuple[str, Any]], name: str) -> Any:
    matches = [estimator for candidate, estimator in candidates if candidate == name]
    if len(matches) != 1:
        raise V18FreezeError("Selected estimator is missing or ambiguous: %s" % name)
    return matches[0]


def _policy_fields(source: dict[str, Any], names: tuple[str, ...]) -> dict[str, float]:
    if any(name not in source for name in names):
        raise V18FreezeError("Selected policy is missing a frozen threshold.")
    return {name: float(source[name]) for name in names}


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    import joblib

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", required=True)
    parser.add_argument("--relation-scores", required=True)
    parser.add_argument("--v14-report", required=True)
    parser.add_argument("--atomic-scores", required=True)
    parser.add_argument("--v15-report", required=True)
    parser.add_argument("--v17-report", required=True)
    parser.add_argument("--artifact-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    args = parser.parse_args(argv)
    bundle, manifest = freeze_candidate(
        _load(args.development),
        _load(args.relation_scores),
        _load(args.v14_report),
        _load(args.atomic_scores),
        _load(args.v15_report),
        _load(args.v17_report),
    )
    artifact = Path(args.artifact_output)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, artifact, compress=3)
    manifest["artifact"] = {
        "path": artifact.name,
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "bytes": artifact.stat().st_size,
        "format": "joblib",
        "trusted_local_artifact_only": True,
    }
    _write_json(Path(args.manifest_output), manifest)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "artifact": manifest["artifact"],
                "candidate": manifest["candidate"],
                "protocol": manifest["protocol"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
