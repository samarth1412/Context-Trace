from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


NO_FAILURE = "no_failure_detected"


@dataclass(frozen=True)
class ReliabilityScore:
    score: int
    grade: str
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    components: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "grade": self.grade,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "recommendations": self.recommendations,
            "components": self.components,
        }


class ReliabilityScorer:
    """Practical, explainable diagnostic score for ContextTrace reports."""

    DEFAULT_WEIGHTS = {
        "citation_support": 0.35,
        "unsupported_claim_rate": 0.25,
        "failure_rate": 0.25,
        "retrieval_quality": 0.10,
        "abstention_quality": 0.10,
        "token_efficiency": 0.05,
    }

    def score(
        self,
        *,
        citation_support: Optional[float] = None,
        unsupported_claim_rate: Optional[float] = None,
        failure_rate: Optional[float] = None,
        retrieval_quality: Optional[float] = None,
        abstention_quality: Optional[float] = None,
        token_efficiency: Optional[float] = None,
    ) -> ReliabilityScore:
        raw_components = {
            "citation_support": _optional_clamp(citation_support),
            "unsupported_claim_rate": _invert(unsupported_claim_rate),
            "failure_rate": _invert(failure_rate),
            "retrieval_quality": _optional_clamp(retrieval_quality),
            "abstention_quality": _optional_clamp(abstention_quality),
            "token_efficiency": _optional_clamp(token_efficiency),
        }
        available = {
            key: value for key, value in raw_components.items() if value is not None
        }
        if not available:
            return ReliabilityScore(
                score=0,
                grade="F",
                weaknesses=["No evaluation metrics are available yet."],
                recommendations=["Run citation verification before using the reliability score."],
            )

        total_weight = sum(self.DEFAULT_WEIGHTS[key] for key in available)
        score = round(
            sum(
                available[key] * (self.DEFAULT_WEIGHTS[key] / total_weight)
                for key in available
            )
            * 100
        )
        score = max(0, min(100, score))
        strengths, weaknesses, recommendations = self._explain(
            citation_support=citation_support,
            unsupported_claim_rate=unsupported_claim_rate,
            failure_rate=failure_rate,
            retrieval_quality=retrieval_quality,
            abstention_quality=abstention_quality,
            token_efficiency=token_efficiency,
        )
        return ReliabilityScore(
            score=score,
            grade=_grade(score),
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            components={key: round(value * 100) for key, value in available.items()},
        )

    def score_trace(self, trace: Mapping[str, Any]) -> ReliabilityScore:
        evaluation = trace.get("evaluation") or {}
        if isinstance(evaluation.get("reliability"), dict):
            reliability = evaluation["reliability"]
            return ReliabilityScore(
                score=int(reliability.get("score", 0)),
                grade=str(reliability.get("grade", "F")),
                strengths=list(reliability.get("strengths") or []),
                weaknesses=list(reliability.get("weaknesses") or []),
                recommendations=list(reliability.get("recommendations") or []),
                components=dict(reliability.get("components") or {}),
            )

        scores = evaluation.get("scores") or _scores_from_citation_checks(evaluation)
        failure = evaluation.get("failure") or {}
        failure_type = str(failure.get("failure_type") or "unknown")
        answer = trace.get("answer") or {}
        return self.score(
            citation_support=_as_float(scores.get("citation_support")),
            unsupported_claim_rate=_as_float(scores.get("unsupported_claim_rate")),
            failure_rate=0.0 if failure_type == NO_FAILURE else 1.0,
            retrieval_quality=_retrieval_quality(trace.get("chunks") or []),
            abstention_quality=0.0 if failure_type == "should_have_abstained" else None,
            token_efficiency=_token_efficiency(answer.get("usage") or {}),
        )

    def _explain(
        self,
        *,
        citation_support: Optional[float],
        unsupported_claim_rate: Optional[float],
        failure_rate: Optional[float],
        retrieval_quality: Optional[float],
        abstention_quality: Optional[float],
        token_efficiency: Optional[float],
    ) -> tuple[list[str], list[str], list[str]]:
        strengths: list[str] = []
        weaknesses: list[str] = []
        recommendations: list[str] = []

        citation_support = _optional_clamp(citation_support)
        unsupported_claim_rate = _optional_clamp(unsupported_claim_rate)
        failure_rate = _optional_clamp(failure_rate)
        retrieval_quality = _optional_clamp(retrieval_quality)
        abstention_quality = _optional_clamp(abstention_quality)
        token_efficiency = _optional_clamp(token_efficiency)

        if citation_support is not None:
            if citation_support >= 0.85:
                strengths.append("Citations are usually supported by the cited evidence.")
            elif citation_support < 0.60:
                weaknesses.append("Citation support is weak across evaluated claims.")
                recommendations.append("Add claim-level citation checks before returning answers.")
            else:
                weaknesses.append("Citation support is mixed and needs targeted review.")
                recommendations.append("Review low-support citations and improve source selection.")

        if unsupported_claim_rate is not None:
            if unsupported_claim_rate <= 0.10:
                strengths.append("Unsupported claims are uncommon in this evaluation.")
            elif unsupported_claim_rate >= 0.30:
                weaknesses.append("Unsupported claims appear frequently.")
                recommendations.append("Constrain generation to selected evidence and add abstention rules.")
            else:
                weaknesses.append("Unsupported claims are present at a noticeable rate.")
                recommendations.append("Tighten answer generation around cited chunks.")

        if failure_rate is not None:
            if failure_rate <= 0.05:
                strengths.append("Few evaluated traces produced classified failures.")
            else:
                weaknesses.append("A meaningful share of traces produced classified failures.")
                recommendations.append("Prioritize the most common failure type before tuning prompts.")

        if retrieval_quality is not None:
            if retrieval_quality >= 0.75:
                strengths.append("Retrieved or selected context has strong relevance signals.")
            else:
                weaknesses.append("Retrieval relevance signals are low.")
                recommendations.append("Try hybrid retrieval, reranking, or better metadata filters.")

        if abstention_quality is not None:
            if abstention_quality >= 0.75:
                strengths.append("Abstention behavior looks aligned with available evidence.")
            else:
                weaknesses.append("The system likely answered when it should have abstained.")
                recommendations.append("Add low-confidence abstention thresholds and user-facing uncertainty.")

        if token_efficiency is not None:
            if token_efficiency >= 0.75:
                strengths.append("Token usage is within a reasonable diagnostic budget.")
            else:
                weaknesses.append("Token usage is high relative to the logged answer.")
                recommendations.append("Reduce context size or use compression that preserves citation-bearing text.")

        if not recommendations:
            recommendations.append("Keep monitoring this score alongside the raw reliability metrics.")

        return strengths, weaknesses, _dedupe(recommendations)


def _scores_from_citation_checks(evaluation: Mapping[str, Any]) -> dict[str, float]:
    checks = evaluation.get("citation_checks") or []
    if not checks:
        return {"citation_support": 0.0, "unsupported_claim_rate": 1.0}
    support_scores = [float(check.get("support_score") or 0.0) for check in checks]
    unsupported = [
        check
        for check in checks
        if check.get("verdict") in {"unsupported", "contradicted", "not_enough_info"}
    ]
    return {
        "citation_support": round(sum(support_scores) / len(support_scores), 3),
        "unsupported_claim_rate": round(len(unsupported) / len(checks), 3),
    }


def _retrieval_quality(chunks: list[Mapping[str, Any]]) -> Optional[float]:
    selected_scores = [
        _as_float(chunk.get("relevance_score"))
        for chunk in chunks
        if chunk.get("selected") and _as_float(chunk.get("relevance_score")) is not None
    ]
    all_scores = [
        _as_float(chunk.get("relevance_score"))
        for chunk in chunks
        if _as_float(chunk.get("relevance_score")) is not None
    ]
    values = selected_scores or all_scores
    if not values:
        return None
    return round(sum(value for value in values if value is not None) / len(values), 3)


def _token_efficiency(usage: Mapping[str, Any]) -> Optional[float]:
    total_tokens = _as_float(usage.get("total_tokens"))
    if total_tokens is None:
        return None
    if total_tokens <= 2000:
        return 1.0
    if total_tokens >= 12000:
        return 0.0
    return round(1.0 - ((total_tokens - 2000) / 10000), 3)


def _invert(value: Optional[float]) -> Optional[float]:
    clamped = _optional_clamp(value)
    if clamped is None:
        return None
    return 1.0 - clamped


def _optional_clamp(value: Optional[float]) -> Optional[float]:
    value = _as_float(value)
    if value is None:
        return None
    return max(0.0, min(1.0, value))


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 45:
        return "D"
    return "F"


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique
