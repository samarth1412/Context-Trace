"""Run the frozen candidate and ablations without accepting any gold input."""

from __future__ import annotations

import argparse
import json
import platform
import re
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from contexttrace.verify.schema import RAGTrace, TraceCitation, TraceContext
from contexttrace.verify.semantic_core_v2 import verify_trace_v2
from contexttrace.verify.semantic_core_v2.nli import build_pinned_nli
from contexttrace.verify.semantic_core_v2.profile import profile_for_id

from benchmarks.contexttrace_unseen_v1.baselines.contract import (
    iter_frozen_candidates,
)

from .integrity import (
    EvaluationIntegrityError,
    canonical_sha256,
    file_sha256,
    load_json_object,
    require_execution_authorization,
    verify_phase6_locks,
    verify_runtime_environment,
)


RUN_SCHEMA_VERSION = "contexttrace-unseen-v1-candidate-run-1.0"
_INLINE_CITATION_RE = re.compile(r"\[([^\]\r\n]{1,256})\]")
_URL_CITATION_RE = re.compile(r"https?://[^\s<>\]\[\"')]+")


def _source_condition(source: Mapping[str, Any]) -> str:
    conditions = {str(item).casefold() for item in source.get("source_conditions", [])}
    for source_value, candidate_value in (
        ("superseded", "superseded"),
        ("stale", "stale"),
        ("archived", "stale"),
        ("low_authority", "low_authority"),
        ("conflicting", "conflicting_authorities"),
        ("noncanonical", "current_noncanonical"),
    ):
        if source_value in conditions:
            return candidate_value
    if "current" in conditions and "canonical" in conditions:
        return "current_canonical"
    return "unknown"


def _source_index(source_manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    sources = source_manifest.get("sources")
    if not isinstance(sources, list):
        raise EvaluationIntegrityError("Source manifest has no sources list.")
    index: dict[str, dict[str, Any]] = {}
    for source in sources:
        if not isinstance(source, Mapping) or not source.get("source_id"):
            raise EvaluationIntegrityError("Source manifest contains an invalid row.")
        source_id = str(source["source_id"])
        if source_id in index:
            raise EvaluationIntegrityError(f"Duplicate source ID: {source_id}.")
        metadata = dict(source.get("metadata") or {})
        metadata.update(
            {
                "source_id": source_id,
                "source_snapshot_id": source.get("snapshot_sha256"),
                "source_condition": _source_condition(source),
                "published_at": source.get("published_at"),
                "authority_basis": source.get("authority_basis"),
                "source_url": source.get("source_url"),
                "canonical": "canonical"
                in {str(item) for item in source.get("source_conditions", [])},
                "current": "current"
                in {str(item) for item in source.get("source_conditions", [])},
            }
        )
        index[source_id] = metadata
    return index


def _sentence_for_offset(answer: str, offset: int) -> str:
    start = max(
        answer.rfind(".", 0, offset),
        answer.rfind("!", 0, offset),
        answer.rfind("?", 0, offset),
    )
    ends = [position for mark in ".!?" if (position := answer.find(mark, offset)) >= 0]
    end = min(ends) + 1 if ends else len(answer)
    return answer[start + 1 : end].strip()


def prepare_trace(
    candidate: Mapping[str, Any],
    source_index: Mapping[str, Mapping[str, Any]],
    *,
    case: Mapping[str, Any] | None = None,
) -> RAGTrace:
    case = case or {}
    contexts: list[TraceContext] = []
    source_to_chunks: dict[str, list[str]] = {}
    for raw in candidate["selected_contexts"]:
        source_id = str(raw["source_id"])
        chunk_id = str(raw["chunk_id"])
        if source_id not in source_index:
            raise EvaluationIntegrityError(
                f"{candidate['case_id']}: source {source_id!r} is not frozen."
            )
        metadata = dict(source_index[source_id])
        metadata["chunk_id"] = chunk_id
        contexts.append(
            TraceContext(id=chunk_id, text=str(raw["text"]), metadata=metadata)
        )
        source_to_chunks.setdefault(source_id, []).append(chunk_id)

    answer = str(candidate["answer"])
    citations: list[TraceCitation] = []
    for match in _INLINE_CITATION_RE.finditer(answer):
        target = match.group(1).strip()
        if target in source_to_chunks and len(source_to_chunks[target]) == 1:
            target = source_to_chunks[target][0]
        elif target.isdigit() and 1 <= int(target) <= len(contexts):
            target = contexts[int(target) - 1].id
        citations.append(
            TraceCitation(
                claim=_sentence_for_offset(answer, match.start()),
                source_id=target,
                metadata={"parser": "inline_bracket_v1"},
            )
        )
    selected_urls = {
        str(context.metadata.get("source_url")): context.id
        for context in contexts
        if context.metadata.get("source_url")
    }
    for match in _URL_CITATION_RE.finditer(answer):
        target_url = match.group(0).rstrip(".,;:")
        citations.append(
            TraceCitation(
                claim=_sentence_for_offset(answer, match.start()),
                source_id=selected_urls.get(target_url, target_url),
                metadata={"parser": "url_v1"},
            )
        )
    return RAGTrace(
        query=str(candidate["query"]),
        answer=answer,
        contexts=contexts,
        citations=citations,
        metadata={
            "dataset_id": candidate["dataset_id"],
            "case_id": candidate["case_id"],
            "candidate_input_sha256": candidate["candidate_input_sha256"],
            "track": candidate["track"],
            "citation_required": case.get("citation_format") not in {None, "none"},
            "retrieval_family": (case.get("retrieval") or {}).get("family"),
            "reranking_enabled": (case.get("reranking") or {}).get("enabled"),
            "chunk_size": (case.get("chunking") or {}).get("size"),
        },
    )


def _profile_locks(ablation_config: Mapping[str, Any]) -> list[tuple[str, str]]:
    rows = [
        (
            str(ablation_config["candidate_profile"]["id"]),
            str(ablation_config["candidate_profile"]["sha256"]),
        )
    ]
    rows.extend(
        (str(row["profile_id"]), str(row["profile_sha256"]))
        for row in ablation_config["ablations"]
    )
    for profile_id, expected in rows:
        if profile_for_id(profile_id).sha256 != expected:
            raise EvaluationIntegrityError(
                f"Runtime profile differs from lock: {profile_id}."
            )
    return rows


def run_candidates(
    *,
    repository_root: Path,
    manifest_path: Path,
    artifact_root: Path,
    source_manifest_path: Path,
    model_path: Path,
    output_path: Path,
    authorization_path: Path,
    expected_manifest_file_sha256: str | None = None,
) -> dict[str, Any]:
    locks = verify_phase6_locks(repository_root)
    evaluation = locks["evaluation"]
    ablations = locks["ablations"]
    expected_source_manifest_sha256 = locks["dataset_freeze"]["artifact_chain"][
        "combined_source_manifest_file_sha256"
    ]
    authorization = require_execution_authorization(
        authorization_path,
        evaluation,
        ablations,
        expected_source_manifest_sha256=expected_source_manifest_sha256,
    )
    runtime_environment = verify_runtime_environment(
        repository_root, locks["dependencies"]
    )
    expected_manifest_file_sha256 = (
        expected_manifest_file_sha256
        or evaluation["dataset"]["frozen_manifest_file_sha256"]
    )
    if file_sha256(manifest_path) != expected_manifest_file_sha256:
        raise EvaluationIntegrityError("Frozen manifest file hash mismatch.")
    source_manifest = load_json_object(source_manifest_path)
    source_manifest_sha256 = file_sha256(source_manifest_path)
    if source_manifest_sha256 != expected_source_manifest_sha256:
        raise EvaluationIntegrityError("Frozen source-manifest file hash mismatch.")
    source_index = _source_index(source_manifest)
    nli = build_pinned_nli(model_path)
    profile_locks = _profile_locks(ablations)
    prediction_schema = load_json_object(
        repository_root / "packages/contexttrace/contexttrace/schemas/"
        "claim-verification-v2.schema.json"
    )
    validator = Draft202012Validator(prediction_schema)

    manifest = load_json_object(manifest_path)
    manifest_cases = manifest.get("cases")
    if not isinstance(manifest_cases, list):
        raise EvaluationIntegrityError("Frozen manifest cases are absent.")
    case_by_id = {
        str(case["case_id"]): case
        for case in manifest_cases
        if isinstance(case, Mapping) and case.get("case_id")
    }
    candidates = list(
        iter_frozen_candidates(
            manifest_path,
            artifact_root,
            expected_payload_sha256=evaluation["dataset"][
                "frozen_manifest_payload_sha256"
            ],
        )
    )
    if len(candidates) != evaluation["dataset"]["case_count"]:
        raise EvaluationIntegrityError("Candidate count differs from evaluation lock.")

    if output_path.exists():
        raise EvaluationIntegrityError("Candidate output path already exists.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path = output_path.with_suffix(output_path.suffix + ".journal.jsonl")
    if journal_path.exists():
        raise EvaluationIntegrityError("Candidate journal path already exists.")

    outputs: list[dict[str, Any]] = []
    with journal_path.open("x", encoding="utf-8") as journal:
        for candidate in candidates:
            case = case_by_id.get(str(candidate["case_id"]))
            if case is None:
                raise EvaluationIntegrityError(
                    f"Manifest metadata is missing {candidate['case_id']}."
                )
            trace = prepare_trace(candidate, source_index, case=case)
            profile_outputs: dict[str, Any] = {}
            for profile_id, _ in profile_locks:
                started = time.perf_counter()
                try:
                    prediction = verify_trace_v2(
                        trace,
                        profile=profile_for_id(profile_id),
                        nli=nli,
                    )
                    latency_ms = round((time.perf_counter() - started) * 1000, 6)
                    errors = sorted(
                        validator.iter_errors(prediction),
                        key=lambda error: tuple(error.absolute_path),
                    )
                    if errors:
                        raise EvaluationIntegrityError(
                            f"Schema validation failed: {errors[0].message}"
                        )
                    profile_outputs[profile_id] = {
                        "status": "completed",
                        "latency_ms": latency_ms,
                        "prediction": prediction,
                    }
                except Exception as exc:
                    profile_outputs[profile_id] = {
                        "status": "failed",
                        "latency_ms": round((time.perf_counter() - started) * 1000, 6),
                        "error_code": type(exc).__name__,
                        "error_message": str(exc)[:500],
                    }
            output = {
                "case_id": candidate["case_id"],
                "candidate_input_sha256": candidate["candidate_input_sha256"],
                "profiles": profile_outputs,
            }
            outputs.append(output)
            journal.write(json.dumps(output, ensure_ascii=False, sort_keys=True) + "\n")
            journal.flush()

    failure_count = sum(
        profile.get("status") != "completed"
        for output in outputs
        for profile in output["profiles"].values()
    )
    record: dict[str, Any] = {
        "schema_version": RUN_SCHEMA_VERSION,
        "dataset_id": evaluation["dataset"]["id"],
        "status": (
            "completed_unscored"
            if failure_count == 0
            else "completed_unscored_with_failures"
        ),
        "manifest_file_sha256": expected_manifest_file_sha256,
        "manifest_payload_sha256": evaluation["dataset"][
            "frozen_manifest_payload_sha256"
        ],
        "source_manifest_file_sha256": source_manifest_sha256,
        "authorization_file_sha256": file_sha256(authorization_path),
        "authorization_payload_sha256": authorization["payload_sha256"],
        "implementation_source_manifest_sha256": evaluation["candidate_system"][
            "implementation_source_manifest_sha256"
        ],
        "nli_artifact_manifest_sha256": locks["dependencies"]["nli"][
            "artifact_manifest_sha256"
        ],
        "profile_locks": [
            {"profile_id": profile_id, "profile_sha256": digest}
            for profile_id, digest in profile_locks
        ],
        "case_count": len(outputs),
        "profile_failure_count": failure_count,
        "journal_file_sha256": file_sha256(journal_path),
        "case_ids_sha256": canonical_sha256([output["case_id"] for output in outputs]),
        "environment": {
            **runtime_environment,
            "python_build": sys.version,
            "platform_detail": platform.platform(),
        },
        "outputs": outputs,
    }
    identity = dict(record)
    identity["outputs"] = [
        {
            **row,
            "profiles": {
                profile_id: {
                    key: item for key, item in value.items() if key != "latency_ms"
                }
                for profile_id, value in row["profiles"].items()
            },
        }
        for row in outputs
    ]
    record["run_payload_sha256"] = canonical_sha256(identity)
    output_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return record


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    record = run_candidates(
        repository_root=args.repository_root,
        manifest_path=args.manifest,
        artifact_root=args.artifact_root,
        source_manifest_path=args.source_manifest,
        model_path=args.model_path,
        output_path=args.output,
        authorization_path=args.authorization,
    )
    print(
        json.dumps(
            {
                "case_count": record["case_count"],
                "run_payload_sha256": record["run_payload_sha256"],
                "status": record["status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
