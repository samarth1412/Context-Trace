"""Relational, observable-only source-condition reasoning for v2.1."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from contexttrace.verify.schema import RAGTrace, TraceContext

from .checker import observable_conflicts
from .profile import V21Profile

SOURCE_CONDITION_REASONER_VERSION = "source-condition-reasoner-v2.1.0"

_CONDITIONS = {
    "current_canonical",
    "current_noncanonical",
    "stale",
    "superseded",
    "low_authority",
    "conflicting_authorities",
    "unknown",
}
_CONDITION_ALIASES = {
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
_TRUE = {"1", "true", "yes", "y", "on"}
_FALSE = {"0", "false", "no", "n", "off", ""}
_VERSION_RE = re.compile(r"\d+")
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_MONTHS = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}
_CONFLICT_STOPWORDS = {"a", "an", "is", "on", "the", "to", "was"}
_LINEAGE_KEYS = (
    "source_family",
    "source_group",
    "document_family",
    "document_id",
    "logical_source",
    "policy_id",
    "api_name",
)
_TIME_KEYS = ("effective_at", "updated_at", "published_at", "source_timestamp")
_VERSION_KEYS = ("source_version", "version", "document_version", "api_version")
_AUTHORITY_LABEL_SCORES = {
    "official": 0.95,
    "canonical": 0.95,
    "primary": 0.95,
    "regulator": 0.95,
    "maintainer": 0.9,
    "secondary": 0.55,
    "mirror": 0.3,
    "summary": 0.25,
    "community": 0.25,
    "third_party": 0.25,
    "noncanonical": 0.25,
}


def assess_source_condition_v2_1(
    *,
    best_context_id: str | None,
    claim: str,
    trace: RAGTrace,
    profile: V21Profile,
) -> dict[str, Any]:
    """Assess selected-source condition from bounded, explicit observables."""

    if not profile.source_condition_features:
        return _record("unknown", "source_features_disabled")
    contexts = {context.id: context for context in trace.contexts}
    selected = contexts.get(str(best_context_id or ""))
    if selected is None:
        return _record("unknown", "no_selected_source")
    metadata = dict(selected.metadata or {})
    explicit = _condition(metadata)

    if explicit == "superseded" or _flag(metadata, "superseded", "is_superseded"):
        return _record(
            "superseded",
            "explicit_superseded_metadata",
            selected,
        )
    if explicit == "stale" or _flag(metadata, "stale", "is_stale"):
        return _record("stale", "explicit_stale_metadata", selected)

    replacement = _explicit_replacement(selected, trace.contexts)
    if replacement is not None:
        return _record(
            "superseded",
            "explicit_replacement_relation",
            selected,
            related=[replacement],
        )

    linked_conflicts = _linked_conflicts(selected, trace.contexts)
    if explicit == "conflicting_authorities" or linked_conflicts:
        return _record(
            "conflicting_authorities",
            "explicit_authority_conflict",
            selected,
            related=linked_conflicts,
        )

    conflicting = [
        context
        for context in trace.contexts
        if context.id != selected.id and _source_conflicts(claim, context.text)
    ]
    newer = [
        context
        for context in trace.contexts
        if context.id != selected.id
        and _same_lineage(selected, context)
        and _is_newer(selected, context)
    ]
    newer_conflicts = [context for context in newer if context in conflicting]
    if newer_conflicts:
        return _record(
            "superseded",
            "newer_related_source_conflicts_with_claim",
            selected,
            related=newer_conflicts,
        )
    if newer:
        return _record(
            "stale",
            "newer_related_source_observed",
            selected,
            related=newer,
        )

    selected_strength = _authority_score(metadata)
    strong_conflicts = [
        context
        for context in conflicting
        if _is_authoritative(context.metadata, profile)
        and _is_authoritative(metadata, profile)
    ]
    if strong_conflicts:
        return _record(
            "conflicting_authorities",
            "authoritative_sources_observably_conflict",
            selected,
            related=strong_conflicts,
        )

    if explicit == "low_authority" or (
        selected_strength is not None
        and selected_strength < profile.thresholds.low_authority_score
    ):
        return _record(
            "low_authority",
            "selected_source_below_authority_threshold",
            selected,
            related=conflicting,
        )

    canonical = _canonical(metadata)
    current = _current(metadata)
    if explicit == "current_noncanonical" or (
        canonical is False and current is not False
    ):
        return _record(
            "current_noncanonical",
            "explicit_noncanonical_source",
            selected,
            related=conflicting,
        )
    if explicit == "current_canonical" or (canonical is True and current is not False):
        return _record(
            "current_canonical",
            "explicit_current_canonical_source",
            selected,
            related=conflicting,
        )
    return _record(
        "unknown",
        "insufficient_source_metadata",
        selected,
        related=conflicting,
    )


def _condition(metadata: dict[str, Any]) -> str:
    for key in ("source_condition", "source_status", "freshness_status"):
        normalized = _normalize(metadata.get(key))
        normalized = _CONDITION_ALIASES.get(normalized, normalized)
        if normalized in _CONDITIONS:
            return normalized
    return "unknown"


def _explicit_replacement(
    selected: TraceContext,
    contexts: list[TraceContext],
) -> TraceContext | None:
    known = {context.id: context for context in contexts}
    for key in ("superseded_by", "replaced_by", "replacement_source_id"):
        for target in _ids(selected.metadata.get(key)):
            if target in known and target != selected.id:
                return known[target]
    for context in contexts:
        if context.id == selected.id:
            continue
        targets = set()
        for key in ("supersedes", "replaces", "replacement_for"):
            targets.update(_ids(context.metadata.get(key)))
        if selected.id in targets:
            return context
    return None


def _linked_conflicts(
    selected: TraceContext,
    contexts: list[TraceContext],
) -> list[TraceContext]:
    known = {context.id: context for context in contexts if context.id != selected.id}
    linked = set(_ids(selected.metadata.get("conflicts_with")))
    for context in contexts:
        if selected.id in set(_ids(context.metadata.get("conflicts_with"))):
            linked.add(context.id)
    if _flag(selected.metadata, "authority_conflict", "conflicting_authorities"):
        return list(known.values())
    return [known[context_id] for context_id in sorted(linked) if context_id in known]


def _same_lineage(left: TraceContext, right: TraceContext) -> bool:
    left_metadata = dict(left.metadata or {})
    right_metadata = dict(right.metadata or {})
    for key in _LINEAGE_KEYS:
        left_value = _normalize(left_metadata.get(key))
        right_value = _normalize(right_metadata.get(key))
        if left_value and left_value == right_value:
            return True
    return False


def _is_newer(selected: TraceContext, candidate: TraceContext) -> bool:
    selected_metadata = dict(selected.metadata or {})
    candidate_metadata = dict(candidate.metadata or {})
    selected_version = _version(selected_metadata)
    candidate_version = _version(candidate_metadata)
    if selected_version and candidate_version and candidate_version > selected_version:
        return True
    selected_time = _timestamp(selected_metadata)
    candidate_time = _timestamp(candidate_metadata)
    if selected_time and candidate_time and candidate_time > selected_time:
        return True
    return bool(
        _current(selected_metadata) is False and _current(candidate_metadata) is True
    )


def _is_authoritative(metadata: dict[str, Any], profile: V21Profile) -> bool:
    if _canonical(metadata) is True:
        return True
    score = _authority_score(metadata)
    return bool(score is not None and score >= profile.thresholds.high_authority_score)


def _source_conflicts(claim: str, evidence: str) -> bool:
    if observable_conflicts(claim, evidence):
        return True
    claim_words = {word.casefold() for word in _WORD_RE.findall(claim)}
    evidence_words = {word.casefold() for word in _WORD_RE.findall(evidence)}
    claim_months = claim_words & _MONTHS
    evidence_months = evidence_words & _MONTHS
    shared = (claim_words & evidence_words) - _CONFLICT_STOPWORDS - _MONTHS
    return bool(
        claim_months
        and evidence_months
        and claim_months != evidence_months
        and len(shared) >= 2
    )


def _canonical(metadata: dict[str, Any]) -> bool | None:
    for key in ("canonical", "is_canonical"):
        if key in metadata:
            return _boolean(metadata[key])
    label = _normalize(metadata.get("source_authority") or metadata.get("authority"))
    if label in {"official", "canonical", "primary", "regulator", "maintainer"}:
        return True
    if label in {"mirror", "summary", "community", "third_party", "noncanonical"}:
        return False
    return None


def _current(metadata: dict[str, Any]) -> bool | None:
    if _flag(metadata, "stale", "is_stale", "superseded", "is_superseded"):
        return False
    for key in ("current", "is_current"):
        if key in metadata:
            return _boolean(metadata[key])
    condition = _condition(metadata)
    if condition in {"current_canonical", "current_noncanonical"}:
        return True
    if condition in {"stale", "superseded"}:
        return False
    freshness = _normalize(metadata.get("freshness"))
    if freshness in {"current", "fresh", "active", "latest"}:
        return True
    if freshness in {"stale", "expired", "archived", "superseded"}:
        return False
    return None


def _authority_score(metadata: dict[str, Any]) -> float | None:
    value = metadata.get("authority_score")
    if isinstance(value, bool):
        return None
    if isinstance(value, (str, int, float)):
        try:
            number = float(value)
            return max(0.0, min(1.0, number)) if isfinite(number) else None
        except ValueError:
            pass
    label = _normalize(metadata.get("source_authority") or metadata.get("authority"))
    return _AUTHORITY_LABEL_SCORES.get(label)


def _version(metadata: dict[str, Any]) -> tuple[int, ...]:
    for key in _VERSION_KEYS:
        raw = tuple(
            int(value) for value in _VERSION_RE.findall(str(metadata.get(key) or ""))
        )
        if raw:
            values = list(raw)
            while len(values) > 1 and values[-1] == 0:
                values.pop()
            return tuple(values)
    return ()


def _version_label(metadata: dict[str, Any]) -> str | None:
    for key in _VERSION_KEYS:
        value = str(metadata.get(key) or "").strip()
        if value:
            return value[:128]
    return None


def _timestamp(metadata: dict[str, Any]) -> datetime | None:
    for key in _TIME_KEYS:
        value = str(metadata.get(key) or "").strip()
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _timestamp_label(metadata: dict[str, Any]) -> str | None:
    for key in _TIME_KEYS:
        value = str(metadata.get(key) or "").strip()
        if value:
            return value[:128]
    return None


def _boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in _TRUE:
            return True
        if normalized in _FALSE:
            return False
    return None


def _flag(metadata: dict[str, Any], *keys: str) -> bool:
    return any(_boolean(metadata.get(key)) is True for key in keys)


def _ids(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in values if str(item or "").strip()]


def _normalize(value: Any) -> str:
    return str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")


def _record(
    condition: str,
    reason_code: str,
    selected: TraceContext | None = None,
    *,
    related: list[TraceContext] | None = None,
) -> dict[str, Any]:
    metadata = dict(selected.metadata or {}) if selected is not None else {}
    return {
        "condition": condition,
        "reason_code": reason_code,
        "reasoner_version": SOURCE_CONDITION_REASONER_VERSION,
        "context_id": selected.id if selected is not None else None,
        "observables": {
            "canonical": _canonical(metadata),
            "current": _current(metadata),
            "authority_score": _authority_score(metadata),
            "publication_or_effective_at": _timestamp_label(metadata),
            "source_version": _version_label(metadata),
        },
        "related_sources": [
            {
                "context_id": context.id,
                "canonical": _canonical(context.metadata),
                "current": _current(context.metadata),
                "authority_score": _authority_score(context.metadata),
                "publication_or_effective_at": _timestamp_label(context.metadata),
                "source_version": _version_label(context.metadata),
            }
            for context in (related or [])[:8]
        ],
    }
