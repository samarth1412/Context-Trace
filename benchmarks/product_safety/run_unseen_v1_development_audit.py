"""Audit the reclassified ContextTrace-Unseen-v1 corpus as development data.

This runner never accepts gold labels. It verifies every referenced trace hash,
runs the current v2.1 candidate with the pinned local NLI artifact, checkpoints
compact per-case outputs, and reports observable safety-policy violations. The
result is development evidence only and must not be described as untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import time
from collections import Counter
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path
from typing import Any

from contexttrace.verify.schema import RAGTrace, TraceCitation, TraceContext
from contexttrace.verify.semantic_core_v2 import build_pinned_nli, verify_nli_artifact
from contexttrace.verify.semantic_core_v2_1 import (
    SELECTIVE_V2_1_PROFILE,
    verify_trace_v2_1,
)

AUDIT_SCHEMA_VERSION = "contexttrace-unseen-v1-development-audit-1.0"
RISKY_SOURCE_CONDITIONS = {
    "conflicting_authorities",
    "current_noncanonical",
    "low_authority",
    "stale",
    "superseded",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    result = run_audit(
        manifest_path=args.manifest,
        artifact_root=args.artifact_root,
        source_manifest_path=args.source_manifest,
        model_path=args.model_path,
        output_path=args.output,
        resume=args.resume,
    )
    print(
        json.dumps(
            {
                "case_count": result["case_count"],
                "observable_safety_violation_count": result[
                    "observable_safety_violation_count"
                ],
                "report_payload_sha256": result["report_payload_sha256"],
                "status": result["status"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["status"] == "completed" else 1


def run_audit(
    *,
    manifest_path: Path,
    artifact_root: Path,
    source_manifest_path: Path,
    model_path: Path,
    output_path: Path,
    resume: bool = False,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with _exclusive_output_lock(output_path):
        return _run_audit_locked(
            manifest_path=manifest_path,
            artifact_root=artifact_root,
            source_manifest_path=source_manifest_path,
            model_path=model_path,
            output_path=output_path,
            resume=resume,
        )


def _run_audit_locked(
    *,
    manifest_path: Path,
    artifact_root: Path,
    source_manifest_path: Path,
    model_path: Path,
    output_path: Path,
    resume: bool = False,
) -> dict[str, Any]:
    manifest = _read_object(manifest_path)
    source_manifest = _read_object(source_manifest_path)
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("The development manifest must contain cases.")
    expected_count = manifest.get("case_count")
    if expected_count != len(cases):
        raise ValueError("The manifest case count does not match its cases.")
    if manifest.get("status") != "frozen_unscored":
        raise ValueError("The input must be the frozen unlabeled manifest.")
    if any(_contains_label_key(case) for case in cases):
        raise ValueError("The development manifest unexpectedly contains labels.")

    source_index = _source_index(source_manifest)
    model_lock = verify_nli_artifact(model_path)
    nli = build_pinned_nli(model_path)
    journal_path = output_path.with_suffix(output_path.suffix + ".journal.jsonl")
    rows = _load_or_initialize_journal(
        output_path=output_path,
        journal_path=journal_path,
        resume=resume,
    )
    completed_ids = {str(row["case_id"]) for row in rows}
    case_ids = [str(case["case_id"]) for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("The development manifest contains duplicate case IDs.")
    if not completed_ids.issubset(set(case_ids)):
        raise ValueError("The audit journal contains a case outside the manifest.")

    mode = "a" if rows else "x"
    with journal_path.open(mode, encoding="utf-8") as journal:
        for case in cases:
            case_id = str(case["case_id"])
            if case_id in completed_ids:
                continue
            trace_path = artifact_root / "artifacts" / str(case["trace_artifact_path"])
            expected_trace_sha256 = str(case["trace_sha256"])
            if _file_sha256(trace_path) != expected_trace_sha256:
                raise ValueError(f"Frozen trace hash mismatch: {case_id}.")
            artifact_hash = manifest.get("artifacts", {}).get(
                str(case["trace_artifact_path"])
            )
            if artifact_hash != expected_trace_sha256:
                raise ValueError(f"Manifest artifact binding mismatch: {case_id}.")
            trace_payload = _read_object(trace_path)
            trace = prepare_trace(case, trace_payload, source_index)
            started = time.perf_counter()
            try:
                prediction = verify_trace_v2_1(
                    trace,
                    profile=SELECTIVE_V2_1_PROFILE,
                    nli=nli,
                )
                latency_ms = round((time.perf_counter() - started) * 1000, 3)
                row = _compact_row(case, trace, prediction, latency_ms)
            except Exception as exc:  # noqa: BLE001
                row = {
                    "case_id": case_id,
                    "status": "failed",
                    "error_code": type(exc).__name__,
                    "error_message": str(exc)[:500],
                }
            rows.append(row)
            journal.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            journal.flush()

    if [str(row["case_id"]) for row in rows] != case_ids:
        raise ValueError("The completed journal order differs from the manifest.")
    report = _build_report(
        rows=rows,
        manifest=manifest,
        manifest_path=manifest_path,
        source_manifest_path=source_manifest_path,
        journal_path=journal_path,
        model_lock=model_lock,
    )
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


@contextmanager
def _exclusive_output_lock(output_path: Path) -> Iterator[None]:
    lock_path = output_path.with_suffix(output_path.suffix + ".lock")
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError(f"Another audit process holds {lock_path}.") from exc
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode())
        yield
    finally:
        os.close(descriptor)
        lock_path.unlink(missing_ok=True)


def prepare_trace(
    case: Mapping[str, Any],
    trace_payload: Mapping[str, Any],
    source_index: Mapping[str, Mapping[str, Any]],
) -> RAGTrace:
    case_id = str(case["case_id"])
    if trace_payload.get("case_id") != case_id:
        raise ValueError(f"Trace case binding mismatch: {case_id}.")
    retrieved = trace_payload.get("retrieved_chunks")
    selected_ids = trace_payload.get("selected_context_ids")
    if not isinstance(retrieved, list) or not isinstance(selected_ids, list):
        raise TypeError(f"Trace retrieval fields are invalid: {case_id}.")
    retrieved_by_id = {
        str(chunk["id"]): chunk
        for chunk in retrieved
        if isinstance(chunk, Mapping) and chunk.get("id")
    }
    contexts: list[TraceContext] = []
    for selected_id in selected_ids:
        chunk_id = str(selected_id)
        chunk = retrieved_by_id.get(chunk_id)
        if chunk is None:
            raise ValueError(f"Selected chunk is absent from retrieval: {case_id}.")
        source_id = str(chunk["source_id"])
        source = source_index.get(source_id)
        if source is None:
            raise ValueError(f"Selected source is absent from manifest: {case_id}.")
        metadata = dict(source)
        metadata.update(
            {
                "chunk_id": chunk_id,
                "document_path": chunk.get("document_path"),
            }
        )
        contexts.append(
            TraceContext(id=chunk_id, text=str(chunk["text"]), metadata=metadata)
        )

    answer = str(trace_payload["answer"])
    citations: list[TraceCitation] = []
    for citation in trace_payload.get("citations") or []:
        if not isinstance(citation, Mapping):
            continue
        raw = str(citation.get("raw") or "")
        position = answer.find(raw) if raw else 0
        citations.append(
            TraceCitation(
                claim=_sentence_for_offset(answer, max(position, 0)),
                source_id=str(citation.get("chunk_id") or citation["source_id"]),
                metadata={"parser": "frozen_trace_citation_v1"},
            )
        )
    return RAGTrace(
        query=str(trace_payload["query"]),
        answer=answer,
        contexts=contexts,
        citations=citations,
        metadata={
            "case_id": case_id,
            "track": case["track"],
            "source_family": case["source_family"],
            "domain_group": case["domain_group"],
            "publication_window": case["publication_window"],
            "citation_required": case.get("citation_format") not in {None, "none"},
            "retrieval_family": (case.get("retrieval") or {}).get("family"),
            "reranking_enabled": (case.get("reranking") or {}).get("enabled"),
            "chunk_size": (case.get("chunking") or {}).get("size"),
        },
    )


def _compact_row(
    case: Mapping[str, Any],
    trace: RAGTrace,
    prediction: Mapping[str, Any],
    latency_ms: float,
) -> dict[str, Any]:
    context_by_id = {context.id: context for context in trace.contexts}
    citation_required = bool(trace.metadata.get("citation_required"))
    claims: list[dict[str, Any]] = []
    for claim in prediction["claims"]:
        reasons = _observable_safety_reasons(
            claim,
            context_by_id=context_by_id,
            citation_required=citation_required,
        )
        deterministic = dict(claim.get("deterministic") or {})
        signals = dict(deterministic.get("signals") or {})
        attribution = dict(signals.get("evidence_attribution") or {})
        claims.append(
            {
                "claim_id": claim["claim_id"],
                "text": claim["text"],
                "verification_text": claim.get("verification_text"),
                "start_char": claim["start_char"],
                "end_char": claim["end_char"],
                "claim_verdict": claim["claim_verdict"],
                "route": claim["route"],
                "diagnostic_confidence": claim["diagnostic_confidence"],
                "diagnostic_abstention": claim["diagnostic_abstention"],
                "green": claim["green"],
                "qualification_required": claim["qualification_required"],
                "failure_label": claim["failure_label"],
                "primary_root_cause": claim["primary_root_cause"],
                "abstention_requirement": claim["abstention_requirement"],
                "citation_state": claim["citation_state"],
                "source_condition": claim["source_condition"],
                "deterministic_verdict": deterministic.get("verdict"),
                "deterministic_confidence": deterministic.get("confidence"),
                "evidence_span_count": len(claim.get("evidence_spans") or []),
                "evidence_exact_offsets_verified": attribution.get(
                    "exact_offsets_verified"
                ),
                "evidence_term_coverage": attribution.get("claim_term_coverage"),
                "nli": claim.get("nli"),
                "flags": claim.get("flags"),
                "observable_safety_reasons": reasons,
            }
        )
    return {
        "case_id": case["case_id"],
        "status": "completed",
        "track": case["track"],
        "source_family": case["source_family"],
        "domain_group": case["domain_group"],
        "publication_window": case["publication_window"],
        "trace_sha256": case["trace_sha256"],
        "latency_ms": latency_ms,
        "summary": prediction["summary"],
        "claims": claims,
    }


def _observable_safety_reasons(
    claim: Mapping[str, Any],
    *,
    context_by_id: Mapping[str, TraceContext],
    citation_required: bool,
) -> list[str]:
    if not claim.get("green"):
        return []
    reasons: list[str] = []
    if claim.get("claim_verdict") != "supported":
        reasons.append("green_non_supported_verdict")
    if claim.get("diagnostic_abstention"):
        reasons.append("green_diagnostic_abstention")
    if claim.get("qualification_required"):
        reasons.append("green_qualification_required")
    if claim.get("abstention_requirement") != "must_answer":
        reasons.append("green_non_answer_requirement")
    if claim.get("failure_label") != "none":
        reasons.append("green_failure_label")
    if claim.get("primary_root_cause") != "none":
        reasons.append("green_root_cause")
    if claim.get("source_condition") in RISKY_SOURCE_CONDITIONS:
        reasons.append("green_risky_source_condition")
    if citation_required and claim.get("citation_state") not in {"correct", "valid"}:
        reasons.append("green_invalid_required_citation")
    evidence_spans = claim.get("evidence_spans") or []
    if not evidence_spans:
        reasons.append("green_without_evidence_span")
    for span in evidence_spans:
        context = context_by_id.get(str(span.get("context_id")))
        start = span.get("start_char")
        end = span.get("end_char")
        text = span.get("text")
        if (
            context is None
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end < start
            or context.text[start:end] != text
        ):
            reasons.append("green_non_exact_evidence_span")
            break
    return sorted(set(reasons))


def _build_report(
    *,
    rows: list[dict[str, Any]],
    manifest: Mapping[str, Any],
    manifest_path: Path,
    source_manifest_path: Path,
    journal_path: Path,
    model_lock: Mapping[str, Any],
) -> dict[str, Any]:
    completed = [row for row in rows if row["status"] == "completed"]
    failures = [row for row in rows if row["status"] != "completed"]
    claims = [claim for row in completed for claim in row["claims"]]
    violations = [
        {
            "case_id": row["case_id"],
            "claim_id": claim["claim_id"],
            "reasons": claim["observable_safety_reasons"],
        }
        for row in completed
        for claim in row["claims"]
        if claim["observable_safety_reasons"]
    ]
    review_candidates = [
        {
            "case_id": row["case_id"],
            "claim_id": claim["claim_id"],
            "reason": "green_low_evidence_term_coverage",
        }
        for row in completed
        for claim in row["claims"]
        if claim["green"]
        and isinstance(claim.get("evidence_term_coverage"), (int, float))
        and claim["evidence_term_coverage"] < 0.75
    ]
    latencies = [float(row["latency_ms"]) for row in completed]
    total_nli = sum(int(row["summary"]["nli_invocations"]) for row in completed)
    report: dict[str, Any] = {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "audit_id": "contexttrace-unseen-v1-v2.1-final-development-audit",
        "evidence_class": "development_only_not_untouched_not_sota_evidence",
        "status": "completed" if not failures else "completed_with_failures",
        "dataset": {
            "id": "ContextTrace-Unseen-v1-reclassified-development",
            "case_count": len(rows),
            "manifest_file_sha256": _file_sha256(manifest_path),
            "manifest_payload_sha256": manifest["seal"]["payload_sha256"],
            "source_manifest_file_sha256": _file_sha256(source_manifest_path),
            "journal_file_sha256": _file_sha256(journal_path),
        },
        "candidate": {
            "profile_id": SELECTIVE_V2_1_PROFILE.id,
            "profile_sha256": SELECTIVE_V2_1_PROFILE.sha256,
            "nli_model_id": model_lock["model_id"],
            "nli_model_revision": model_lock["model_revision"],
            "nli_artifact_manifest_sha256": model_lock["artifact_manifest_sha256"],
            "runtime_versions": {
                "torch": version("torch"),
                "transformers": version("transformers"),
            },
        },
        "case_count": len(rows),
        "completed_case_count": len(completed),
        "runtime_failure_count": len(failures),
        "runtime_failures": [
            {
                "case_id": row["case_id"],
                "error_code": row.get("error_code"),
                "error_message": row.get("error_message"),
            }
            for row in failures
        ],
        "claim_count": len(claims),
        "green_claim_count": sum(bool(claim["green"]) for claim in claims),
        "diagnostic_abstention_count": sum(
            bool(claim["diagnostic_abstention"]) for claim in claims
        ),
        "nli_invocation_count": total_nli,
        "nli_invocation_rate": _ratio(total_nli, len(claims)),
        "overall_status_counts": _counter(
            row["summary"]["overall_status"] for row in completed
        ),
        "track_counts": _counter(row["track"] for row in completed),
        "claim_verdict_counts": _counter(claim["claim_verdict"] for claim in claims),
        "route_counts": _counter(claim["route"] for claim in claims),
        "source_condition_counts": _counter(
            claim["source_condition"] for claim in claims
        ),
        "failure_label_counts": _counter(claim["failure_label"] for claim in claims),
        "observable_safety_violation_count": len(violations),
        "observable_safety_violations": violations,
        "manual_review_candidate_count": len(review_candidates),
        "manual_review_candidates": review_candidates,
        "latency_ms": {
            "p50": round(statistics.median(latencies), 3) if latencies else 0.0,
            "p95": _percentile(latencies, 0.95),
        },
        "interpretation": [
            "The 493 cases were reclassified as development data after the original independent-label protocol failed.",
            "No gold-label file or private scoring detail was read by this audit.",
            "Observable safety violations are internal consistency failures, not measured false-green errors.",
            "This report cannot support untouched, confirmatory, or SOTA claims.",
        ],
    }
    identity = dict(report)
    report["report_payload_sha256"] = _canonical_sha256(identity)
    return report


def _source_index(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise TypeError("The source manifest must contain sources.")
    result: dict[str, dict[str, Any]] = {}
    for source in sources:
        if not isinstance(source, Mapping) or not source.get("source_id"):
            raise ValueError("The source manifest contains an invalid row.")
        source_id = str(source["source_id"])
        if source_id in result:
            raise ValueError(f"Duplicate source ID: {source_id}.")
        conditions = {
            str(item).casefold() for item in source.get("source_conditions", [])
        }
        metadata = dict(source.get("metadata") or {})
        metadata.update(
            {
                "source_id": source_id,
                "source_snapshot_id": source.get("snapshot_sha256"),
                "source_condition": _source_condition(conditions),
                "published_at": source.get("published_at"),
                "authority_basis": source.get("authority_basis"),
                "authority_score": source.get("authority_score"),
                "source_url": source.get("source_url"),
                "canonical": "canonical" in conditions,
                "current": "current" in conditions,
                "source_version": source.get("source_version"),
                "document_lineage_id": source.get("document_lineage_id"),
            }
        )
        result[source_id] = metadata
    return result


def _source_condition(conditions: set[str]) -> str:
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


def _sentence_for_offset(answer: str, offset: int) -> str:
    start = max(
        answer.rfind(".", 0, offset),
        answer.rfind("!", 0, offset),
        answer.rfind("?", 0, offset),
    )
    ends = [position for mark in ".!?" if (position := answer.find(mark, offset)) >= 0]
    end = min(ends) + 1 if ends else len(answer)
    return answer[start + 1 : end].strip()


def _load_or_initialize_journal(
    *, output_path: Path, journal_path: Path, resume: bool
) -> list[dict[str, Any]]:
    if not resume and (output_path.exists() or journal_path.exists()):
        raise FileExistsError("Audit output exists; pass --resume to continue it.")
    if resume and not journal_path.exists():
        raise FileNotFoundError("Cannot resume because the audit journal is absent.")
    if not journal_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        journal_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid audit journal line {line_number}.") from exc
        if not isinstance(value, dict) or not value.get("case_id"):
            raise ValueError(f"Invalid audit journal row {line_number}.")
        rows.append(value)
    return rows


def _contains_label_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in {"gold", "gold_label", "failure_label", "verdict"}:
                return True
            if _contains_label_key(item):
                return True
    elif isinstance(value, list):
        return any(_contains_label_key(item) for item in value)
    return False


def _counter(values: Any) -> dict[str, int]:
    counts = Counter(str(value) for value in values)
    return {key: counts[key] for key in sorted(counts)}


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object: {path}.")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    index = max(0, math.ceil(quantile * len(values)) - 1)
    return round(sorted(values)[index], 3)


if __name__ == "__main__":
    raise SystemExit(main())
