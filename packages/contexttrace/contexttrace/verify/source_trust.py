from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from contexttrace.verify.claims import Claim
from contexttrace.verify.evidence import score_claim_against_context
from contexttrace.verify.schema import RAGTrace
from contexttrace.verify.verdicts import classify_claim


GROUNDING_SOURCE_UNKNOWN = "freshness_unknown"
SUPPORTED_BY_CANONICAL_SOURCE = "supported_by_canonical_source"
GROUNDED_BUT_STALE = "grounded_but_stale"
GROUNDED_BUT_CONFLICTED = "grounded_but_conflicted"
GROUNDED_BY_LOW_AUTHORITY_SOURCE = "grounded_by_low_authority_source"
STALE_SOURCE = "stale_source"
CONFLICTING_SOURCE = "conflicting_source"
LOW_AUTHORITY_THRESHOLD = 0.4
HIGH_AUTHORITY_THRESHOLD = 0.85


def attach_source_assessments(
    claims: list[dict[str, Any]],
    trace: RAGTrace,
    *,
    mode: str,
) -> list[dict[str, Any]]:
    contexts_by_id = {context.id: context for context in trace.contexts}
    return [
        {
            **claim,
            **_source_fields(claim, trace, contexts_by_id, mode=mode),
        }
        for claim in claims
    ]


def _source_fields(
    claim: dict[str, Any],
    trace: RAGTrace,
    contexts_by_id: dict[str, Any],
    *,
    mode: str,
) -> dict[str, Any]:
    assessment = source_assessment(claim, trace, contexts_by_id, mode=mode)
    status = source_status_from_assessment(claim, assessment)
    return {
        "source_status": status,
        "source_assessment": assessment,
    }


def source_assessment(
    claim: dict[str, Any],
    trace: RAGTrace,
    contexts_by_id: dict[str, Any],
    *,
    mode: str,
) -> dict[str, Any]:
    claim_text = str(claim.get("claim") or "")
    best_context_id = str(claim.get("best_context_id") or "")
    best_context = contexts_by_id.get(best_context_id)
    best_signal = _context_signal(best_context, claim_text, mode=mode) if best_context is not None else None
    context_signals = [
        _context_signal(context, claim_text, mode=mode)
        for context in trace.contexts
    ]
    supporting = [signal for signal in context_signals if signal["verdict"] == "supported"]
    conflicting = [signal for signal in context_signals if signal["verdict"] == "contradicted"]
    newer_sources = _newer_related_sources(best_signal, context_signals)
    stronger_conflicts = _stronger_conflicts(best_signal, conflicting)
    explicit_status = _metadata_status(best_signal["metadata"] if best_signal else {})
    return {
        "best_source": best_signal,
        "supporting_sources": _signal_summaries(supporting),
        "conflicting_sources": _signal_summaries(conflicting),
        "newer_related_sources": _signal_summaries(newer_sources),
        "stronger_conflicting_sources": _signal_summaries(stronger_conflicts),
        "has_conflict": bool(conflicting),
        "has_stronger_conflict": bool(stronger_conflicts),
        "has_newer_related_source": bool(newer_sources),
        "explicit_source_status": explicit_status,
    }


def source_status_from_assessment(claim: dict[str, Any], assessment: dict[str, Any]) -> str:
    verdict = str(claim.get("verdict") or "")
    best = assessment.get("best_source") or {}
    explicit_status = str(assessment.get("explicit_source_status") or "")
    if not best:
        return "no_source"
    if verdict != "supported":
        if assessment.get("has_stronger_conflict") or assessment.get("has_conflict"):
            return CONFLICTING_SOURCE
        if explicit_status:
            return explicit_status
        return GROUNDING_SOURCE_UNKNOWN
    if explicit_status in {GROUNDED_BUT_STALE, STALE_SOURCE, "stale_or_version_conflicted"}:
        return GROUNDED_BUT_STALE
    if bool(best.get("stale")) or assessment.get("has_newer_related_source"):
        return GROUNDED_BUT_STALE
    if assessment.get("has_stronger_conflict"):
        return GROUNDED_BUT_CONFLICTED
    if float(best.get("authority_score") or 0.0) < LOW_AUTHORITY_THRESHOLD:
        return GROUNDED_BY_LOW_AUTHORITY_SOURCE
    if bool(best.get("canonical")) or float(best.get("authority_score") or 0.0) >= HIGH_AUTHORITY_THRESHOLD:
        return SUPPORTED_BY_CANONICAL_SOURCE
    if explicit_status:
        return explicit_status
    return GROUNDING_SOURCE_UNKNOWN


def _context_signal(context: Any, claim_text: str, *, mode: str) -> dict[str, Any]:
    metadata = dict(getattr(context, "metadata", {}) or {})
    match = score_claim_against_context(claim_text, context, mode=mode)
    verification = classify_claim(
        Claim(id="source_check", text=claim_text),
        match,
        has_contexts=True,
        mode=mode,
    )
    timestamp = _timestamp(metadata)
    version = _version_tuple(metadata)
    authority_score = _authority_score(metadata)
    return {
        "context_id": getattr(context, "id", None),
        "verdict": verification.verdict,
        "score": verification.best_score,
        "authority_score": authority_score,
        "authority_label": _authority_label(metadata, authority_score),
        "canonical": _is_canonical(metadata),
        "stale": _is_stale(metadata),
        "source_group": _source_group(context, metadata),
        "source_timestamp": _timestamp_label(metadata),
        "timestamp_sort": timestamp.timestamp() if timestamp else None,
        "source_version": _version_label(metadata),
        "version_sort": list(version) if version else None,
        "metadata": metadata,
        "evidence": verification.evidence,
    }


def _stronger_conflicts(best: dict[str, Any] | None, conflicting: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not best:
        return conflicting
    stronger = []
    best_authority = float(best.get("authority_score") or 0.0)
    best_time = best.get("timestamp_sort")
    best_version = tuple(best.get("version_sort") or [])
    for signal in conflicting:
        if signal.get("context_id") == best.get("context_id"):
            continue
        same_group = signal.get("source_group") == best.get("source_group")
        conflict_authority = float(signal.get("authority_score") or 0.0)
        conflict_time = signal.get("timestamp_sort")
        conflict_version = tuple(signal.get("version_sort") or [])
        if bool(signal.get("canonical")) and not bool(best.get("canonical")):
            stronger.append(signal)
        elif conflict_authority >= best_authority + 0.15:
            stronger.append(signal)
        elif same_group and conflict_time is not None and (best_time is None or conflict_time > best_time):
            stronger.append(signal)
        elif same_group and conflict_version and (not best_version or conflict_version > best_version):
            stronger.append(signal)
    return stronger


def _newer_related_sources(best: dict[str, Any] | None, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not best:
        return []
    newer = []
    best_time = best.get("timestamp_sort")
    best_version = tuple(best.get("version_sort") or [])
    for signal in signals:
        if signal.get("context_id") == best.get("context_id"):
            continue
        if signal.get("source_group") != best.get("source_group"):
            continue
        signal_time = signal.get("timestamp_sort")
        signal_version = tuple(signal.get("version_sort") or [])
        if signal_time is not None and best_time is not None and signal_time > best_time:
            newer.append(signal)
        elif signal_version and best_version and signal_version > best_version:
            newer.append(signal)
    return newer


def _signal_summaries(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "context_id": signal.get("context_id"),
            "verdict": signal.get("verdict"),
            "score": signal.get("score"),
            "authority_score": signal.get("authority_score"),
            "authority_label": signal.get("authority_label"),
            "canonical": signal.get("canonical"),
            "stale": signal.get("stale"),
            "source_group": signal.get("source_group"),
            "source_timestamp": signal.get("source_timestamp"),
            "source_version": signal.get("source_version"),
            "evidence": signal.get("evidence"),
        }
        for signal in signals
    ]


def _authority_score(metadata: dict[str, Any]) -> float:
    for key in ("source_authority", "authority_score", "trust_score", "authority"):
        value = metadata.get(key)
        if value is None:
            continue
        numeric = _float(value)
        if numeric is not None:
            return round(max(0.0, min(1.0, numeric / 100 if numeric > 1 else numeric)), 3)
        label = str(value).strip().lower()
        if label in {"canonical", "official", "primary", "high", "trusted", "source_of_truth"}:
            return 1.0
        if label in {"medium", "reviewed", "internal"}:
            return 0.65
        if label in {"low", "unknown", "unverified", "forum", "blog", "secondary"}:
            return 0.25
    if _is_canonical(metadata):
        return 1.0
    return 0.5


def _authority_label(metadata: dict[str, Any], authority_score: float) -> str:
    for key in ("source_authority", "authority"):
        value = metadata.get(key)
        if value is not None and _float(value) is None:
            return str(value).strip().lower()
    if authority_score >= HIGH_AUTHORITY_THRESHOLD:
        return "high"
    if authority_score < LOW_AUTHORITY_THRESHOLD:
        return "low"
    return "medium"


def _is_canonical(metadata: dict[str, Any]) -> bool:
    for key in ("canonical", "is_canonical", "source_of_truth"):
        if _bool(metadata.get(key)):
            return True
    value = metadata.get("canonical_source")
    if isinstance(value, bool):
        return value
    if str(value or "").strip().lower() in {"true", "yes", "1", "canonical", "official", "source_of_truth"}:
        return True
    return False


def _is_stale(metadata: dict[str, Any]) -> bool:
    if _bool(metadata.get("stale")):
        return True
    status = str(metadata.get("source_status") or metadata.get("freshness") or metadata.get("freshness_status") or "").lower()
    return status in {"stale", "stale_source", GROUNDED_BUT_STALE, "stale_or_version_conflicted"}


def _metadata_status(metadata: dict[str, Any]) -> str:
    for key in ("source_status", "freshness", "freshness_status"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def _source_group(context: Any, metadata: dict[str, Any]) -> str:
    canonical = metadata.get("canonical_source")
    if canonical is not None and not isinstance(canonical, bool):
        value = str(canonical).strip()
        if value and value.lower() not in {"true", "false", "yes", "no", "1", "0"}:
            return _clean_source_key(value)
    for key in ("source_group", "source_family", "document_family", "source", "document", "path", "file"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return _clean_source_key(value)
    return _clean_source_key(str(getattr(context, "id", "") or "unknown"))


def _clean_source_key(value: str) -> str:
    text = value.replace("\\", "/").strip().lower()
    text = text.rsplit("/", 1)[-1]
    text = re.sub(r"v?\d+(?:[._-]\d+)*", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "unknown"


def _timestamp(metadata: dict[str, Any]) -> datetime | None:
    value = _timestamp_label(metadata)
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(value[:10], fmt)
        except ValueError:
            continue
    return None


def _timestamp_label(metadata: dict[str, Any]) -> str:
    for key in ("source_timestamp", "updated_at", "published_at", "created_at", "timestamp", "date"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def _version_tuple(metadata: dict[str, Any]) -> tuple[int, ...]:
    value = _version_label(metadata)
    if not value:
        return ()
    numbers = [int(part) for part in re.findall(r"\d+", value)]
    return tuple(numbers)


def _version_label(metadata: dict[str, Any]) -> str:
    for key in ("source_version", "version", "doc_version", "revision"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
