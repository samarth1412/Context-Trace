"""Build V13 independent five-way development and held-out datasets."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from benchmarks.jev_v2_verification.run import shared_input


EXPERIMENT = "contexttrace_v13_independent_contradictions"
LABELS = (
    "supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "unverifiable",
)
SOURCE_HASHES = {
    "development": "b3cd60e5bea1c28f852b8ad8949aee135e8de5460b070f7811302db026b38f17",
    "heldout": "b50b90f40eddbad6b8ada051d8b223c7e04d408797148f755eba66b5796c75a3",
}
OUTPUT_SPLITS = {
    "development": "external_fiveway_v13_development",
    "heldout": "external_fiveway_v13_heldout",
}


class V13BuildError(RuntimeError):
    """Raised when the independent V13 data contract is violated."""


def build(
    development_path: str | Path,
    heldout_path: str | Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    development = _adapt(Path(development_path), expected_split="development")
    heldout = _adapt(Path(heldout_path), expected_split="heldout")
    development_ids = {row["id"] for row in development["examples"]}
    heldout_ids = {row["id"] for row in heldout["examples"]}
    development_claims = {_normalized_claim(row) for row in development["examples"]}
    heldout_claims = {_normalized_claim(row) for row in heldout["examples"]}
    development_inputs = {_sha256_json(row["input"]) for row in development["examples"]}
    heldout_inputs = {_sha256_json(row["input"]) for row in heldout["examples"]}
    checks = {
        "source_hashes_verified": True,
        "case_ids_disjoint": not bool(development_ids & heldout_ids),
        "normalized_claims_disjoint": not bool(development_claims & heldout_claims),
        "normalized_selected_inputs_disjoint": not bool(
            development_inputs & heldout_inputs
        ),
        "labels_absent_from_model_inputs": all(
            not ({"label", "target", "verdict", "dataset"} & set(row["input"]))
            for dataset in (development, heldout)
            for row in dataset["examples"]
        ),
        "selected_evidence_nonempty": all(
            bool(row["input"]["evidence"])
            for dataset in (development, heldout)
            for row in dataset["examples"]
        ),
        "heldout_predictions_used_for_selection": False,
    }
    required_true = {
        key: value
        for key, value in checks.items()
        if key != "heldout_predictions_used_for_selection"
    }
    if (
        not all(required_true.values())
        or checks["heldout_predictions_used_for_selection"] is not False
    ):
        raise V13BuildError(f"V13 split audit failed: {checks}")
    audit = {
        "schema_version": "contexttrace-v13-independent-audit-1.0",
        "experiment": EXPERIMENT,
        "counts": {
            split: _counts(dataset)
            for split, dataset in (
                ("development", development),
                ("heldout", heldout),
            )
        },
        "checks": checks,
        "limitations": [
            "The public source labels are mapped to ContextTrace verdicts rather than newly annotated.",
            "Public benchmark contamination in base-model pretraining cannot be ruled out.",
            "This resource is independent of V11 training and selection, but its source packs were used by earlier non-V11 ContextTrace experiments.",
        ],
    }
    manifest = {
        "schema_version": "contexttrace-v13-independent-manifest-1.0",
        "experiment": EXPERIMENT,
        "status": "heldout_frozen_before_v13_relation_scoring",
        "source_sha256": SOURCE_HASHES,
        "dataset_sha256": {
            "development": _sha256_json(development),
            "heldout": _sha256_json(heldout),
        },
        "audit_sha256": _sha256_json(audit),
        "development_labels_available_for_future_policy_selection": True,
        "heldout_labels_used_for_policy_selection": False,
        "v11_model_or_thresholds_changed": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
    }
    return development, heldout, audit, manifest


def _adapt(path: Path, *, expected_split: str) -> dict[str, Any]:
    if _sha256_file(path) != SOURCE_HASHES[expected_split]:
        raise V13BuildError(
            f"{expected_split} source pack does not match its frozen hash."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("split") != expected_split:
        raise V13BuildError(f"Expected {expected_split} source split.")
    cases = list(payload.get("cases") or [])
    if not cases:
        raise V13BuildError(f"The {expected_split} source pack is empty.")
    label_counts = Counter(str(case.get("expected_verdict")) for case in cases)
    if label_counts != Counter({label: 25 for label in LABELS}):
        raise V13BuildError(
            f"The {expected_split} source pack must contain 25 cases per verdict."
        )
    if payload.get("predictions_used_for_selection") is not False:
        raise V13BuildError(
            f"The {expected_split} source pack does not attest label-independent selection."
        )
    examples = []
    for case in cases:
        label = str(case.get("expected_verdict"))
        if label not in LABELS:
            raise V13BuildError(f"Unknown V13 verdict: {label}")
        selected, input_audit = shared_input(case)
        model_input = {
            "query": str(case.get("query") or ""),
            "claim": str(case["claim"]),
            "evidence": [
                {"id": context.id, "text": context.text} for context in selected
            ],
        }
        examples.append(
            {
                "id": str(case["id"]),
                "input": model_input,
                "target": {"verdict": label},
                "source": {
                    "dataset": str(case.get("dataset") or ""),
                    "label_scope": str(case.get("label_scope") or ""),
                    "source_split": str(case.get("source_split") or ""),
                    "selected_span_count": input_audit["selected_span_count"],
                },
            }
        )
    if len({row["id"] for row in examples}) != len(examples):
        raise V13BuildError(f"The {expected_split} pack contains duplicate case IDs.")
    return {
        "schema_version": "contexttrace-v13-independent-dataset-1.0",
        "experiment": EXPERIMENT,
        "split": OUTPUT_SPLITS[expected_split],
        "source": {
            "dataset": "WiCE+VitaminC+AmbiEnt",
            "source_file": path.name,
            "source_sha256": SOURCE_HASHES[expected_split],
            "selected_evidence_only": True,
        },
        "examples": examples,
    }


def _counts(dataset: dict[str, Any]) -> dict[str, Any]:
    rows = dataset["examples"]
    return {
        "cases": len(rows),
        "labels": dict(
            sorted(Counter(row["target"]["verdict"] for row in rows).items())
        ),
        "datasets": dict(
            sorted(Counter(row["source"]["dataset"] for row in rows).items())
        ),
        "selected_evidence_spans": sum(len(row["input"]["evidence"]) for row in rows),
    }


def _normalized_claim(row: dict[str, Any]) -> str:
    return " ".join(str(row["input"]["claim"]).casefold().split())


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _write(path: str | Path, value: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-source", required=True)
    parser.add_argument("--heldout-source", required=True)
    parser.add_argument("--development-output", required=True)
    parser.add_argument("--heldout-output", required=True)
    parser.add_argument("--audit-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    args = parser.parse_args(argv)
    values = build(args.development_source, args.heldout_source)
    for path, value in zip(
        (
            args.development_output,
            args.heldout_output,
            args.audit_output,
            args.manifest_output,
        ),
        values,
        strict=True,
    ):
        _write(path, value)
    print(
        json.dumps(
            {"counts": values[2]["counts"], "checks": values[2]["checks"]}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
