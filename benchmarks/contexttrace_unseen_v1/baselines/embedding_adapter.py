"""Pinned local sentence-embedding baseline; execution is an explicit later step."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Mapping

from .contract import BaselineInputError, canonical_sha256, iter_frozen_candidates
from .lexical_overlap import _claim_spans


BASELINE_ID = "minilm_cosine_support_v1"
BASELINE_VERSION = "1.0.0"
MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
FROZEN_MANIFEST_PAYLOAD_SHA256 = (
    "8bf65cd7e2c95ccfcc12e78b580fc47e4157b0f808ba3fcace0a24bfcdc2e5f6"
)


def score_candidate(
    candidate: Mapping[str, Any],
    *,
    model: Any | None = None,
) -> dict[str, Any]:
    """Score claim/context cosine similarity without assigning root causes."""

    try:
        from sentence_transformers import SentenceTransformer, util
    except ImportError as exc:
        raise BaselineInputError(
            "sentence-transformers==5.6.1 is required for the embedding baseline."
        ) from exc

    started = time.perf_counter()
    if model is None:
        model = SentenceTransformer(
            MODEL_ID,
            revision=MODEL_REVISION,
            local_files_only=True,
        )
    claims = [
        text
        for _, _, text in _claim_spans(
            re.sub(r"\[[^\]\r\n]{1,256}\]", " ", str(candidate["answer"]))
        )
    ]
    contexts = [str(item["text"]) for item in candidate["selected_contexts"]]
    if not claims or not contexts:
        raise BaselineInputError("Embedding baseline requires claims and contexts.")
    claim_vectors = model.encode(claims, convert_to_tensor=True, normalize_embeddings=True)
    context_vectors = model.encode(
        contexts, convert_to_tensor=True, normalize_embeddings=True
    )
    matrix = util.cos_sim(claim_vectors, context_vectors).cpu().tolist()
    per_claim = [
        {
            "claim_index": index,
            "maximum_context_cosine": round(max(row), 12),
            "best_context_id": candidate["selected_contexts"][
                max(range(len(row)), key=row.__getitem__)
            ]["chunk_id"],
        }
        for index, row in enumerate(matrix)
    ]
    similarities = [row["maximum_context_cosine"] for row in per_claim]
    result: dict[str, Any] = {
        "schema_version": "contexttrace-unseen-v1-baseline-output-1.0",
        "dataset_id": candidate["dataset_id"],
        "case_id": candidate["case_id"],
        "candidate_input_sha256": candidate["candidate_input_sha256"],
        "baseline_id": BASELINE_ID,
        "baseline_version": BASELINE_VERSION,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "execution_class": "local_model",
        "status": "completed",
        "scores": {
            "minimum_claim_context_cosine": round(min(similarities), 12),
            "mean_claim_context_cosine": round(
                sum(similarities) / len(similarities), 12
            ),
        },
        "claims": per_claim,
        "failure_label": None,
        "root_cause": None,
        "unsupported_outputs": ["failure_label", "root_cause"],
        "model_calls": 1,
        "cost_usd": 0.0,
        "latency_ms": round((time.perf_counter() - started) * 1000, 6),
    }
    identity = dict(result)
    identity.pop("latency_ms")
    result["output_payload_sha256"] = canonical_sha256(identity)
    return result


def run_manifest(
    manifest_path: Path,
    artifact_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise BaselineInputError(
            "sentence-transformers==5.6.1 is required for the embedding baseline."
        ) from exc
    model = SentenceTransformer(
        MODEL_ID,
        revision=MODEL_REVISION,
        local_files_only=True,
    )
    outputs = [
        score_candidate(candidate, model=model)
        for candidate in iter_frozen_candidates(
            manifest_path,
            artifact_root,
            expected_payload_sha256=FROZEN_MANIFEST_PAYLOAD_SHA256,
        )
    ]
    record: dict[str, Any] = {
        "schema_version": "contexttrace-unseen-v1-baseline-run-1.0",
        "dataset_id": "ContextTrace-Unseen-v1",
        "baseline_id": BASELINE_ID,
        "baseline_version": BASELINE_VERSION,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
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
    parser.add_argument("--artifact-root", type=Path, required=True)
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
