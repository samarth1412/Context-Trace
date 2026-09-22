"""Experimental local requirement-level evidence coverage verification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from contexttrace.verify.judges import ClaimJudge, JudgeVerdict
from contexttrace.verify.local_quality import select_local_evidence
from contexttrace.verify.schema import TraceContext


ATOMIC_COVERAGE_VERSION = "atomic_coverage_v2_experimental"

_RIGHT_HAND_PREDICATES = (
    "are|became|becomes|becoming|can|caused|causes|contains|continued|continues|"
    "did|does|featuring|features|had|has|have|includes|including|is|led|leads|"
    "made|makes|making|offers|provides|remained|remains|resulted|results|"
    "supports|was|were|will"
)


class AtomicCoverageError(RuntimeError):
    """Raised when the explicitly requested local coverage backend is invalid."""


@dataclass(frozen=True)
class AtomicCoverageProfile:
    spans_per_requirement: int = 3
    maximum_requirements: int = 6
    entailment_threshold: float = 0.70
    contradiction_threshold: float = 0.70
    review_threshold: float = 0.75
    maximum_combined_characters: int = 6000

    def __post_init__(self) -> None:
        if self.spans_per_requirement < 1:
            raise AtomicCoverageError("spans_per_requirement must be positive.")
        if self.maximum_requirements < 1:
            raise AtomicCoverageError("maximum_requirements must be positive.")
        for name in (
            "entailment_threshold",
            "contradiction_threshold",
            "review_threshold",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise AtomicCoverageError("%s must be between zero and one." % name)


@dataclass(frozen=True)
class RequirementCoverage:
    requirement: str
    status: str
    confidence: float
    evidence_context_ids: tuple[str, ...]
    evidence_texts: tuple[str, ...]
    nli_scores: dict[str, float]
    nli_label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement,
            "status": self.status,
            "confidence": self.confidence,
            "evidence_context_ids": list(self.evidence_context_ids),
            "evidence_texts": list(self.evidence_texts),
            "nli_scores": dict(self.nli_scores),
            "nli_label": self.nli_label,
        }


class AtomicCoverageJudge:
    """Verify locally by requiring evidence coverage for every claim requirement."""

    provider = "local_atomic_coverage"

    def __init__(
        self,
        *,
        nli: ClaimJudge,
        profile: AtomicCoverageProfile | None = None,
    ) -> None:
        self.nli = nli
        self.profile = profile or AtomicCoverageProfile()
        self.model = str(getattr(nli, "model", "") or "") or None
        if str(getattr(nli, "provider", "")).casefold() not in {
            "local_nli",
            "local_atomic_test",
        }:
            raise AtomicCoverageError("Atomic coverage requires an explicit local NLI provider.")

    def verify_claim(
        self,
        *,
        query: str,
        claim: str,
        contexts: list[TraceContext],
    ) -> JudgeVerdict:
        requirements = decompose_atomic_requirements(
            claim,
            maximum=self.profile.maximum_requirements,
        )
        coverage = [
            self._assess_requirement(query=query, requirement=value, contexts=contexts)
            for value in requirements
        ]
        verdict, confidence, reason = aggregate_coverage(coverage)
        review_required = bool(
            verdict == "unverifiable" or confidence < self.profile.review_threshold
        )
        return JudgeVerdict(
            verdict=verdict,
            confidence=confidence,
            reason=reason,
            matched_facts=[row.requirement for row in coverage if row.status == "covered"],
            missing_facts=[row.requirement for row in coverage if row.status == "missing"],
            conflicting_facts=[
                row.requirement for row in coverage if row.status == "contradicted"
            ],
            provider=self.provider,
            model=self.model,
            raw={
                "verifier_version": ATOMIC_COVERAGE_VERSION,
                "experimental": True,
                "local_only": True,
                "remote_inference": False,
                "review_required": review_required,
                "automatic_supported": verdict == "supported" and not review_required,
                "reason_code": reason,
                "requirements": [row.to_dict() for row in coverage],
                "coverage_summary": {
                    "requirements": len(coverage),
                    "covered": sum(row.status == "covered" for row in coverage),
                    "missing": sum(row.status == "missing" for row in coverage),
                    "contradicted": sum(
                        row.status == "contradicted" for row in coverage
                    ),
                },
                "profile": {
                    "spans_per_requirement": self.profile.spans_per_requirement,
                    "maximum_requirements": self.profile.maximum_requirements,
                    "entailment_threshold": self.profile.entailment_threshold,
                    "contradiction_threshold": self.profile.contradiction_threshold,
                    "review_threshold": self.profile.review_threshold,
                    "maximum_combined_characters": self.profile.maximum_combined_characters,
                },
                "backend": {
                    "provider": str(getattr(self.nli, "provider", "local_nli")),
                    "model": self.model,
                    "remote_inference": False,
                },
            },
        )

    def _assess_requirement(
        self,
        *,
        query: str,
        requirement: str,
        contexts: list[TraceContext],
    ) -> RequirementCoverage:
        selected = select_local_evidence(
            query=query,
            claim=requirement,
            contexts=contexts,
            limit=self.profile.spans_per_requirement,
        )
        selected_contexts = [
            TraceContext(
                id="%s:%s:%s" % (span.context_id, span.start_char, span.end_char),
                text=span.text,
                metadata={"source_context_id": span.context_id},
            )
            for span in selected
        ]
        if not selected_contexts:
            return RequirementCoverage(
                requirement=requirement,
                status="missing",
                confidence=1.0,
                evidence_context_ids=(),
                evidence_texts=(),
                nli_scores={"entailment": 0.0, "contradiction": 0.0, "neutral": 1.0},
                nli_label="neutral",
            )
        combined = _combined_context(
            selected_contexts,
            maximum_characters=self.profile.maximum_combined_characters,
        )
        result = self.nli.verify_claim(
            query="",
            claim=requirement,
            contexts=[combined],
        )
        scores = {
            key: float(value)
            for key, value in dict(result.raw.get("nli_scores") or {}).items()
            if key in {"entailment", "contradiction", "neutral"}
        }
        if set(scores) != {"entailment", "contradiction", "neutral"}:
            raise AtomicCoverageError("Local NLI did not return a three-way score distribution.")
        label = str(result.raw.get("nli_label") or "").casefold()
        entailment = scores["entailment"]
        contradiction = scores["contradiction"]
        if (
            contradiction >= self.profile.contradiction_threshold
            and contradiction > entailment
        ):
            status = "contradicted"
            confidence = contradiction
        elif entailment >= self.profile.entailment_threshold:
            status = "covered"
            confidence = entailment
        else:
            status = "missing"
            confidence = max(scores["neutral"], 1.0 - entailment)
        return RequirementCoverage(
            requirement=requirement,
            status=status,
            confidence=round(float(confidence), 4),
            evidence_context_ids=tuple(context.id for context in selected_contexts),
            evidence_texts=tuple(context.text for context in selected_contexts),
            nli_scores={key: round(value, 4) for key, value in scores.items()},
            nli_label=label,
        )


def decompose_atomic_requirements(claim: str, *, maximum: int = 6) -> list[str]:
    """Return conservative claim substrings as independently checked requirements."""

    normalized = " ".join(str(claim or "").split()).strip()
    if not normalized:
        return []
    pieces = re.split(
        r";+|,\s+(?:and|but|while|whereas)\s+|"
        r",\s+(?=(?:which|who|whose|where|making|becoming|including|featuring|"
        r"causing|leading|resulting)\b)",
        normalized,
        flags=re.IGNORECASE,
    )
    requirements = []
    for piece in pieces:
        coordinated = re.split(
            rf"\s+and\s+(?=(?:{_RIGHT_HAND_PREDICATES})\b)",
            piece,
            maxsplit=1,
            flags=re.IGNORECASE,
        )
        for value in coordinated:
            value = value.strip(" ,")
            if len(value.split()) < 2:
                continue
            if value[-1:] not in ".!?":
                value += "."
            if value not in requirements:
                requirements.append(value)
    return (requirements or [normalized])[:maximum]


def aggregate_coverage(
    coverage: Iterable[RequirementCoverage],
) -> tuple[str, float, str]:
    rows = list(coverage)
    if not rows:
        return "unverifiable", 0.0, "no_atomic_requirements"
    contradicted = [row for row in rows if row.status == "contradicted"]
    covered = [row for row in rows if row.status == "covered"]
    missing = [row for row in rows if row.status == "missing"]
    if contradicted:
        return (
            "contradicted",
            round(max(row.confidence for row in contradicted), 4),
            "one_or_more_requirements_contradicted",
        )
    if len(covered) == len(rows):
        return (
            "supported",
            round(min(row.confidence for row in covered), 4),
            "all_requirements_covered",
        )
    if covered and missing:
        return (
            "partially_supported",
            round(min(row.confidence for row in covered), 4),
            "some_requirements_missing",
        )
    return (
        "unsupported",
        round(min(row.confidence for row in missing), 4),
        "no_requirements_covered",
    )


def _combined_context(
    contexts: list[TraceContext], *, maximum_characters: int
) -> TraceContext:
    texts = []
    remaining = maximum_characters
    for context in contexts:
        if remaining <= 0:
            break
        value = context.text[:remaining]
        if value:
            texts.append(value)
            remaining -= len(value)
    return TraceContext(
        id="atomic:" + "+".join(context.id for context in contexts),
        text="\n".join(texts),
        metadata={"source_context_ids": [context.id for context in contexts]},
    )
