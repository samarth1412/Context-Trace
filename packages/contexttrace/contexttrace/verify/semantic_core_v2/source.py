"""Observable-only source-condition assessment."""

from __future__ import annotations

from typing import Any

from contexttrace.verify.schema import RAGTrace, TraceContext

from .profile import V2Profile


_CONDITIONS = {
    "current_canonical",
    "current_noncanonical",
    "stale",
    "superseded",
    "low_authority",
    "conflicting_authorities",
    "unknown",
}


def assess_source_condition(
    *,
    best_context_id: str | None,
    trace: RAGTrace,
    profile: V2Profile,
) -> dict[str, Any]:
    if not profile.source_condition_features:
        return _record("unknown", "source_features_disabled")
    contexts = {context.id: context for context in trace.contexts}
    best = contexts.get(str(best_context_id or ""))
    if best is None:
        return _record("unknown", "no_selected_source")
    metadata = dict(best.metadata or {})

    explicit = _condition(metadata)
    if explicit != "unknown":
        return _record(
            explicit,
            "explicit_source_metadata",
            context_id=best.id,
            metadata=metadata,
        )
    if _is_superseded(best, trace.contexts):
        return _record(
            "superseded",
            "another_context_explicitly_supersedes_selected_source",
            context_id=best.id,
            metadata=metadata,
        )
    if _has_explicit_authority_conflict(best, trace.contexts):
        return _record(
            "conflicting_authorities",
            "explicit_authority_conflict_metadata",
            context_id=best.id,
            metadata=metadata,
        )
    if _truthy(metadata, "stale", "is_stale"):
        return _record(
            "stale",
            "explicit_stale_flag",
            context_id=best.id,
            metadata=metadata,
        )
    authority = _authority_score(metadata)
    if authority is not None and authority < profile.thresholds.low_authority_score:
        return _record(
            "low_authority",
            "authority_score_below_frozen_threshold",
            context_id=best.id,
            metadata=metadata,
        )
    canonical = _canonical(metadata)
    current = _current(metadata)
    if canonical is True and current is not False:
        return _record(
            "current_canonical",
            "explicit_canonical_source",
            context_id=best.id,
            metadata=metadata,
        )
    if canonical is False and current is not False:
        return _record(
            "current_noncanonical",
            "explicit_noncanonical_source",
            context_id=best.id,
            metadata=metadata,
        )
    return _record(
        "unknown",
        "insufficient_source_metadata",
        context_id=best.id,
        metadata=metadata,
    )


def _condition(metadata: dict[str, Any]) -> str:
    values = (
        metadata.get("source_condition"),
        metadata.get("source_status"),
        metadata.get("freshness_status"),
    )
    aliases = {
        "canonical": "current_canonical",
        "current": "current_canonical",
        "fresh": "current_canonical",
        "noncanonical": "current_noncanonical",
        "stale_source": "stale",
        "grounded_but_stale": "stale",
        "stale_or_version_conflicted": "superseded",
        "low_authority_source": "low_authority",
        "grounded_by_low_authority_source": "low_authority",
        "conflicting_source": "conflicting_authorities",
        "grounded_but_conflicted": "conflicting_authorities",
    }
    for value in values:
        normalized = str(value or "").strip().casefold().replace("-", "_")
        normalized = aliases.get(normalized, normalized)
        if normalized in _CONDITIONS:
            return normalized
    if _truthy(metadata, "superseded", "is_superseded"):
        return "superseded"
    return "unknown"


def _is_superseded(best: TraceContext, contexts: list[TraceContext]) -> bool:
    for context in contexts:
        if context.id == best.id:
            continue
        value = context.metadata.get("supersedes")
        targets = value if isinstance(value, list) else [value]
        if best.id in {str(item) for item in targets if item is not None}:
            return True
    return False


def _has_explicit_authority_conflict(
    best: TraceContext,
    contexts: list[TraceContext],
) -> bool:
    if _truthy(best.metadata, "authority_conflict", "conflicting_authorities"):
        return True
    conflict_ids = best.metadata.get("conflicts_with")
    targets = conflict_ids if isinstance(conflict_ids, list) else [conflict_ids]
    known = {context.id for context in contexts}
    return bool(known & {str(item) for item in targets if item is not None})


def _authority_score(metadata: dict[str, Any]) -> float | None:
    value = metadata.get("authority_score")
    if not isinstance(value, (str, int, float)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, number))


def _canonical(metadata: dict[str, Any]) -> bool | None:
    for key in ("canonical", "is_canonical"):
        if key in metadata:
            return bool(metadata[key])
    label = str(metadata.get("authority") or "").casefold()
    if label in {"official", "canonical", "primary"}:
        return True
    if label in {"mirror", "summary", "third_party", "noncanonical"}:
        return False
    return None


def _current(metadata: dict[str, Any]) -> bool | None:
    if _truthy(metadata, "stale", "is_stale", "superseded", "is_superseded"):
        return False
    for key in ("current", "is_current"):
        if key in metadata:
            return bool(metadata[key])
    return None


def _truthy(metadata: dict[str, Any], *keys: str) -> bool:
    return any(bool(metadata.get(key)) for key in keys)


def _record(
    condition: str,
    reason_code: str,
    *,
    context_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = metadata or {}
    return {
        "condition": condition,
        "reason_code": reason_code,
        "context_id": context_id,
        "observables": {
            "canonical": _canonical(metadata),
            "current": _current(metadata),
            "authority_score": _authority_score(metadata),
            "publication_or_effective_at": metadata.get("effective_at")
            or metadata.get("published_at")
            or metadata.get("source_timestamp"),
            "source_version": metadata.get("source_version") or metadata.get("version"),
        },
    }
