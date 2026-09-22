"""Run a post-hoc fine-grid threshold diagnostic for the selected v3 model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.train import binary_metrics
from benchmarks.requirement_alignment.train import binary_targets
from benchmarks.requirement_alignment.train_v2 import verify_source_model
from benchmarks.requirement_alignment.train_v3 import FALSE_POSITIVE_CAP
from benchmarks.requirement_alignment.train_v3 import WICE_RECALL_FLOOR
from benchmarks.requirement_alignment.train_v3 import _BinaryEncodedExamples
from benchmarks.requirement_alignment.train_v3 import _predict_entailment


def fine_threshold_diagnostic(
    contract_examples: list[dict[str, Any]],
    contract_probabilities: list[float],
    wice_examples: list[dict[str, Any]],
    wice_probabilities: list[float],
) -> dict[str, Any]:
    contract_targets = binary_targets(contract_examples)
    wice_targets = binary_targets(wice_examples)
    candidates = []
    for value in range(800, 951):
        threshold = value / 1000
        contract = binary_metrics(
            contract_targets, contract_probabilities, threshold=threshold
        )
        wice = binary_metrics(wice_targets, wice_probabilities, threshold=threshold)
        eligible = (
            contract["false_positive_rate"] <= FALSE_POSITIVE_CAP
            and wice["false_positive_rate"] <= FALSE_POSITIVE_CAP
            and wice["positive_recall"] >= WICE_RECALL_FLOOR
        )
        candidates.append(
            {
                "threshold": threshold,
                "eligible": eligible,
                "contract_development": contract,
                "wice_internal": wice,
            }
        )
    eligible = [row for row in candidates if row["eligible"]]
    selected = max(
        eligible,
        key=lambda row: (
            row["contract_development"]["positive_recall"],
            row["wice_internal"]["positive_recall"],
            row["contract_development"]["macro_f1"],
            row["threshold"],
        ),
    )
    false_support = []
    threshold = float(selected["threshold"])
    for row, probability in zip(
        contract_examples, contract_probabilities, strict=True
    ):
        if row["target"]["label"] == "missing" and probability >= threshold:
            false_support.append(
                {
                    "id": row["id"],
                    "relation": row["source"]["relation"],
                    "hypothesis_id": row["source"]["hypothesis_id"],
                    "hypothesis_description": row["source"][
                        "hypothesis_description"
                    ],
                    "covered_probability": round(probability, 6),
                    "evidence_span_indexes": row["source"]["evidence_span_indexes"],
                }
            )
    return {
        "schema_version": "contexttrace-requirement-v3-threshold-diagnostic-1.0",
        "warning": "Post-hoc development diagnostic; cannot satisfy or change the promotion gate.",
        "range": {"minimum": 0.8, "maximum": 0.95, "step": 0.001},
        "eligible_thresholds": len(eligible),
        "best_eligible": selected,
        "contract_recall_target_met": (
            selected["contract_development"]["positive_recall"] >= 0.50
        ),
        "contract_false_support_at_best": false_support,
    }


def run_diagnostic(
    *,
    model_path: str | Path,
    model_manifest_path: str | Path,
    contract_development_path: str | Path,
    wice_dataset_path: str | Path,
    batch_size: int = 8,
) -> dict[str, Any]:
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    manifest = verify_source_model(model_path, model_manifest_path)
    contract_examples = json.loads(
        Path(contract_development_path).read_text(encoding="utf-8")
    )["examples"]
    wice_examples = [
        row
        for row in json.loads(Path(wice_dataset_path).read_text(encoding="utf-8"))[
            "examples"
        ]
        if row["split"] == "internal_validation"
        and row["task"] == "claim_group_completeness"
        and row["source"]["construction"]
        in {"gold_complete_group", "gold_partial_group"}
    ]
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    separator = str(tokenizer.sep_token or "[SEP]")
    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_path), local_files_only=True
    )

    def predict(rows: list[dict[str, Any]]) -> list[float]:
        dataset = _BinaryEncodedExamples(
            rows, tokenizer=tokenizer, separator=separator
        )
        return _predict_entailment(
            model,
            DataLoader(dataset, batch_size=batch_size, shuffle=False),
            torch=torch,
        )

    output = fine_threshold_diagnostic(
        contract_examples,
        predict(contract_examples),
        wice_examples,
        predict(wice_examples),
    )
    output["model_id"] = manifest["model_id"]
    output["model_artifact_verified"] = True
    output["contract_test_split_accessed"] = False
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-manifest", required=True)
    parser.add_argument("--contract-development", required=True)
    parser.add_argument("--wice-dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args(argv)
    report = run_diagnostic(
        model_path=args.model_path,
        model_manifest_path=args.model_manifest,
        contract_development_path=args.contract_development,
        wice_dataset_path=args.wice_dataset,
        batch_size=args.batch_size,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
