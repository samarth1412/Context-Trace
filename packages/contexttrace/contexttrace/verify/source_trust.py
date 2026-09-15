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
CURRENT_CANONICAL_SOURCE = "current_canonical_source"
GROUNDED_BUT_STALE = "grounded_but_stale"
GROUNDED_BUT_CONFLICTED = "grounded_but_conflicted"
GROUNDED_BY_LOW_AUTHORITY_SOURCE = "grounded_by_low_authority_source"
STALE_SOURCE = "stale_source"
CONFLICTING_SOURCE = "conflicting_source"
HISTORICAL_SOURCE = "historical_source"
LOW_AUTHORITY_THRESHOLD = 0.4
HIGH_AUTHORITY_THRESHOLD = 0.85


def attach_source_assessments(
    claims: list[dict[str, Any]],
    trace: RAGTrace,
    *,
    mode: str,
    metadata_free_reasoning: bool = False,
) -> list[dict[str, Any]]:
    contexts_by_id = {context.id: context for context in trace.contexts}
    return [
        {
            **claim,
            **_source_fields(
                claim,
                trace,
                contexts_by_id,
                mode=mode,
                metadata_free_reasoning=metadata_free_reasoning,
            ),
        }
        for claim in claims
    ]


def _source_fields(
    claim: dict[str, Any],
    trace: RAGTrace,
    contexts_by_id: dict[str, Any],
    *,
    mode: str,
    metadata_free_reasoning: bool,
) -> dict[str, Any]:
    assessment = source_assessment(
        claim,
        trace,
        contexts_by_id,
        mode=mode,
        metadata_free_reasoning=metadata_free_reasoning,
    )
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
    metadata_free_reasoning: bool = False,
) -> dict[str, Any]:
    if not metadata_free_reasoning:
        return _legacy_source_assessment(claim, trace, contexts_by_id, mode=mode)

    claim_text = str(claim.get("claim") or "")
    best_context_id = str(claim.get("best_context_id") or "")
    best_context = contexts_by_id.get(best_context_id)
    best_signal = _context_signal(best_context, claim_text, mode=mode) if best_context is not None else None
    context_signals = [
        _context_signal(context, claim_text, mode=mode)
        for context in trace.contexts
    ]
    attribution = _query_source_attribution(trace.query)
    if attribution and _claim_respects_source_attribution(claim_text, attribution):
        context_signals = [
            signal
            for signal in context_signals
            if attribution in str(signal.get("context_text") or "").lower()
        ] or context_signals
    supporting = [signal for signal in context_signals if signal["verdict"] == "supported"]
    conflicting = [
        signal
        for signal in context_signals
        if signal["verdict"] == "contradicted"
        or signal.get("claim_conflict")
        or _direct_polarity_conflict(claim_text, str(signal.get("evidence") or ""))
    ]
    if best_signal and best_signal.get("lifecycle_signal"):
        conflicting = [
            signal
            for signal in conflicting
            if not _historical_context_is_weaker(best_signal, signal)
        ]
    newer_sources = _newer_related_sources(best_signal, context_signals)
    stronger_conflicts = _stronger_conflicts(best_signal, conflicting)
    unresolved_conflicts = _unresolved_conflicts(best_signal, conflicting)
    explicit_status = _metadata_status(best_signal["metadata"] if best_signal else {})
    query_requests_current = _query_requests_current(trace.query)
    query_requires_current_source = _query_requires_current_source(trace.query)
    query_targets_historical = _query_targets_historical_source(trace.query, best_signal)
    return {
        "best_source": (
            _signal_summary(best_signal, include_metadata=True)
            if best_signal is not None
            else None
        ),
        "supporting_sources": _signal_summaries(supporting),
        "conflicting_sources": _signal_summaries(conflicting),
        "newer_related_sources": _signal_summaries(newer_sources),
        "stronger_conflicting_sources": _signal_summaries(stronger_conflicts),
        "unresolved_conflicting_sources": _signal_summaries(unresolved_conflicts),
        "has_conflict": bool(conflicting),
        "has_stronger_conflict": bool(stronger_conflicts),
        "has_unresolved_conflict": bool(unresolved_conflicts),
        "has_newer_related_source": bool(newer_sources),
        "has_superseding_conflict": any(
            str(signal.get("lifecycle_signal") or "") in {"replacement", "retirement", "deprecation"}
            for signal in newer_sources
        ),
        "has_direct_polarity_conflict": any(
            _direct_polarity_conflict(claim_text, str(signal.get("evidence") or ""))
            for signal in stronger_conflicts
        ),
        "explicit_source_status": explicit_status,
        "query_requests_current": query_requests_current,
        "query_requires_current_source": query_requires_current_source,
        "query_targets_historical_source": query_targets_historical,
        "query_temporal_scope": (
            "historical"
            if query_targets_historical
            else "current_required"
            if query_requires_current_source
            else "unspecified"
        ),
        "query_currentness_basis": (
            "explicit_currentness"
            if query_requests_current
            else "operational_normative"
            if query_requires_current_source
            else "none"
        ),
        "inference_basis": _assessment_inference_basis(
            best_signal,
            newer_sources,
            stronger_conflicts,
            unresolved_conflicts,
        ),
    }


def source_status_from_assessment(claim: dict[str, Any], assessment: dict[str, Any]) -> str:
    verdict = str(claim.get("verdict") or "")
    best = assessment.get("best_source") or {}
    explicit_status = str(assessment.get("explicit_source_status") or "")
    if not best:
        return "no_source"
    if verdict != "supported":
        # A current source contradicting the *answer* is not itself a source conflict.
        # Reserve this label for disagreement among retrieved sources.
        if assessment.get("has_stronger_conflict"):
            return CONFLICTING_SOURCE
        if explicit_status in {"stale", "stale_source", GROUNDED_BUT_STALE}:
            return STALE_SOURCE
        if explicit_status == "incomplete":
            return "incomplete"
        if explicit_status in {"current", "fresh", "active", "latest"} and (
            bool(best.get("canonical")) or float(best.get("authority_score") or 0.0) >= HIGH_AUTHORITY_THRESHOLD
        ):
            return CURRENT_CANONICAL_SOURCE
        if explicit_status:
            return explicit_status
        if bool(best.get("canonical")) or float(best.get("authority_score") or 0.0) >= HIGH_AUTHORITY_THRESHOLD:
            return CURRENT_CANONICAL_SOURCE
        return GROUNDING_SOURCE_UNKNOWN
    explicitly_stale = explicit_status in {
        GROUNDED_BUT_STALE,
        STALE_SOURCE,
        "stale_or_version_conflicted",
    } or bool(best.get("stale"))
    if "query_requires_current_source" not in assessment:
        if explicitly_stale and assessment.get("query_requests_current"):
            return GROUNDED_BUT_STALE
        if assessment.get("has_direct_polarity_conflict"):
            return GROUNDED_BUT_CONFLICTED
        if assessment.get("has_newer_related_source"):
            return GROUNDED_BUT_STALE
        if assessment.get("has_stronger_conflict"):
            return GROUNDED_BUT_CONFLICTED
        if explicitly_stale:
            return GROUNDED_BUT_STALE
        if float(best.get("authority_score") or 0.0) < LOW_AUTHORITY_THRESHOLD:
            return GROUNDED_BY_LOW_AUTHORITY_SOURCE
        if bool(best.get("canonical")) or float(best.get("authority_score") or 0.0) >= HIGH_AUTHORITY_THRESHOLD:
            return SUPPORTED_BY_CANONICAL_SOURCE
        if explicit_status:
            return explicit_status
        return GROUNDING_SOURCE_UNKNOWN
    if (
        assessment.get("query_targets_historical_source")
        and not explicit_status
        and float(best.get("authority_score") or 0.0) >= LOW_AUTHORITY_THRESHOLD
    ):
        return HISTORICAL_SOURCE
    if explicitly_stale and assessment.get("query_requests_current"):
        return GROUNDED_BUT_STALE
    if assessment.get("has_newer_related_source"):
        return GROUNDED_BUT_STALE
    if (
        assessment.get("has_direct_polarity_conflict")
        or assessment.get("has_stronger_conflict")
        or assessment.get("has_unresolved_conflict")
    ):
        return GROUNDED_BUT_CONFLICTED
    if explicitly_stale:
        return GROUNDED_BUT_STALE
    if float(best.get("authority_score") or 0.0) < LOW_AUTHORITY_THRESHOLD:
        return GROUNDED_BY_LOW_AUTHORITY_SOURCE
    if bool(best.get("canonical")) or float(best.get("authority_score") or 0.0) >= HIGH_AUTHORITY_THRESHOLD:
        return SUPPORTED_BY_CANONICAL_SOURCE
    if explicit_status:
        return explicit_status
    return GROUNDING_SOURCE_UNKNOWN


def _legacy_source_assessment(
    claim: dict[str, Any],
    trace: RAGTrace,
    contexts_by_id: dict[str, Any],
    *,
    mode: str,
) -> dict[str, Any]:
    """Return the exact metadata-backed source assessment used by frozen v1."""

    claim_text = str(claim.get("claim") or "")
    best_context_id = str(claim.get("best_context_id") or "")
    best_context = contexts_by_id.get(best_context_id)
    best_signal = (
        _legacy_context_signal(best_context, claim_text, mode=mode)
        if best_context is not None
        else None
    )
    context_signals = [
        _legacy_context_signal(context, claim_text, mode=mode)
        for context in trace.contexts
    ]
    supporting = [signal for signal in context_signals if signal["verdict"] == "supported"]
    conflicting = [
        signal
        for signal in context_signals
        if signal["verdict"] == "contradicted"
        or _direct_polarity_conflict(claim_text, str(signal.get("evidence") or ""))
    ]
    newer_sources = _legacy_newer_related_sources(best_signal, context_signals)
    stronger_conflicts = _legacy_stronger_conflicts(best_signal, conflicting)
    explicit_status = _metadata_status(best_signal["metadata"] if best_signal else {})
    return {
        "best_source": best_signal,
        "supporting_sources": _legacy_signal_summaries(supporting),
        "conflicting_sources": _legacy_signal_summaries(conflicting),
        "newer_related_sources": _legacy_signal_summaries(newer_sources),
        "stronger_conflicting_sources": _legacy_signal_summaries(stronger_conflicts),
        "has_conflict": bool(conflicting),
        "has_stronger_conflict": bool(stronger_conflicts),
        "has_newer_related_source": bool(newer_sources),
        "has_direct_polarity_conflict": any(
            _direct_polarity_conflict(claim_text, str(signal.get("evidence") or ""))
            for signal in stronger_conflicts
        ),
        "explicit_source_status": explicit_status,
        "query_requests_current": _query_requests_current(trace.query),
    }


def _legacy_context_signal(context: Any, claim_text: str, *, mode: str) -> dict[str, Any]:
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


def _legacy_stronger_conflicts(
    best: dict[str, Any] | None,
    conflicting: list[dict[str, Any]],
) -> list[dict[str, Any]]:
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


def _legacy_newer_related_sources(
    best: dict[str, Any] | None,
    signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
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


def _legacy_signal_summaries(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _query_requests_current(query: str) -> bool:
    return bool(
        re.search(
            r"\b(?:current|currently|latest|newest|now|today|active|in force|effective)\b",
            str(query or ""),
            flags=re.IGNORECASE,
        )
    )


def _query_requires_current_source(query: str) -> bool:
    """Return whether answering the query safely depends on operationally current guidance."""
    if _query_requests_current(query):
        return True
    return bool(
        re.search(
            r"\b(?:should|must|recommended|recommendation|recommend|best practice|"
            r"which\s+.{0,40}\s+use|how\s+(?:do|should|can)\s+.{0,40}\s+"
            r"(?:configure|create|deploy|integrate|migrate|use))\b",
            str(query or ""),
            flags=re.IGNORECASE,
        )
    )


def _query_targets_historical_source(query: str, best: dict[str, Any] | None) -> bool:
    text = str(query or "")
    if re.search(r"\b(?:historically|formerly|previously|at\s+the\s+time|used\s+to)\b", text, re.IGNORECASE):
        return True
    query_version, _ = _source_version({}, text)
    best_version = tuple((best or {}).get("version_sort") or [])
    return bool(query_version and best_version and _parse_version(query_version) == best_version)


def _query_source_attribution(query: str) -> str:
    match = re.search(
        r"\b(?:what|which)\s+(?:does|do|did)\s+(?:the\s+)?"
        r"([a-z][a-z0-9 _-]{0,48}?(?:guide|manual|policy|report|specification|notice))\s+say\b",
        str(query or ""),
        flags=re.IGNORECASE,
    )
    return match.group(1).strip().lower() if match else ""


def _claim_respects_source_attribution(claim: str, attribution: str) -> bool:
    text = str(claim or "").lower()
    return bool(
        attribution in text
        and not re.search(r"\b(?:both|all|every|each)\s+(?:the\s+)?(?:guides|manuals|policies|reports|sources)\b", text)
    )


def _historical_context_is_weaker(best: dict[str, Any], signal: dict[str, Any]) -> bool:
    if signal.get("context_id") == best.get("context_id"):
        return True
    text = str(signal.get("context_text") or "")
    return bool(
        best.get("lifecycle_signal")
        and not signal.get("lifecycle_signal")
        and re.search(r"\b(?:before|formerly|previously|historically|used\s+to)\b", text, re.IGNORECASE)
    )


def _direct_polarity_conflict(claim_text: str, evidence_text: str) -> bool:
    claim = str(claim_text or "").lower()
    evidence = str(evidence_text or "").lower()
    pairs = (
        ("enable", "disable"),
        ("allow", "prohibit"),
        ("permit", "forbid"),
        ("require", "optional"),
        ("increase", "decrease"),
        ("accept", "reject"),
    )
    paired = any(
        (left in claim and right in evidence)
        or (right in claim and left in evidence)
        for left, right in pairs
    )
    lifecycle_conflict = bool(
        re.search(r"\b(?:use|should use|can use)\b", claim)
        and re.search(
            r"\b(?:removed|retired|deprecated|renamed|moved|no longer|end.of.support|recommends? (?:migrating|migration))\b",
            evidence,
        )
    )
    return paired or lifecycle_conflict


def _context_signal(context: Any, claim_text: str, *, mode: str) -> dict[str, Any]:
    metadata = dict(getattr(context, "metadata", {}) or {})
    context_text = str(getattr(context, "text", "") or "")
    match = score_claim_against_context(claim_text, context, mode=mode)
    verification = classify_claim(
        Claim(id="source_check", text=claim_text),
        match,
        has_contexts=True,
        mode=mode,
    )
    timestamp_label, timestamp_origin = _source_timestamp(metadata, context_text)
    timestamp = _parse_timestamp(timestamp_label)
    version_label, version_origin = _source_version(metadata, context_text)
    version = _parse_version(version_label)
    authority_score = _authority_score(metadata)
    source_group, source_group_origin = _source_group_with_origin(context, metadata)
    lifecycle_signal = _lifecycle_signal(context_text, claim_text)
    return {
        "context_id": getattr(context, "id", None),
        "verdict": verification.verdict,
        "score": verification.best_score,
        "authority_score": authority_score,
        "authority_label": _authority_label(metadata, authority_score),
        "canonical": _is_canonical(metadata),
        "stale": _is_stale(metadata),
        "source_group": source_group,
        "source_group_origin": source_group_origin,
        "source_timestamp": timestamp_label,
        "timestamp_origin": timestamp_origin,
        "timestamp_sort": timestamp.timestamp() if timestamp else None,
        "source_version": version_label,
        "version_origin": version_origin,
        "version_sort": list(version) if version else None,
        "lifecycle_signal": lifecycle_signal,
        "lifecycle_origin": "content" if lifecycle_signal else "none",
        "metadata": metadata,
        "evidence": verification.evidence,
        "context_text": context_text,
        "claim_conflict": bool(
            verification.verdict == "contradicted"
            or _direct_polarity_conflict(claim_text, context_text)
            or _lifecycle_conflicts_with_claim(context_text, claim_text)
        ),
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
        conflict_authority = float(signal.get("authority_score") or 0.0)
        conflict_time = signal.get("timestamp_sort")
        conflict_version = tuple(signal.get("version_sort") or [])
        relation_basis: list[str] = []
        if bool(signal.get("canonical")) and not bool(best.get("canonical")):
            relation_basis.append("metadata:canonical")
        elif conflict_authority >= best_authority + 0.15:
            relation_basis.append("metadata:authority")
        elif _signals_related(best, signal) and conflict_time is not None and (best_time is None or conflict_time > best_time):
            relation_basis.append("%s:timestamp" % (signal.get("timestamp_origin") or "unknown"))
        elif _signals_related(best, signal) and conflict_version and (not best_version or conflict_version > best_version):
            relation_basis.append("%s:version" % (signal.get("version_origin") or "unknown"))
        elif _signals_related(best, signal) and signal.get("lifecycle_signal"):
            relation_basis.append("content:lifecycle_%s" % signal["lifecycle_signal"])
        if relation_basis:
            stronger.append({**signal, "relation_basis": relation_basis})
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
        if not _signals_related(best, signal):
            continue
        signal_time = signal.get("timestamp_sort")
        signal_version = tuple(signal.get("version_sort") or [])
        relation_basis: list[str] = []
        if signal_time is not None and (best_time is None or signal_time > best_time):
            relation_basis.append("%s:timestamp" % (signal.get("timestamp_origin") or "unknown"))
        elif signal_version and (not best_version or signal_version > best_version):
            relation_basis.append("%s:version" % (signal.get("version_origin") or "unknown"))
        if signal.get("claim_conflict") and signal.get("lifecycle_signal"):
            relation_basis.append("content:lifecycle_%s" % signal["lifecycle_signal"])
        if relation_basis:
            newer.append({**signal, "relation_basis": relation_basis})
    return newer


def _unresolved_conflicts(best: dict[str, Any] | None, conflicting: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not best:
        return []
    unresolved = []
    for signal in conflicting:
        if signal.get("context_id") == best.get("context_id"):
            continue
        if _conflict_is_weaker_than_best(best, signal):
            continue
        unresolved.append({**signal, "relation_basis": ["content:unresolved_disagreement"]})
    return unresolved


def _conflict_is_weaker_than_best(best: dict[str, Any], signal: dict[str, Any]) -> bool:
    if bool(best.get("canonical")) and not bool(signal.get("canonical")):
        return True
    best_authority = float(best.get("authority_score") or 0.0)
    signal_authority = float(signal.get("authority_score") or 0.0)
    if best_authority >= signal_authority + 0.15:
        return True
    if not _signals_related(best, signal):
        return False
    best_time = best.get("timestamp_sort")
    signal_time = signal.get("timestamp_sort")
    if best_time is not None and signal_time is not None and best_time > signal_time:
        return True
    best_version = tuple(best.get("version_sort") or [])
    signal_version = tuple(signal.get("version_sort") or [])
    return bool(best_version and signal_version and best_version > signal_version)


def _signals_related(best: dict[str, Any], signal: dict[str, Any]) -> bool:
    if _same_explicit_source_group(best, signal):
        return True
    return bool(signal.get("claim_conflict"))


def _same_explicit_source_group(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return bool(
        left.get("source_group") == right.get("source_group")
        and left.get("source_group_origin") == "metadata"
        and right.get("source_group_origin") == "metadata"
    )


def _signal_summaries(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_signal_summary(signal) for signal in signals]


def _signal_summary(
    signal: dict[str, Any],
    *,
    include_metadata: bool = False,
) -> dict[str, Any]:
    """Return the documented source signal without internal comparison fields."""

    summary = {
        "context_id": signal.get("context_id"),
        "verdict": signal.get("verdict"),
        "score": signal.get("score"),
        "authority_score": signal.get("authority_score"),
        "authority_label": signal.get("authority_label"),
        "canonical": signal.get("canonical"),
        "stale": signal.get("stale"),
        "source_group": signal.get("source_group"),
        "source_group_origin": signal.get("source_group_origin"),
        "source_timestamp": signal.get("source_timestamp"),
        "timestamp_origin": signal.get("timestamp_origin"),
        "source_version": signal.get("source_version"),
        "version_origin": signal.get("version_origin"),
        "lifecycle_signal": signal.get("lifecycle_signal"),
        "lifecycle_origin": signal.get("lifecycle_origin"),
        "relation_basis": list(signal.get("relation_basis") or []),
        "evidence": signal.get("evidence"),
    }
    if include_metadata:
        summary["metadata"] = dict(signal.get("metadata") or {})
    return summary


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
    return _source_group_with_origin(context, metadata)[0]


def _source_group_with_origin(context: Any, metadata: dict[str, Any]) -> tuple[str, str]:
    canonical = metadata.get("canonical_source")
    if canonical is not None and not isinstance(canonical, bool):
        value = str(canonical).strip()
        if value and value.lower() not in {"true", "false", "yes", "no", "1", "0"}:
            return _clean_source_key(value), "metadata"
    for key in ("source_group", "source_family", "document_family", "source", "document", "path", "file"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return _clean_source_key(value), "metadata"
    return _clean_source_key(str(getattr(context, "id", "") or "unknown")), "context_id"


def _clean_source_key(value: str) -> str:
    text = value.replace("\\", "/").strip().lower()
    text = text.rsplit("/", 1)[-1]
    text = re.sub(r"v?\d+(?:[._-]\d+)*", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "unknown"


def _timestamp(metadata: dict[str, Any]) -> datetime | None:
    value = _timestamp_label(metadata)
    return _parse_timestamp(value)


def _parse_timestamp(value: str) -> datetime | None:
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
    return _parse_version(value)


def _parse_version(value: str) -> tuple[int, ...]:
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


def _source_timestamp(metadata: dict[str, Any], text: str) -> tuple[str, str]:
    metadata_value = _timestamp_label(metadata)
    if metadata_value:
        return metadata_value, "metadata"
    match = re.search(
        r"\b(?:published|updated|revised|effective|dated|as\s+of)\s*(?:on\s+|:\s*)?"
        r"((?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2})\b",
        str(text or ""),
        flags=re.IGNORECASE,
    )
    return (match.group(1), "content") if match else ("", "none")


def _source_version(metadata: dict[str, Any], text: str) -> tuple[str, str]:
    metadata_value = _version_label(metadata)
    if metadata_value:
        return metadata_value, "metadata"
    match = re.search(
        r"\b(?:version|ver\.?|v)\s*[:#]?\s*(\d+(?:\.\d+){0,3})\b",
        str(text or ""),
        flags=re.IGNORECASE,
    )
    return (match.group(1), "content") if match else ("", "none")


def _lifecycle_signal(text: str, claim_text: str) -> str:
    content = str(text or "").lower()
    claim_tokens = set(re.findall(r"[a-z][a-z0-9_-]{2,}", str(claim_text or "").lower()))
    content_tokens = set(re.findall(r"[a-z][a-z0-9_-]{2,}", content))
    if not claim_tokens.intersection(content_tokens):
        return ""
    if re.search(r"\b(?:replaced|superseded)\s+by\b|\binstead\s+of\b|\buse\b.{0,60}\binstead\b", content):
        return "replacement"
    if re.search(r"\b(?:retired|removed|end[- ]of[- ]support|no\s+longer\s+supported)\b", content):
        return "retirement"
    if re.search(r"\bdeprecat(?:e|ed|ion)\b", content):
        return "deprecation"
    return ""


def _lifecycle_conflicts_with_claim(text: str, claim_text: str) -> bool:
    content = str(text or "").lower()
    claim = str(claim_text or "").lower()
    lifecycle_patterns = (
        r"\b([a-z][a-z0-9_.-]+)\s+(?:is|was|has\s+been)\s+"
        r"(?:deprecated\s+(?:and\s+)?)?(?:replaced|superseded)\s+by\b",
        r"\b([a-z][a-z0-9_.-]+)\s+(?:is|was|has\s+been)\s+"
        r"(?:deprecated|retired|removed)\b",
        r"\binstead\s+of\s+([a-z][a-z0-9_.-]+)\b",
    )
    for pattern in lifecycle_patterns:
        match = re.search(pattern, content)
        if match and re.search(r"\b%s\b" % re.escape(match.group(1)), claim):
            return True
    return False


def _assessment_inference_basis(
    best: dict[str, Any] | None,
    newer: list[dict[str, Any]],
    stronger: list[dict[str, Any]],
    unresolved: list[dict[str, Any]],
) -> list[str]:
    basis: list[str] = []
    signals = ([best] if best else []) + newer + stronger + unresolved
    for signal in signals:
        for value in signal.get("relation_basis") or []:
            if value not in basis:
                basis.append(str(value))
        for field in ("timestamp_origin", "version_origin", "lifecycle_origin"):
            origin = str(signal.get(field) or "")
            if origin in {"metadata", "content"}:
                value = "%s:%s" % (origin, field.removesuffix("_origin"))
                if value not in basis:
                    basis.append(value)
    return basis or ["none"]


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
