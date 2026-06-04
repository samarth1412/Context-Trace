from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from contexttrace.verify.claims import Claim
from contexttrace.verify.evidence import find_best_evidence
from contexttrace.verify.runner import verify_trace
from contexttrace.verify.schema import RAGTrace, TraceContext, VerificationInputError, load_trace_file
from contexttrace.verify.verdicts import classify_claim


NO_FAILURE = "no_failure_detected"
RETRIEVAL_MISS = "retrieval_miss"
RERANKING_FAILURE = "reranking_failure"
CHUNKING_ISSUE = "chunking_issue"
CORPUS_GAP = "corpus_gap"
ANSWER_OVERREACH = "answer_overreach"
STALE_SOURCE = "stale_source"
INSUFFICIENT_CONTEXT = "insufficient_context"

AUDIT_FAILURE_LABELS = {
    RETRIEVAL_MISS,
    RERANKING_FAILURE,
    CHUNKING_ISSUE,
    CORPUS_GAP,
    ANSWER_OVERREACH,
    STALE_SOURCE,
    INSUFFICIENT_CONTEXT,
}
BAD_CITATIONS = {
    "cited_source_missing",
    "cited_source_does_not_support_claim",
    "claim_supported_by_different_source",
}
SUPPORTED_VERDICTS = {"supported"}
CORPUS_EXTENSIONS = {
    ".csv",
    ".html",
    ".json",
    ".jsonl",
    ".md",
    ".markdown",
    ".rst",
    ".text",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}
SKIP_DIRECTORIES = {
    ".contexttrace",
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
MAX_FILE_BYTES = 1_000_000
RERANKING_CUTOFF = 3


def audit_trace_file(
    trace_path: str | Path,
    *,
    corpus_path: str | Path,
    mode: str = "lexical",
) -> dict[str, Any]:
    trace = load_trace_file(trace_path)
    return audit_trace(trace, corpus_path=corpus_path, mode=mode)


def audit_trace(
    trace: RAGTrace,
    *,
    corpus_path: str | Path,
    mode: str = "lexical",
) -> dict[str, Any]:
    corpus_contexts = load_corpus(corpus_path)
    return audit_trace_with_corpus(
        trace,
        corpus_contexts,
        corpus_path=str(Path(corpus_path)),
        mode=mode,
    )


def audit_trace_with_corpus(
    trace: RAGTrace,
    corpus_contexts: list[TraceContext],
    *,
    corpus_path: str = "embedded",
    mode: str = "lexical",
) -> dict[str, Any]:
    verification = verify_trace(trace, mode=mode)
    claim_audits = [
        _audit_claim(claim, trace, corpus_contexts, mode=mode)
        for claim in verification.get("claims") or []
    ]
    summary = _summary(claim_audits, verification, corpus_contexts, mode=mode)
    return {
        "query": trace.query,
        "answer": trace.answer,
        "summary": summary,
        "claims": claim_audits,
        "verification": {
            "summary": verification.get("summary") or {},
            "abstention": verification.get("abstention") or {},
            "diagnostics": verification.get("diagnostics") or {},
        },
        "corpus": {
            "path": str(corpus_path),
            "documents": len(corpus_contexts),
        },
        "metadata": dict(trace.metadata),
    }


def load_corpus(corpus_path: str | Path) -> list[TraceContext]:
    root = Path(corpus_path)
    if not root.exists():
        raise VerificationInputError("Corpus path %s does not exist." % root)

    files = [root] if root.is_file() else _corpus_files(root)
    contexts: list[TraceContext] = []
    for path in files:
        text = _read_text(path)
        if not text.strip():
            continue
        context_id = _context_id(path, root)
        contexts.append(
            TraceContext(
                id=context_id,
                text=text,
                metadata={
                    "path": str(path),
                    "source": context_id,
                    "size_bytes": path.stat().st_size,
                    "kind": "corpus_document",
                },
            )
        )

    if not contexts:
        raise VerificationInputError("Corpus path %s did not contain readable text documents." % root)
    return contexts


def audit_failures(result: dict[str, Any], fail_on: tuple[str, ...]) -> list[str]:
    if not fail_on:
        return []
    summary = result.get("summary") or {}
    messages = []
    for raw_rule in fail_on:
        rule = raw_rule.strip().lower().replace("-", "_")
        if rule == "any_failure" and bool(summary.get("has_audit_failures")):
            messages.append("audit failure detected")
        elif rule == "retrieval_miss" and int(summary.get(RETRIEVAL_MISS) or 0) > 0:
            messages.append("retrieval miss detected")
        elif rule == "reranking_failure" and int(summary.get(RERANKING_FAILURE) or 0) > 0:
            messages.append("reranking failure detected")
        elif rule == "chunking_issue" and int(summary.get(CHUNKING_ISSUE) or 0) > 0:
            messages.append("chunking issue detected")
        elif rule == "corpus_gap" and int(summary.get(CORPUS_GAP) or 0) > 0:
            messages.append("corpus gap detected")
        elif rule == "answer_overreach" and int(summary.get(ANSWER_OVERREACH) or 0) > 0:
            messages.append("answer overreach detected")
        elif rule == "stale_source" and int(summary.get(STALE_SOURCE) or 0) > 0:
            messages.append("stale source detected")
        elif rule == "insufficient_context" and int(summary.get(INSUFFICIENT_CONTEXT) or 0) > 0:
            messages.append("insufficient context detected")
        elif rule not in AUDIT_FAILURE_LABELS and rule != "any_failure":
            messages.append("unknown --fail-on rule %s" % raw_rule)
    return messages


def _audit_claim(
    claim: dict[str, Any],
    trace: RAGTrace,
    corpus_contexts: list[TraceContext],
    *,
    mode: str,
) -> dict[str, Any]:
    claim_text = str(claim.get("claim") or "")
    claim_id = str(claim.get("claim_id") or "")
    corpus_match = find_best_evidence(claim_text, corpus_contexts, mode=mode)
    corpus_verification = classify_claim(
        Claim(id=claim_id or "claim", text=claim_text),
        corpus_match,
        has_contexts=bool(corpus_contexts),
        mode=mode,
    )
    diagnosis = _diagnose(claim, trace, corpus_match, corpus_verification)
    return {
        "claim_id": claim_id,
        "claim": claim_text,
        "audit_label": diagnosis["label"],
        "confidence": diagnosis["confidence"],
        "reason": diagnosis["reason"],
        "suggested_fix": diagnosis["suggested_fix"],
        "retrieved": {
            "verdict": claim.get("verdict"),
            "best_context_id": claim.get("best_context_id"),
            "best_score": claim.get("best_score"),
            "evidence": claim.get("evidence"),
            "matched_terms": list(claim.get("matched_terms") or []),
            "root_cause": (claim.get("root_cause") or {}).get("label"),
            "citation_status": claim.get("citation_status"),
        },
        "corpus": {
            "verdict": corpus_verification.verdict,
            "best_document_id": corpus_match.context_id,
            "best_score": corpus_match.score,
            "evidence": corpus_match.snippet,
            "matched_terms": list(corpus_match.matched_terms),
            "evidence_span": corpus_match.span_dict(),
            "supporting_spans": list(corpus_match.supporting_spans or []),
            "required_facts": list(corpus_verification.required_facts),
            "matched_facts": list(corpus_verification.matched_facts),
            "missing_facts": list(corpus_verification.missing_facts),
            "conflicting_facts": list(corpus_verification.conflicting_facts),
        },
    }


def _diagnose(
    claim: dict[str, Any],
    trace: RAGTrace,
    corpus_match: object,
    corpus_verification: object,
) -> dict[str, Any]:
    verdict = str(claim.get("verdict") or "")
    root_label = str((claim.get("root_cause") or {}).get("label") or NO_FAILURE)
    citation_status = str(claim.get("citation_status") or "")
    corpus_verdict = str(getattr(corpus_verification, "verdict", ""))
    corpus_score = float(getattr(corpus_match, "score", 0.0) or 0.0)
    same_source_rank = _same_source_retrieved_rank(str(getattr(corpus_match, "context_id", "") or ""), trace)

    if _is_citation_only_failure(claim):
        return _result(
            NO_FAILURE,
            0.92,
            "The claim is supported by retrieved evidence; the remaining issue is citation-level, not a retrieval or corpus failure.",
            "Fix the claim-level citation, but do not treat this as a retrieval miss.",
        )

    if not _is_failure(claim):
        return _result(
            NO_FAILURE,
            0.99,
            "The claim is already supported by the retrieved contexts.",
            "No fix needed for this claim.",
        )

    if verdict == "contradicted" or corpus_verdict == "contradicted" or root_label in {"stale_context", "conflicting_contexts"}:
        return _result(
            STALE_SOURCE,
            0.86,
            "The claim appears to conflict with retrieved or corpus evidence.",
            "Resolve stale or conflicting sources before allowing the answer to use this fact.",
        )

    if corpus_verdict in SUPPORTED_VERDICTS:
        if same_source_rank is None:
            return _result(
                RETRIEVAL_MISS,
                max(0.82, min(0.98, corpus_score + 0.12)),
                "The broader corpus contains evidence for this claim, but the retrieved contexts did not include it.",
                "Improve retrieval recall, filters, query rewriting, or top_k so this source is retrieved.",
            )
        if same_source_rank >= RERANKING_CUTOFF:
            return _result(
                RERANKING_FAILURE,
                max(0.78, min(0.95, corpus_score + 0.08)),
                "A related source was retrieved, but it appeared too low in the retrieved context list for reliable generation.",
                "Add a reranker or raise high-evidence chunks from this source before generation.",
            )
        return _result(
            CHUNKING_ISSUE,
            max(0.78, min(0.95, corpus_score + 0.08)),
            "The retrieved source appears related, but the retrieved chunk omitted the supporting span found in the corpus.",
            "Adjust chunk boundaries, overlap, or parent-document retrieval so the answerable span is included.",
        )

    if root_label == "answer_overreach" or verdict == "partially_supported":
        return _result(
            ANSWER_OVERREACH,
            0.82,
            "The evidence supports part of the claim, but not every required fact.",
            "Remove unsupported details or retrieve evidence that explicitly supports each detail.",
        )

    if corpus_verdict == "partially_supported":
        return _result(
            ANSWER_OVERREACH,
            0.78,
            "The corpus supports only part of the claim, so the answer likely added unsupported detail.",
            "Split the claim and require support for every required fact before answering.",
        )

    if corpus_verdict == "unverifiable" or verdict == "unverifiable":
        return _result(
            INSUFFICIENT_CONTEXT,
            0.72,
            "The closest corpus evidence is related but too weak or ambiguous to verify the claim.",
            "Retrieve more specific evidence or force the model to qualify/abstain.",
        )

    if citation_status in BAD_CITATIONS and corpus_score >= 0.35:
        return _result(
            INSUFFICIENT_CONTEXT,
            0.7,
            "The claim has a citation problem and the broader corpus evidence is still not strong enough.",
            "Regenerate claim-level citations and require cited sources to cover all required facts.",
        )

    return _result(
        CORPUS_GAP,
        max(0.7, min(0.95, 1.0 - corpus_score)),
        "Neither the retrieved contexts nor the broader corpus provide enough support for this claim.",
        "Add the missing source to the corpus or make the answer abstain when the corpus lacks this fact.",
    )


def _summary(
    claim_audits: list[dict[str, Any]],
    verification: dict[str, Any],
    corpus_contexts: list[TraceContext],
    *,
    mode: str,
) -> dict[str, Any]:
    counts = Counter(str(claim.get("audit_label") or NO_FAILURE) for claim in claim_audits)
    labels = [NO_FAILURE] + sorted(AUDIT_FAILURE_LABELS)
    failure_count = sum(counts[label] for label in AUDIT_FAILURE_LABELS)
    return {
        "mode": mode,
        "total_claims": len(claim_audits),
        "audited_claims": len([claim for claim in claim_audits if claim.get("audit_label") != NO_FAILURE]),
        "corpus_documents": len(corpus_contexts),
        "has_audit_failures": failure_count > 0,
        "primary_audit_label": _primary_label(counts),
        "verification_failure_type": (verification.get("summary") or {}).get("failure_type"),
        "verification_primary_root_cause": (verification.get("summary") or {}).get("primary_root_cause"),
        **{label: counts[label] for label in labels},
    }


def _primary_label(counts: Counter) -> str:
    failures = {label: counts[label] for label in AUDIT_FAILURE_LABELS if counts[label]}
    if not failures:
        return NO_FAILURE
    priority = [
        RETRIEVAL_MISS,
        CHUNKING_ISSUE,
        RERANKING_FAILURE,
        CORPUS_GAP,
        ANSWER_OVERREACH,
        STALE_SOURCE,
        INSUFFICIENT_CONTEXT,
    ]
    return max(
        failures,
        key=lambda label: (
            failures[label],
            -priority.index(label) if label in priority else -len(priority),
        ),
    )


def _is_failure(claim: dict[str, Any]) -> bool:
    return (
        str(claim.get("verdict") or "") not in SUPPORTED_VERDICTS
        or str(claim.get("citation_status") or "") in BAD_CITATIONS
        or str((claim.get("root_cause") or {}).get("label") or NO_FAILURE) != NO_FAILURE
    )


def _is_citation_only_failure(claim: dict[str, Any]) -> bool:
    return (
        str(claim.get("verdict") or "") in SUPPORTED_VERDICTS
        and str(claim.get("citation_status") or "") in BAD_CITATIONS
        and str((claim.get("root_cause") or {}).get("label") or NO_FAILURE)
        in {"wrong_source_cited", "missing_cited_source", NO_FAILURE}
    )


def _same_source_retrieved_rank(corpus_context_id: str, trace: RAGTrace) -> int | None:
    corpus_key = _source_key(corpus_context_id)
    if not corpus_key:
        return None
    for index, context in enumerate(trace.contexts):
        candidates = [
            context.id,
            context.metadata.get("source"),
            context.metadata.get("path"),
            context.metadata.get("file"),
            context.metadata.get("document"),
        ]
        if any(_sources_match(corpus_key, _source_key(value)) for value in candidates):
            return index
    return None


def _sources_match(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    return Path(left).name == Path(right).name


def _source_key(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/").lower()
    return text.strip("./")


def _result(label: str, confidence: float, reason: str, suggested_fix: str) -> dict[str, Any]:
    return {
        "label": label,
        "confidence": round(confidence, 3),
        "reason": reason,
        "suggested_fix": suggested_fix,
    }


def _corpus_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRECTORIES for part in path.parts):
            continue
        if path.suffix.lower() not in CORPUS_EXTENSIONS:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        files.append(path)
    return sorted(files, key=lambda item: str(item).lower())


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""
    except OSError:
        return ""


def _context_id(path: Path, root: Path) -> str:
    if root.is_file():
        return path.name
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name
