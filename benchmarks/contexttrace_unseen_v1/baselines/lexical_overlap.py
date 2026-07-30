"""Deterministic lexical evidence-overlap sanity baseline."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contract import (
    BaselineInputError,
    canonical_sha256,
    iter_frozen_candidates,
)


BASELINE_ID = "lexical_evidence_overlap_v1"
BASELINE_VERSION = "1.0.0"
FROZEN_MANIFEST_PAYLOAD_SHA256 = (
    "8bf65cd7e2c95ccfcc12e78b580fc47e4157b0f808ba3fcace0a24bfcdc2e5f6"
)
_TOKEN_RE = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", flags=re.UNICODE)
_CITATION_RE = re.compile(r"\[[^\]\r\n]{1,256}\]")
_SENTENCE_RE = re.compile(r".+?(?:[.!?]+(?=\s+|$)|$)", flags=re.DOTALL)


def _tokens(text: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN_RE.finditer(text)}


def _claim_spans(answer: str) -> list[tuple[int, int, str]]:
    clean = _CITATION_RE.sub(lambda match: " " * len(match.group(0)), answer)
    spans: list[tuple[int, int, str]] = []
    for match in _SENTENCE_RE.finditer(clean):
        raw = match.group(0)
        start = match.start() + len(raw) - len(raw.lstrip())
        without_terminal = raw.rstrip()
        without_terminal = without_terminal.rstrip(".!?").rstrip()
        end = match.start() + len(without_terminal)
        text = clean[start:end]
        if not text:
            continue
        spans.append((start, end, text))
    if not spans and clean.strip():
        start = len(clean) - len(clean.lstrip())
        spans.append((start, len(clean.rstrip()), clean.strip()))
    return spans


def score_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Return continuous overlap scores; never invent unsupported root causes."""

    started = time.perf_counter()
    contexts = candidate.get("selected_contexts")
    if not isinstance(contexts, Sequence) or isinstance(contexts, (str, bytes)):
        raise BaselineInputError("selected_contexts must be a sequence.")

    context_tokens: list[tuple[str, set[str]]] = []
    for context in contexts:
        if not isinstance(context, Mapping):
            raise BaselineInputError("Each selected context must be an object.")
        context_tokens.append((str(context["chunk_id"]), _tokens(str(context["text"]))))

    claim_results: list[dict[str, Any]] = []
    for claim_index, (start, end, text) in enumerate(
        _claim_spans(str(candidate["answer"]))
    ):
        claim_tokens = _tokens(text)
        chunk_scores: list[tuple[str, float]] = []
        for chunk_id, tokens in context_tokens:
            coverage = (
                len(claim_tokens & tokens) / len(claim_tokens)
                if claim_tokens
                else 0.0
            )
            chunk_scores.append((chunk_id, coverage))
        best_chunk_id, best_coverage = max(
            chunk_scores,
            key=lambda item: (item[1], item[0]),
            default=("", 0.0),
        )
        union_tokens = set().union(*(tokens for _, tokens in context_tokens))
        union_coverage = (
            len(claim_tokens & union_tokens) / len(claim_tokens)
            if claim_tokens
            else 0.0
        )
        claim_results.append(
            {
                "claim_index": claim_index,
                "start": start,
                "end": end,
                "text": text,
                "token_count": len(claim_tokens),
                "best_context_id": best_chunk_id or None,
                "best_context_token_coverage": round(best_coverage, 12),
                "all_context_token_coverage": round(union_coverage, 12),
            }
        )

    coverages = [
        float(claim["all_context_token_coverage"]) for claim in claim_results
    ]
    result: dict[str, Any] = {
        "schema_version": "contexttrace-unseen-v1-baseline-output-1.0",
        "dataset_id": candidate["dataset_id"],
        "case_id": candidate["case_id"],
        "candidate_input_sha256": candidate["candidate_input_sha256"],
        "baseline_id": BASELINE_ID,
        "baseline_version": BASELINE_VERSION,
        "execution_class": "local_deterministic",
        "status": "completed",
        "scores": {
            "minimum_claim_token_coverage": round(min(coverages), 12)
            if coverages
            else None,
            "mean_claim_token_coverage": round(
                sum(coverages) / len(coverages), 12
            )
            if coverages
            else None,
        },
        "claims": claim_results,
        "failure_label": None,
        "root_cause": None,
        "unsupported_outputs": ["failure_label", "root_cause"],
        "model_calls": 0,
        "cost_usd": 0.0,
        "latency_ms": round((time.perf_counter() - started) * 1000, 6),
    }
    identity_view = dict(result)
    identity_view.pop("latency_ms")
    result["output_payload_sha256"] = canonical_sha256(identity_view)
    return result


def run_manifest(
    manifest_path: Path,
    artifact_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    candidates = iter_frozen_candidates(
        manifest_path,
        artifact_root,
        expected_payload_sha256=FROZEN_MANIFEST_PAYLOAD_SHA256,
    )
    outputs: list[dict[str, Any]] = []
    for candidate in candidates:
        outputs.append(score_candidate(candidate))

    record: dict[str, Any] = {
        "schema_version": "contexttrace-unseen-v1-baseline-run-1.0",
        "dataset_id": "ContextTrace-Unseen-v1",
        "baseline_id": BASELINE_ID,
        "baseline_version": BASELINE_VERSION,
        "frozen_manifest_payload_sha256": FROZEN_MANIFEST_PAYLOAD_SHA256,
        "case_count": len(outputs),
        "case_ids_sha256": canonical_sha256([row["case_id"] for row in outputs]),
        "outputs": outputs,
    }
    identity_record = dict(record)
    identity_record["outputs"] = [
        {key: value for key, value in row.items() if key != "latency_ms"}
        for row in outputs
    ]
    record["run_payload_sha256"] = canonical_sha256(identity_record)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return record


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--artifact-root",
        type=Path,
        required=True,
        help="Directory containing the manifest's traces/ directory.",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    record = run_manifest(args.manifest, args.artifact_root, args.output)
    print(
        json.dumps(
            {
                "baseline_id": record["baseline_id"],
                "case_count": record["case_count"],
                "run_payload_sha256": record["run_payload_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
