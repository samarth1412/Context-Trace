from __future__ import annotations

from statistics import mean
from typing import Any


FAILURE_VERDICTS = {"partially_supported", "unsupported", "unverifiable", "contradicted"}


def build_triage_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = result.get("summary") or {}
    claims = [claim for claim in result.get("claims") or [] if isinstance(claim, dict)]
    failures = [claim for claim in claims if claim.get("verdict") in FAILURE_VERDICTS]
    lead = failures[0] if failures else (claims[0] if claims else {})
    root = lead.get("root_cause") if isinstance(lead.get("root_cause"), dict) else {}
    citation_issues = [
        str(claim.get("citation_status"))
        for claim in claims
        if claim.get("citation_status") not in {None, "citation_aligned", "claim_has_no_citation"}
    ]
    confidences = [float(claim.get("confidence")) for claim in failures if claim.get("confidence") is not None]
    failure = str(summary.get("failure_type") or "no_failure_detected")
    risk = _risk_level(summary, failures)
    claim_text = str(lead.get("claim") or "No failed claim detected.")
    return {
        "most_likely_failure": failure,
        "why_it_happened": str(root.get("reason") or lead.get("reason") or "No evidence-chain failure was detected."),
        "evidence": str(lead.get("evidence") or "No evidence span selected."),
        "citation_issue": ", ".join(sorted(set(citation_issues))) or "none",
        "one_next_fix": str(root.get("suggested_fix") or summary.get("suggested_fix") or "No fix needed."),
        "regression_test": "Assert %s for claim: %s" % (failure, claim_text),
        "risk_level": risk,
        "confidence": round(mean(confidences), 3) if confidences else 1.0,
    }


def render_triage_summary(result: dict[str, Any]) -> str:
    triage = build_triage_summary(result)
    return "\n".join(
        [
            "Developer Triage Summary",
            "- Most likely failure: %s" % triage["most_likely_failure"],
            "- Why it happened: %s" % triage["why_it_happened"],
            "- Evidence: %s" % triage["evidence"],
            "- Citation issue: %s" % triage["citation_issue"],
            "- One next fix: %s" % triage["one_next_fix"],
            "- Regression test: %s" % triage["regression_test"],
            "- Risk level: %s" % triage["risk_level"],
            "- Confidence: %.3f" % triage["confidence"],
        ]
    )


def _risk_level(summary: dict[str, Any], failures: list[dict[str, Any]]) -> str:
    if bool(summary.get("should_abstain")) or any(claim.get("verdict") == "contradicted" for claim in failures):
        return "high"
    if failures:
        return "medium"
    return "low"
