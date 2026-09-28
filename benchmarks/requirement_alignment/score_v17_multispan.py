"""Score improved atomic requirements over local evidence-span combinations."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import re
import statistics
import time
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.score_v12_relations import (
    _sha256_file,
    _sha256_json,
    _verify_artifact,
)
from contexttrace.verify.atomic_coverage import decompose_atomic_requirements
from contexttrace.verify.local_nli import LocalNLIJudge
from contexttrace.verify.local_quality import (
    decompose_material_claim,
    select_local_evidence,
)
from contexttrace.verify.schema import TraceContext
from contexttrace.verify.semantic_core_v2_1.claims import unitize_atomic_claims


DEVELOPMENT_SPLIT = "external_fiveway_v13_development"
CONFIRMATION_SPLIT = "external_fiveway_v19_confirmation"
V21_DEVELOPMENT_SPLIT = "external_fiveway_v21_development"
ALLOWED_SPLITS = {DEVELOPMENT_SPLIT, CONFIRMATION_SPLIT, V21_DEVELOPMENT_SPLIT}
RELATIONS = ("entailment", "contradiction", "neutral")
_FRAGMENT_START_RE = re.compile(
    r"^(?:and|but|that|which|who|whose|where|while|whereas|including|"
    r"featuring|making|becoming|causing|leading|resulting)\b",
    flags=re.IGNORECASE,
)


class V17ScoringError(RuntimeError):
    """Raised when V17 scoring violates its local development-only contract."""


def decompose_v17_requirements(
    claim: str, *, maximum: int = 8
) -> tuple[str, list[str]]:
    """Choose the most complete non-fragmentary deterministic decomposition."""

    candidates = {
        "semantic_core_v2_1": [
            unit.verification_text
            for unit in unitize_atomic_claims(claim, max_claims=maximum)[0]
        ],
        "local_quality": decompose_material_claim(claim),
        "atomic_coverage_v2": decompose_atomic_requirements(claim, maximum=maximum),
    }
    valid: list[tuple[int, int, str, list[str]]] = []
    preference = {
        "semantic_core_v2_1": 3,
        "local_quality": 2,
        "atomic_coverage_v2": 1,
    }
    for source, values in candidates.items():
        normalized = _normalized_requirements(values, maximum=maximum)
        if normalized and not any(_is_fragment(value) for value in normalized):
            valid.append((len(normalized), preference[source], source, normalized))
    if not valid:
        fallback = _normalized_requirements([claim], maximum=maximum)
        if not fallback:
            raise V17ScoringError("Claim did not produce a verifiable requirement.")
        return "whole_claim_fallback", fallback
    _, _, source, requirements = max(valid)
    return source, requirements


def score_multispan_requirements(
    dataset_path: str | Path,
    *,
    model_path: str | Path,
    model_manifest_path: str | Path,
    spans_per_requirement: int = 4,
    maximum_combination_size: int = 3,
) -> dict[str, Any]:
    if spans_per_requirement < 1:
        raise V17ScoringError("spans_per_requirement must be positive.")
    if not 1 <= maximum_combination_size <= spans_per_requirement:
        raise V17ScoringError(
            "maximum_combination_size must be between one and spans_per_requirement."
        )
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    try:
        import torch

        torch.set_num_threads(min(4, os.cpu_count() or 1))
    except ImportError:
        pass

    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    examples = list(dataset.get("examples") or [])
    split = str(dataset.get("split") or "")
    if split not in ALLOWED_SPLITS or not examples:
        raise V17ScoringError("V17 scoring accepts only frozen V13/V19 data.")
    if any(
        {"label", "target", "verdict", "dataset"} & set(row["input"])
        for row in examples
    ):
        raise V17ScoringError("Evaluation labels or metadata appear in model inputs.")

    artifact = _verify_artifact(Path(model_path), Path(model_manifest_path))
    nli = LocalNLIJudge(
        model_path=str(model_path),
        tokenizer_path=str(model_path),
        backend="transformers",
        max_length=256,
    )
    rows = []
    total_requirements = 0
    total_combinations = 0
    started = time.perf_counter()
    for example in examples:
        claim = str(example["input"]["claim"])
        source, requirements = decompose_v17_requirements(claim)
        contexts = [
            TraceContext(id=str(row["id"]), text=str(row["text"]))
            for row in example["input"]["evidence"]
        ]
        case_started = time.perf_counter()
        scored = [
            _score_requirement(
                requirement,
                query=str(example["input"].get("query") or ""),
                contexts=contexts,
                nli=nli,
                spans_per_requirement=spans_per_requirement,
                maximum_combination_size=maximum_combination_size,
            )
            for requirement in requirements
        ]
        total_requirements += len(scored)
        total_combinations += sum(len(row["combinations"]) for row in scored)
        rows.append(
            {
                "case_id": str(example["id"]),
                "input_sha256": _sha256_json(example["input"]),
                "latency_ms": round((time.perf_counter() - case_started) * 1000.0, 3),
                "decomposition_source": source,
                "requirements": scored,
            }
        )
    seconds = time.perf_counter() - started
    return {
        "schema_version": "contexttrace-v17-multispan-scores-1.0",
        "experiment": (
            "contexttrace_v21_domain_diverse_development"
            if split == V21_DEVELOPMENT_SPLIT
            else (
                "contexttrace_v19_untouched_confirmation"
                if split == CONFIRMATION_SPLIT
                else "contexttrace_v17_multispan_completeness"
            )
        ),
        "split": split,
        "dataset_sha256": _sha256_json(dataset),
        "cases": len(rows),
        "requirements": total_requirements,
        "combinations": total_combinations,
        "model": {
            "model_id": artifact["model_id"],
            "manifest_sha256": _sha256_file(Path(model_manifest_path)),
            "artifact_verified": True,
            "local_files_only": True,
        },
        "scoring_profile": {
            "spans_per_requirement": spans_per_requirement,
            "maximum_combination_size": maximum_combination_size,
            "decomposition_candidates": [
                "semantic_core_v2_1",
                "local_quality",
                "atomic_coverage_v2",
            ],
            "fragmentary_decompositions_rejected": True,
        },
        "latency": {
            "seconds": round(seconds, 4),
            "combinations_per_second": round(total_combinations / seconds, 4),
        },
        "input_contract": {
            "selected_evidence_only": True,
            "evaluation_labels_sent": False,
            "requirement_and_evidence_text_committed": False,
        },
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "local_only_network_calls": 0,
        "rows": rows,
    }


def _score_requirement(
    requirement: str,
    *,
    query: str,
    contexts: list[TraceContext],
    nli: LocalNLIJudge,
    spans_per_requirement: int,
    maximum_combination_size: int,
) -> dict[str, Any]:
    selected = select_local_evidence(
        query=query,
        claim=requirement,
        contexts=contexts,
        limit=spans_per_requirement,
    )
    combinations = []
    for size in range(1, min(maximum_combination_size, len(selected)) + 1):
        for indexes in itertools.combinations(range(len(selected)), size):
            texts = [selected[index].text for index in indexes]
            result = nli.verify_claim(
                query="",
                claim=requirement,
                contexts=[
                    TraceContext(
                        id="v17:" + "+".join(str(index) for index in indexes),
                        text="\n".join(texts),
                    )
                ],
            )
            scores = {
                relation: float(result.raw["nli_scores"][relation])
                for relation in RELATIONS
            }
            combinations.append(
                {
                    "size": size,
                    "selected_span_indexes": list(indexes),
                    "evidence_context_ids": [
                        str(selected[index].context_id) for index in indexes
                    ],
                    "evidence_text_sha256": [
                        hashlib.sha256(text.encode("utf-8")).hexdigest()
                        for text in texts
                    ],
                    "nli_scores": scores,
                    "nli_label": str(result.raw["nli_label"]),
                }
            )
    return {
        "requirement_sha256": hashlib.sha256(requirement.encode("utf-8")).hexdigest(),
        "selected_span_count": len(selected),
        "selected_span_sha256": [span.span_hash for span in selected],
        "combinations": combinations,
        "summary": _combination_summary(combinations),
    }


def _combination_summary(combinations: list[dict[str, Any]]) -> dict[str, Any]:
    if not combinations:
        return {
            "best_entailment": 0.0,
            "best_contradiction": 0.0,
            "best_neutral": 1.0,
            "best_single_entailment": 0.0,
            "best_pair_entailment": 0.0,
            "best_triple_entailment": 0.0,
            "best_entailment_combination_size": 0,
            "multispan_entailment_gain": 0.0,
            "mean_entailment": 0.0,
        }
    best = max(combinations, key=lambda row: row["nli_scores"]["entailment"])
    by_size = {
        size: [
            float(row["nli_scores"]["entailment"])
            for row in combinations
            if row["size"] == size
        ]
        for size in (1, 2, 3)
    }
    best_single = max(by_size[1], default=0.0)
    best_multi = max(by_size[2] + by_size[3], default=best_single)
    return {
        "best_entailment": max(
            float(row["nli_scores"]["entailment"]) for row in combinations
        ),
        "best_contradiction": max(
            float(row["nli_scores"]["contradiction"]) for row in combinations
        ),
        "best_neutral": max(
            float(row["nli_scores"]["neutral"]) for row in combinations
        ),
        "best_single_entailment": best_single,
        "best_pair_entailment": max(by_size[2], default=0.0),
        "best_triple_entailment": max(by_size[3], default=0.0),
        "best_entailment_combination_size": int(best["size"]),
        "multispan_entailment_gain": round(best_multi - best_single, 4),
        "mean_entailment": round(
            statistics.fmean(
                float(row["nli_scores"]["entailment"]) for row in combinations
            ),
            4,
        ),
    }


def _normalized_requirements(values: list[str], *, maximum: int) -> list[str]:
    output = []
    for value in values:
        normalized = " ".join(str(value or "").split()).strip(" ,")
        if len(normalized.split()) < 2:
            continue
        if normalized[-1:] not in ".!?":
            normalized += "."
        if normalized not in output:
            output.append(normalized)
        if len(output) == maximum:
            break
    return output


def _is_fragment(requirement: str) -> bool:
    return bool(_FRAGMENT_START_RE.match(requirement))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--spans-per-requirement", type=int, default=4)
    parser.add_argument("--maximum-combination-size", type=int, default=3)
    args = parser.parse_args(argv)
    result = score_multispan_requirements(
        args.dataset,
        model_path=args.model_path,
        model_manifest_path=args.model_manifest,
        spans_per_requirement=args.spans_per_requirement,
        maximum_combination_size=args.maximum_combination_size,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "cases": result["cases"],
                "requirements": result["requirements"],
                "combinations": result["combinations"],
                "latency": result["latency"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
