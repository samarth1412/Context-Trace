"""Frozen adapter for the unchanged semantic_v1_calibrated comparator."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Mapping

from contexttrace.contracts import VERIFIER_VERSION
from contexttrace.verify.runner import FULL_VERIFICATION_PROFILE, verify_trace
from contexttrace.verify.schema import RAGTrace, TraceCitation, TraceContext

from .contract import BaselineInputError, canonical_sha256, iter_frozen_candidates


BASELINE_ID = "semantic_v1_calibrated"
BASELINE_VERSION = "semantic_v1_calibrated"
FACTS_SOURCE_SHA256 = (
    "4fa507db2126423c8d0787811e78d0d6ffecf5d7603828b6a6d9b23ca8207bc4"
)
FROZEN_MANIFEST_PAYLOAD_SHA256 = (
    "8bf65cd7e2c95ccfcc12e78b580fc47e4157b0f808ba3fcace0a24bfcdc2e5f6"
)
_INLINE_CITATION_RE = re.compile(r"\[([^\]\r\n]{1,256})\]")


def _sentence_for_offset(answer: str, offset: int) -> str:
    start = max(answer.rfind(".", 0, offset), answer.rfind("!", 0, offset), answer.rfind("?", 0, offset))
    end_candidates = [
        position
        for mark in ".!?"
        if (position := answer.find(mark, offset)) >= 0
    ]
    end = min(end_candidates) + 1 if end_candidates else len(answer)
    return answer[start + 1 : end].strip()


def prepare_trace(candidate: Mapping[str, Any]) -> RAGTrace:
    if VERIFIER_VERSION != BASELINE_VERSION:
        raise BaselineInputError(
            f"Expected {BASELINE_VERSION}, found {VERIFIER_VERSION}; refusing substitution."
        )
    answer = str(candidate["answer"])
    citations = [
        TraceCitation(
            claim=_sentence_for_offset(answer, match.start()),
            source_id=match.group(1),
            metadata={"adapter": "inline_bracket_citation_v1"},
        )
        for match in _INLINE_CITATION_RE.finditer(answer)
    ]
    return RAGTrace(
        query=str(candidate["query"]),
        answer=answer,
        contexts=[
            TraceContext(
                id=str(context["chunk_id"]),
                text=str(context["text"]),
                metadata={"source_id": context["source_id"]},
            )
            for context in candidate["selected_contexts"]
        ],
        citations=citations,
        metadata={
            "dataset_id": candidate["dataset_id"],
            "case_id": candidate["case_id"],
            "candidate_input_sha256": candidate["candidate_input_sha256"],
            "adapter": "contexttrace-unseen-v1-semantic-v1-adapter-1.0",
        },
    )


def score_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    raw_output = verify_trace(
        prepare_trace(candidate),
        mode="semantic",
        profile=FULL_VERIFICATION_PROFILE,
    )
    result: dict[str, Any] = {
        "schema_version": "contexttrace-unseen-v1-baseline-output-1.0",
        "dataset_id": candidate["dataset_id"],
        "case_id": candidate["case_id"],
        "candidate_input_sha256": candidate["candidate_input_sha256"],
        "baseline_id": BASELINE_ID,
        "baseline_version": BASELINE_VERSION,
        "facts_source_sha256": FACTS_SOURCE_SHA256,
        "execution_class": "local_deterministic",
        "status": "completed",
        "model_calls": 0,
        "cost_usd": 0.0,
        "latency_ms": round((time.perf_counter() - started) * 1000, 6),
        "raw_output": raw_output,
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
    outputs = [
        score_candidate(candidate)
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
        "facts_source_sha256": FACTS_SOURCE_SHA256,
        "profile": FULL_VERIFICATION_PROFILE.to_dict(),
        "mode": "semantic",
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
