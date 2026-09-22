"""Run pinned MiniCheck on the Jev-v2 shared claim-evidence inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .run import _percentile, _write_json, load_case_pack, shared_input


MINICHECK_SOURCE_COMMIT = "b58b9fa69acbd1015ec970fa65dd752413a053d2"


@dataclass(frozen=True)
class MiniCheckModelSpec:
    model_name: str
    repository: str
    revision: str
    weight_filename: str
    weight_bytes: int
    weight_sha256: str
    required_files: tuple[str, ...]
    input_prefix: str = ""


MINICHECK_MODELS = {
    "flan-t5-large": MiniCheckModelSpec(
        model_name="flan-t5-large",
        repository="lytang/MiniCheck-Flan-T5-Large",
        revision="96eafd01cee2d16cf81aaa2fb226b14f422a37b3",
        weight_filename="pytorch_model.bin",
        weight_bytes=3_132_786_242,
        weight_sha256="41291881e13c6235ed47149cec903bee9493e45d9d7325587a9fa2e266c526c0",
        required_files=(
            "config.json",
            "generation_config.json",
            "pytorch_model.bin",
            "tokenizer_config.json",
        ),
        input_prefix="predict: ",
    ),
    "roberta-large": MiniCheckModelSpec(
        model_name="roberta-large",
        repository="lytang/MiniCheck-RoBERTa-Large",
        revision="74c8919647e61ed0f71bc177d94f10930f090068",
        weight_filename="pytorch_model.bin",
        weight_bytes=1_421_577_710,
        weight_sha256="67af45a2d5a2706283821049232c7d7c81cea22e81dfdbb7097487a98bc61b53",
        required_files=(
            "config.json",
            "pytorch_model.bin",
            "tokenizer.json",
            "tokenizer_config.json",
        ),
    ),
}

# Backward-compatible aliases for the original, default Flan baseline.
MINICHECK_MODEL_NAME = "flan-t5-large"
MINICHECK_MODEL_REPO = MINICHECK_MODELS[MINICHECK_MODEL_NAME].repository
MINICHECK_MODEL_REVISION = MINICHECK_MODELS[MINICHECK_MODEL_NAME].revision
MINICHECK_MODEL_BYTES = MINICHECK_MODELS[MINICHECK_MODEL_NAME].weight_bytes
MINICHECK_MODEL_SHA256 = MINICHECK_MODELS[MINICHECK_MODEL_NAME].weight_sha256


class MiniCheckBaselineError(RuntimeError):
    """Raised when the pinned, offline MiniCheck baseline cannot run safely."""


@dataclass(frozen=True)
class MiniCheckOutput:
    support_probability: float
    latency_ms: float
    input_tokens: int | None
    used_chunks: tuple[dict[str, Any], ...]


class MiniCheckScorer(Protocol):
    model_metadata: dict[str, Any]

    def score_one(self, *, document: str, claim: str) -> MiniCheckOutput: ...


class OfficialMiniCheckScorer:
    """Thin offline-only wrapper around the official MiniCheck package API."""

    def __init__(
        self,
        *,
        cache_dir: str | Path,
        nltk_data: str | Path,
        batch_size: int = 4,
        model_name: str = MINICHECK_MODEL_NAME,
    ) -> None:
        try:
            model_spec = MINICHECK_MODELS[model_name]
        except KeyError as exc:
            raise MiniCheckBaselineError("Unsupported MiniCheck model: %s." % model_name) from exc
        cache = Path(cache_dir).resolve()
        nltk_root = Path(nltk_data).resolve()
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["NLTK_DATA"] = str(nltk_root)
        _prepare_pinned_model_cache(cache, model_spec=model_spec)
        _verify_nltk_data(nltk_root)

        try:
            from minicheck.minicheck import MiniCheck
        except ImportError as exc:
            raise MiniCheckBaselineError(
                "Install the pinned official MiniCheck source before running this baseline."
            ) from exc

        self._scorer = MiniCheck(
            model_name=model_spec.model_name,
            batch_size=batch_size,
            cache_dir=str(cache),
        )
        self.model_metadata = {
            "provider": "official_minicheck",
            "package_version": "0.1.0",
            "source_commit": MINICHECK_SOURCE_COMMIT,
            "model_name": model_spec.model_name,
            "model_repo": model_spec.repository,
            "resolved_model_revision": model_spec.revision,
            "weight_filename": model_spec.weight_filename,
            "weight_bytes": model_spec.weight_bytes,
            "weight_sha256": model_spec.weight_sha256,
            "cache_dir_name": cache.name,
            "automatic_download": False,
            "remote_inference": False,
        }
        self._model_spec = model_spec

    def score_one(self, *, document: str, claim: str) -> MiniCheckOutput:
        started = time.perf_counter()
        _, probabilities, chunks, per_chunk = self._scorer.score(
            docs=[document],
            claims=[claim],
        )
        latency = (time.perf_counter() - started) * 1000.0
        probability = float(probabilities[0])
        used_chunks = list(chunks[0])
        chunk_probabilities = [float(value) for value in per_chunk[0]]
        records = tuple(
            {
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "characters": len(text),
                "support_probability": chunk_probability,
            }
            for text, chunk_probability in zip(used_chunks, chunk_probabilities, strict=True)
        )
        tokenizer = self._scorer.model.tokenizer
        input_tokens = sum(
            len(
                tokenizer(
                    self._model_spec.input_prefix + tokenizer.eos_token.join([chunk, claim]),
                    add_special_tokens=True,
                    truncation=True,
                    max_length=self._scorer.model.max_model_len,
                )["input_ids"]
            )
            for chunk in used_chunks
        )
        return MiniCheckOutput(
            support_probability=probability,
            latency_ms=round(latency, 3),
            input_tokens=input_tokens,
            used_chunks=records,
        )


def run_minicheck(
    cases: list[dict[str, Any]],
    *,
    split_metadata: dict[str, Any],
    scorer: MiniCheckScorer,
    threshold: float = 0.5,
    checkpoint: str | Path | None = None,
) -> dict[str, Any]:
    if not 0.0 <= threshold <= 1.0:
        raise MiniCheckBaselineError("threshold must be between 0 and 1.")
    rows: list[dict[str, Any]] = []
    result: dict[str, Any] = {}
    for case in cases:
        contexts, input_audit = shared_input(case)
        document = "\n\n".join(context.text for context in contexts)
        output = scorer.score_one(document=document, claim=str(case["claim"]))
        probability = output.support_probability
        if not 0.0 <= probability <= 1.0:
            raise MiniCheckBaselineError("MiniCheck returned a probability outside [0, 1].")
        predicted = "supported" if probability > threshold else "not_supported"
        gold = "supported" if case["expected_verdict"] == "supported" else "not_supported"
        rows.append(
            {
                "case_id": case["id"],
                "five_way_gold": case["expected_verdict"],
                "binary_gold": gold,
                "input_audit": input_audit,
                "document_sha256": hashlib.sha256(document.encode("utf-8")).hexdigest(),
                "prediction": {
                    "label": predicted,
                    "threshold": threshold,
                    "probabilities": {
                        "supported": probability,
                        "not_supported": 1.0 - probability,
                    },
                    "confidence": max(probability, 1.0 - probability),
                    "confidence_semantics": "minicheck_binary_support_probability",
                    "latency_ms": output.latency_ms,
                    "input_tokens": output.input_tokens,
                    "used_chunks": list(output.used_chunks),
                    "explanation": None,
                    "matched_facts": [],
                    "evidence_spans": [],
                },
            }
        )
        result = _result(
            rows,
            split_metadata=split_metadata,
            model_metadata=scorer.model_metadata,
            threshold=threshold,
        )
        if checkpoint is not None:
            _write_json(Path(checkpoint), result)
    return result


def _result(
    rows: list[dict[str, Any]],
    *,
    split_metadata: dict[str, Any],
    model_metadata: dict[str, Any],
    threshold: float,
) -> dict[str, Any]:
    return {
        "experiment": "contexttrace_minicheck_shared_input_binary",
        "schema_version": "1.0",
        "split": split_metadata,
        "cases_completed": len(rows),
        "task": {
            "type": "binary_grounding",
            "positive_label": "supported",
            "negative_label": "not_supported",
            "negative_source_labels": [
                "partially_supported",
                "unsupported",
                "contradicted",
                "unverifiable",
            ],
            "threshold": threshold,
            "five_way_comparison_allowed": False,
            "reason": "MiniCheck is a binary sentence-level grounding checker.",
        },
        "model": dict(model_metadata),
        "input_contract": {
            "same_selector_as_jev_v2": True,
            "evaluation_labels_sent": False,
            "sent_fields": ["claim", "selected_evidence"],
            "query_used_by_shared_selector_only": True,
            "no_generated_explanations_or_evidence_spans": True,
        },
        "stable_defaults_changed": False,
        "metrics": binary_metrics(rows),
        "rows": rows,
    }


def binary_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = ("supported", "not_supported")
    confusion = {gold: {predicted: 0 for predicted in labels} for gold in labels}
    dangerous = []
    false_rejections = []
    latencies = []
    brier = []
    ece_rows = []
    tokens = []
    five_way: dict[str, dict[str, int]] = {}
    for row in rows:
        gold = row["binary_gold"]
        prediction = row["prediction"]
        predicted = prediction["label"]
        probability = float(prediction["probabilities"]["supported"])
        confusion[gold][predicted] += 1
        latencies.append(float(prediction["latency_ms"]))
        brier.append((probability - float(gold == "supported")) ** 2)
        ece_rows.append((max(probability, 1.0 - probability), predicted == gold))
        if prediction["input_tokens"] is not None:
            tokens.append(int(prediction["input_tokens"]))
        source_label = row.get("five_way_gold")
        if source_label is not None:
            bucket = five_way.setdefault(
                str(source_label), {"cases": 0, "predicted_supported": 0}
            )
            bucket["cases"] += 1
            bucket["predicted_supported"] += int(predicted == "supported")
        if gold == "not_supported" and predicted == "supported":
            dangerous.append(str(row["case_id"]))
        if gold == "supported" and predicted == "not_supported":
            false_rejections.append(str(row["case_id"]))

    per_label = {}
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in labels if other != label)
        fn = sum(confusion[label][other] for other in labels if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {
            "support": sum(confusion[label].values()),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    correct = sum(confusion[label][label] for label in labels)
    recalls = [per_label[label]["recall"] for label in labels]
    supported_total = sum(confusion["supported"].values())
    negative_total = sum(confusion["not_supported"].values())
    return {
        "cases": len(rows),
        "accuracy": round(correct / len(rows), 4) if rows else None,
        "balanced_accuracy": round(statistics.fmean(recalls), 4) if rows else None,
        "macro_f1": round(statistics.fmean(per_label[label]["f1"] for label in labels), 4)
        if rows
        else None,
        "per_label": per_label,
        "confusion": confusion,
        "dangerous_false_support": {
            "count": len(dangerous),
            "denominator_not_supported": negative_total,
            "rate": round(len(dangerous) / negative_total, 4) if negative_total else None,
            "case_ids": dangerous,
        },
        "false_rejection_of_supported": {
            "count": len(false_rejections),
            "denominator_supported": supported_total,
            "rate": round(len(false_rejections) / supported_total, 4) if supported_total else None,
            "case_ids": false_rejections,
        },
        "by_five_way_gold": {
            label: {
                **counts,
                "predicted_supported_rate": round(
                    counts["predicted_supported"] / counts["cases"], 4
                ),
            }
            for label, counts in sorted(five_way.items())
        },
        "probability_quality": {
            "binary_brier": round(statistics.fmean(brier), 6) if brier else None,
            "top_label_ece_10_bins": _ece(ece_rows, bins=10),
        },
        "latency_ms": {
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
            "mean": round(statistics.fmean(latencies), 3) if latencies else None,
        },
        "input_tokens": {
            "total": sum(tokens) if tokens else None,
            "mean": round(statistics.fmean(tokens), 3) if tokens else None,
        },
    }


def compare_with_five_way_baseline(
    minicheck_result: dict[str, Any],
    baseline_result: dict[str, Any],
    *,
    variants: tuple[str, ...] = ("stable_semantic", "jev"),
) -> dict[str, Any]:
    """Compare binary MiniCheck decisions with five-way results on identical inputs."""

    baseline_rows = {str(row["case_id"]): row for row in baseline_result["rows"]}
    minicheck_rows = {str(row["case_id"]): row for row in minicheck_result["rows"]}
    if set(baseline_rows) != set(minicheck_rows):
        raise MiniCheckBaselineError("MiniCheck and baseline case IDs do not match.")

    comparisons: dict[str, Any] = {}
    for variant in variants:
        disagreements = []
        counts = {
            "cases": 0,
            "agreements": 0,
            "both_correct": 0,
            "minicheck_only_correct": 0,
            "baseline_only_correct": 0,
            "both_wrong": 0,
        }
        for case_id, minicheck_row in minicheck_rows.items():
            baseline_row = baseline_rows[case_id]
            if (
                minicheck_row["input_audit"]["input_sha256"]
                != baseline_row["input_audit"]["input_sha256"]
            ):
                raise MiniCheckBaselineError(
                    "MiniCheck and baseline selected inputs differ for %s." % case_id
                )
            prediction = baseline_row.get("predictions", {}).get(variant)
            if prediction is None:
                continue
            gold = minicheck_row["binary_gold"]
            minicheck_label = minicheck_row["prediction"]["label"]
            baseline_label = (
                "supported" if prediction["verdict"] == "supported" else "not_supported"
            )
            minicheck_correct = minicheck_label == gold
            baseline_correct = baseline_label == gold
            counts["cases"] += 1
            counts["agreements"] += int(minicheck_label == baseline_label)
            if minicheck_correct and baseline_correct:
                counts["both_correct"] += 1
            elif minicheck_correct:
                counts["minicheck_only_correct"] += 1
            elif baseline_correct:
                counts["baseline_only_correct"] += 1
            else:
                counts["both_wrong"] += 1
            if minicheck_label != baseline_label:
                disagreements.append(
                    {
                        "case_id": case_id,
                        "five_way_gold": minicheck_row["five_way_gold"],
                        "binary_gold": gold,
                        "minicheck": minicheck_label,
                        "baseline_binary": baseline_label,
                        "baseline_five_way": prediction["verdict"],
                    }
                )
        if counts["cases"]:
            comparisons[variant] = {
                **counts,
                "agreement_rate": round(counts["agreements"] / counts["cases"], 4),
                "disagreements": disagreements,
            }
    return {
        "binary_mapping": "supported versus every other existing verdict",
        "exact_case_ids_and_selected_inputs_required": True,
        "variants": comparisons,
    }


def _ece(rows: list[tuple[float, bool]], *, bins: int) -> float | None:
    if not rows:
        return None
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for confidence, correct in rows:
        buckets[min(bins - 1, int(confidence * bins))].append((confidence, correct))
    value = 0.0
    for bucket in buckets:
        if bucket:
            confidence = statistics.fmean(item[0] for item in bucket)
            accuracy = statistics.fmean(float(item[1]) for item in bucket)
            value += len(bucket) / len(rows) * abs(accuracy - confidence)
    return round(value, 6)


def _prepare_pinned_model_cache(
    cache_dir: str | Path,
    *,
    model_spec: MiniCheckModelSpec | None = None,
    expected_weight_bytes: int | None = None,
    expected_weight_sha256: str | None = None,
) -> None:
    model_spec = model_spec or MINICHECK_MODELS[MINICHECK_MODEL_NAME]
    expected_weight_bytes = (
        model_spec.weight_bytes if expected_weight_bytes is None else expected_weight_bytes
    )
    expected_weight_sha256 = (
        model_spec.weight_sha256 if expected_weight_sha256 is None else expected_weight_sha256
    )
    cache_dir = Path(cache_dir)
    repository = cache_dir / ("models--" + model_spec.repository.replace("/", "--"))
    snapshot = repository / "snapshots" / model_spec.revision
    missing = [name for name in model_spec.required_files if not (snapshot / name).exists()]
    if missing:
        raise MiniCheckBaselineError(
            "Pinned MiniCheck snapshot is incomplete: %s. Run the pinned hf download command in README.md."
            % ", ".join(missing)
        )
    weight = snapshot / model_spec.weight_filename
    actual_bytes = weight.stat().st_size
    if actual_bytes != expected_weight_bytes:
        raise MiniCheckBaselineError(
            "MiniCheck weight size mismatch: expected %s bytes, found %s."
            % (expected_weight_bytes, actual_bytes)
        )
    actual_sha256 = _sha256_file(weight)
    if actual_sha256 != expected_weight_sha256:
        raise MiniCheckBaselineError(
            "MiniCheck weight SHA-256 mismatch: expected %s, found %s."
            % (expected_weight_sha256, actual_sha256)
        )
    ref = repository / "refs" / "main"
    if ref.is_file() and ref.read_text(encoding="utf-8").strip() != model_spec.revision:
        raise MiniCheckBaselineError(
            "MiniCheck model revision mismatch: expected %s, found %s."
            % (model_spec.revision, ref.read_text(encoding="utf-8").strip())
        )
    ref.parent.mkdir(parents=True, exist_ok=True)
    # huggingface_hub resolves this file verbatim and does not strip whitespace.
    ref.write_text(model_spec.revision, encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_nltk_data(nltk_data: Path) -> None:
    try:
        import nltk
    except ImportError as exc:
        raise MiniCheckBaselineError("nltk is required by the official MiniCheck package.") from exc
    if str(nltk_data) not in nltk.data.path:
        nltk.data.path.insert(0, str(nltk_data))
    missing = []
    for resource in ("tokenizers/punkt", "tokenizers/punkt_tab/english"):
        try:
            nltk.data.find(resource, paths=[str(nltk_data)])
        except LookupError:
            missing.append(resource)
    if missing:
        raise MiniCheckBaselineError(
            "NLTK resources are missing (%s). Run the pinned local resource command in README.md."
            % ", ".join(missing)
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--split", choices=("development", "heldout"), required=True)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--nltk-data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--model", choices=tuple(MINICHECK_MODELS), default=MINICHECK_MODEL_NAME)
    parser.add_argument(
        "--baseline-results",
        help="Optional Jev-v2 result JSON for exact-input binary disagreement reporting.",
    )
    args = parser.parse_args(argv)

    split_metadata, cases = load_case_pack(args.cases, expected_split=args.split)
    scorer = OfficialMiniCheckScorer(
        cache_dir=args.cache_dir,
        nltk_data=args.nltk_data,
        batch_size=args.batch_size,
        model_name=args.model,
    )
    result = run_minicheck(
        cases,
        split_metadata=split_metadata,
        scorer=scorer,
        threshold=args.threshold,
        checkpoint=args.output,
    )
    if args.baseline_results:
        baseline_result = json.loads(Path(args.baseline_results).read_text(encoding="utf-8"))
        result["baseline_comparison"] = compare_with_five_way_baseline(
            result,
            baseline_result,
        )
    _write_json(Path(args.output), result)
    print(json.dumps({"output": args.output, "metrics": result["metrics"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
