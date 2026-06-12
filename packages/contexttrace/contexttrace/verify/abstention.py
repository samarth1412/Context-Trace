from __future__ import annotations

from contexttrace.verify.claims import Claim
from contexttrace.verify.evidence import find_best_evidence
from contexttrace.verify.schema import TraceContext
from contexttrace.verify.verdicts import ClaimVerification


def judge_abstention(
    *,
    query: str,
    claims: list[Claim],
    contexts: list[TraceContext],
    verifications: list[ClaimVerification],
    mode: str = "lexical",
) -> dict[str, object]:
    if not claims:
        return {
            "should_abstain": False,
            "reason": "The answer does not contain factual claims that require evidence support.",
        }

    if not contexts:
        return {
            "should_abstain": True,
            "reason": "The answer contains factual claims, but no retrieved contexts were provided.",
        }

    total_claims = len(verifications)
    supported = len([item for item in verifications if item.verdict == "supported"])
    unsupported_like = len(
        [
            item
            for item in verifications
            if item.verdict in {"unsupported", "contradicted", "unverifiable"}
        ]
    )
    contradicted = len([item for item in verifications if item.verdict == "contradicted"])

    if supported > 0 and unsupported_like > 0 and contradicted == 0:
        return {
            "should_abstain": False,
            "partial_answer": True,
            "reason": (
                "The answer mixes supported claims with unsupported details; it should remove "
                "or qualify unsupported details rather than fully abstain."
            ),
        }

    query_match = find_best_evidence(query, contexts, mode=mode)
    if supported == 0 and query_match.score < 0.18:
        return {
            "should_abstain": True,
            "reason": (
                "The query asks for information that does not appear in the retrieved contexts, "
                "but the answer still gives a factual response."
            ),
        }

    if unsupported_like / total_claims >= 0.5:
        return {
            "should_abstain": True,
            "reason": (
                "The answer contains factual claims, but most important claims are unsupported "
                "or contradicted by the retrieved contexts."
            ),
        }

    if any(item.verdict == "partially_supported" for item in verifications):
        return {
            "should_abstain": False,
            "reason": (
                "At least one claim is only partially supported; the answer should remove "
                "or qualify unsupported details rather than fully abstain."
            ),
        }

    return {
        "should_abstain": False,
        "reason": "Most generated claims are supported by retrieved evidence.",
    }
