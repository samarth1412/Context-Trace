"""Dedicated fail-closed checker for observable claim/evidence conflicts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from contexttrace.verify.facts import compare_facts
from contexttrace.verify.judges import ClaimJudge, JudgeVerdict
from contexttrace.verify.schema import TraceContext

from .bounded import fact_scope_complexity

OBSERVABLE_CONFLICT_GUARD_VERSION = "observable-conflict-guard-v1.0.0"

_ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9_-]{1,}\b")
_PATH_RE = re.compile(r"(?<!\w)/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+")
_RELATION_RE = re.compile(
    r"^\s*(?P<subject>.+?)\s+"
    r"(?P<verb>approves?|calls?|invokes?|writes?|reads?|sends?|returns?|creates?|deletes?)\s+"
    r"(?P<object>.+?)\s*[.!?]?\s*$",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_GUARDED_FACT_TYPES = {
    "date",
    "negation",
    "numeric",
    "path",
    "relation",
    "status",
    "version",
}
_OPPOSED_STATUS_TERMS = (
    ("active", "deprecated"),
    ("current", "superseded"),
    ("enabled", "disabled"),
)
_CONDITION_RE = re.compile(r"\b(?:if|unless|only if|provided that)\b", re.IGNORECASE)
_SCOPE_RE = re.compile(
    r"\b(?:only\s+)?for\s+"
    r"(?P<scope>local development|beta users?|enterprise accounts?|administrators?)\b",
    re.IGNORECASE,
)
_BOUNDARY_RE = re.compile(
    r"\b(?P<operator>under|below|less than|over|more than|at most|up to)\s+"
    r"(?P<value>\d+(?:\.\d+)?)\b",
    re.IGNORECASE,
)
_TEMPORAL_VERSION_RE = re.compile(
    r"\b(?P<relation>after|before|in)\s+(?P<value>v?\d+(?:\.\d+)*)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ObservableConflict:
    category: str
    claim_value: str
    evidence_value: str | None = None
    resolution: str = "contradicted"

    def to_dict(self) -> dict[str, str | None]:
        return {
            "category": self.category,
            "claim_value": self.claim_value,
            "evidence_value": self.evidence_value,
            "resolution": self.resolution,
        }


class ObservableConflictGuard:
    """Prevent an NLI entailment from overriding explicit conflicting facts.

    This is intentionally narrower than a general semantic verifier. It changes
    only a base ``supported`` verdict and only when the exact evidence selected by
    that base checker exposes a structured conflict.
    """

    provider = "contexttrace_observable_conflict_guard"

    def __init__(self, base: ClaimJudge) -> None:
        self._base = base
        self.model = getattr(base, "model", None)

    def verify_claim(
        self,
        *,
        query: str,
        claim: str,
        contexts: list[TraceContext],
    ) -> JudgeVerdict:
        base = self._base.verify_claim(
            query=query,
            claim=claim,
            contexts=contexts,
        )
        if base.verdict != "supported":
            return base

        selected = _selected_context(base, contexts)
        if selected is None:
            return base
        evidence = _evidence_text(selected.text)
        conflicts = observable_conflicts(claim, evidence)
        if not conflicts:
            return base

        conflict_records = [conflict.to_dict() for conflict in conflicts]
        resolution = (
            "contradicted"
            if any(conflict.resolution == "contradicted" for conflict in conflicts)
            else "unsupported"
        )
        raw: dict[str, Any] = dict(base.raw)
        raw.update(
            {
                "nli_label": (
                    "contradiction" if resolution == "contradicted" else "neutral"
                ),
                "base_verdict": base.verdict,
                "base_confidence": base.confidence,
                "base_provider": base.provider,
                "observable_conflict_guard": {
                    "version": OBSERVABLE_CONFLICT_GUARD_VERSION,
                    "conflicts": conflict_records,
                },
            }
        )
        return JudgeVerdict(
            verdict=resolution,
            confidence=round(max(0.9, float(base.confidence)), 6),
            reason=(
                "The selected evidence exposes an observable conflict that "
                "prevents an entailment verdict."
            ),
            missing_facts=(
                [conflict.claim_value for conflict in conflicts]
                if resolution == "unsupported"
                else []
            ),
            conflicting_facts=(
                [conflict.claim_value for conflict in conflicts]
                if resolution == "contradicted"
                else []
            ),
            provider=self.provider,
            model=base.model,
            raw=raw,
        )


def observable_conflicts(claim: str, evidence: str) -> list[ObservableConflict]:
    """Return stable, deduplicated conflicts supported by surface observables."""

    conflicts: list[ObservableConflict] = []
    if not fact_scope_complexity(claim)["guarded"]:
        fact_match = compare_facts(claim, evidence, mode="semantic")
        for fact in fact_match.conflicting_fact_details:
            if fact.type not in _GUARDED_FACT_TYPES:
                continue
            conflicts.append(
                ObservableConflict(category=fact.type, claim_value=fact.text)
            )

    relation = _reversed_relation(claim, evidence)
    if relation is not None:
        conflicts.append(relation)
    acronym = _acronym_substitution(claim, evidence)
    if acronym is not None:
        conflicts.append(acronym)
    path = _path_substitution(claim, evidence)
    if path is not None:
        conflicts.append(path)
    status = _opposed_status(claim, evidence)
    if status is not None:
        conflicts.append(status)
    for conflict in (
        _condition_omission(claim, evidence),
        _scope_omission(claim, evidence),
        _numeric_boundary_conflict(claim, evidence),
        _temporal_version_conflict(claim, evidence),
    ):
        if conflict is not None:
            conflicts.append(conflict)
    return _deduplicate(conflicts)


def _selected_context(
    verdict: JudgeVerdict,
    contexts: list[TraceContext],
) -> TraceContext | None:
    context_id = str(verdict.raw.get("context_id") or "").strip()
    if context_id:
        for context in contexts:
            if context.id == context_id:
                return context
    if len(contexts) == 1:
        return contexts[0]
    return None


def _evidence_text(text: str) -> str:
    value = str(text or "")
    marker = "\nEvidence: "
    if value.startswith("Question: ") and marker in value:
        return value.split(marker, 1)[1]
    return value


def _reversed_relation(claim: str, evidence: str) -> ObservableConflict | None:
    claim_relation = _relation(claim)
    if claim_relation is None:
        return None
    for clause in re.split(r"(?<=[.!?])\s+|[;\n]+", evidence):
        evidence_relation = _relation(clause)
        if evidence_relation is None:
            continue
        claim_subject, claim_verb, claim_object = claim_relation
        evidence_subject, evidence_verb, evidence_object = evidence_relation
        if (
            claim_verb == evidence_verb
            and claim_subject == evidence_object
            and claim_object == evidence_subject
        ):
            return ObservableConflict(
                category="reversed_relation",
                claim_value=claim.strip(),
                evidence_value=clause.strip(),
            )
    return None


def _relation(text: str) -> tuple[str, str, str] | None:
    match = _RELATION_RE.match(str(text or ""))
    if match is None:
        return None
    return (
        _normalize_phrase(match.group("subject")),
        _normalize_verb(match.group("verb")),
        _normalize_phrase(match.group("object")),
    )


def _normalize_verb(value: str) -> str:
    verb = value.casefold()
    return verb.removesuffix("s")


def _normalize_phrase(value: str) -> str:
    return " ".join(_WORD_RE.findall(value.casefold()))


def _acronym_substitution(
    claim: str,
    evidence: str,
) -> ObservableConflict | None:
    claim_acronyms = set(_ACRONYM_RE.findall(claim))
    evidence_acronyms = set(_ACRONYM_RE.findall(evidence))
    claim_only = claim_acronyms - evidence_acronyms
    evidence_only = evidence_acronyms - claim_acronyms
    shared = claim_acronyms & evidence_acronyms
    if len(claim_only) != 1 or len(evidence_only) != 1 or not shared:
        return None
    if _non_acronym_overlap(claim, evidence) < 0.7:
        return None
    return ObservableConflict(
        category="identifier_substitution",
        claim_value=next(iter(claim_only)),
        evidence_value=next(iter(evidence_only)),
    )


def _non_acronym_overlap(left: str, right: str) -> float:
    left_tokens = {
        token.casefold()
        for token in _WORD_RE.findall(_ACRONYM_RE.sub(" ", left))
        if len(token) > 2
    }
    right_tokens = {
        token.casefold()
        for token in _WORD_RE.findall(_ACRONYM_RE.sub(" ", right))
        if len(token) > 2
    }
    if not left_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens)


def _path_substitution(claim: str, evidence: str) -> ObservableConflict | None:
    claim_paths = set(_PATH_RE.findall(claim))
    evidence_paths = set(_PATH_RE.findall(evidence))
    claim_only = claim_paths - evidence_paths
    evidence_only = evidence_paths - claim_paths
    if len(claim_only) != 1 or len(evidence_only) != 1:
        return None
    if _surface_overlap(_PATH_RE.sub(" ", claim), _PATH_RE.sub(" ", evidence)) < 0.7:
        return None
    return ObservableConflict(
        category="path_substitution",
        claim_value=next(iter(claim_only)),
        evidence_value=next(iter(evidence_only)),
    )


def _opposed_status(claim: str, evidence: str) -> ObservableConflict | None:
    claim_lower = claim.casefold()
    evidence_lower = evidence.casefold()
    for left, right in _OPPOSED_STATUS_TERMS:
        if left in claim_lower and right in evidence_lower:
            claim_value, evidence_value = left, right
        elif right in claim_lower and left in evidence_lower:
            claim_value, evidence_value = right, left
        else:
            continue
        stripped_claim = re.sub(rf"\b(?:{left}|{right})\b", " ", claim_lower)
        stripped_evidence = re.sub(rf"\b(?:{left}|{right})\b", " ", evidence_lower)
        if _surface_overlap(stripped_claim, stripped_evidence) >= 0.7:
            return ObservableConflict(
                category="status",
                claim_value=claim_value,
                evidence_value=evidence_value,
            )
    return None


def _surface_overlap(left: str, right: str) -> float:
    left_tokens = {
        token.casefold() for token in _WORD_RE.findall(left) if len(token) > 2
    }
    right_tokens = {
        token.casefold() for token in _WORD_RE.findall(right) if len(token) > 2
    }
    if not left_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens)


def _condition_omission(claim: str, evidence: str) -> ObservableConflict | None:
    match = _CONDITION_RE.search(evidence)
    if match is None or _CONDITION_RE.search(claim) is not None:
        return None
    if _surface_overlap(claim, evidence[: match.start()]) < 0.7:
        return None
    return ObservableConflict(
        category="condition_omission",
        claim_value=claim.strip(),
        evidence_value=evidence[match.start() :].strip(),
        resolution="unsupported",
    )


def _scope_omission(claim: str, evidence: str) -> ObservableConflict | None:
    match = _SCOPE_RE.search(evidence)
    if match is None or match.group(0).casefold() in claim.casefold():
        return None
    if _surface_overlap(claim, evidence[: match.start()]) < 0.7:
        return None
    return ObservableConflict(
        category="scope_omission",
        claim_value=claim.strip(),
        evidence_value=match.group(0),
        resolution="unsupported",
    )


def _numeric_boundary_conflict(
    claim: str,
    evidence: str,
) -> ObservableConflict | None:
    evidence_match = _BOUNDARY_RE.search(evidence)
    if evidence_match is None:
        return None
    value = evidence_match.group("value")
    claim_match = _BOUNDARY_RE.search(claim)
    if claim_match is not None and claim_match.group("operator").casefold() == (
        evidence_match.group("operator").casefold()
    ):
        return None
    if re.search(rf"\b{re.escape(value)}\b", claim) is None:
        return None
    if _surface_overlap(claim, evidence) < 0.6:
        return None
    return ObservableConflict(
        category="numeric_boundary",
        claim_value=value,
        evidence_value=evidence_match.group(0),
    )


def _temporal_version_conflict(
    claim: str,
    evidence: str,
) -> ObservableConflict | None:
    claim_match = _TEMPORAL_VERSION_RE.search(claim)
    evidence_match = _TEMPORAL_VERSION_RE.search(evidence)
    if claim_match is None or evidence_match is None:
        return None
    if (
        claim_match.group("value").casefold()
        != evidence_match.group("value").casefold()
    ):
        return None
    claim_relation = claim_match.group("relation").casefold()
    evidence_relation = evidence_match.group("relation").casefold()
    if claim_relation == evidence_relation:
        return None
    if _surface_overlap(claim, evidence) < 0.7:
        return None
    return ObservableConflict(
        category="temporal_boundary",
        claim_value=claim_match.group(0),
        evidence_value=evidence_match.group(0),
    )


def _deduplicate(conflicts: list[ObservableConflict]) -> list[ObservableConflict]:
    unique: list[ObservableConflict] = []
    seen: set[tuple[str, str, str | None, str]] = set()
    for conflict in conflicts:
        key = (
            conflict.category,
            conflict.claim_value,
            conflict.evidence_value,
            conflict.resolution,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(conflict)
    return unique
