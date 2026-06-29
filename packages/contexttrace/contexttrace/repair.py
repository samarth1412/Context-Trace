from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contexttrace.diagnose import DiagnoseInputError, diagnose_trace_file
from contexttrace.verify.qa import qa_trace
from contexttrace.verify.schema import VerificationInputError, load_trace_file


REPAIR_SCHEMA_VERSION = "0.1"

_ACTION_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "retrieval_miss": [
        (
            "Increase retrieval recall with measured top-k, query-rewrite, or metadata-filter changes.",
            "The corpus contains support that was absent from the retrieved contexts.",
        ),
        (
            "Add the missed source to a retrieval regression set and verify that it is returned for this query.",
            "A retrieval fix needs a source-level acceptance check, not only a better final answer.",
        ),
    ],
    "reranking_failure": [
        (
            "Rerank retrieved chunks with claim-relevant evidence signals before generation.",
            "A relevant source was retrieved but ranked too low to support reliable generation.",
        ),
        (
            "Measure the supporting chunk rank and set a regression threshold for this query.",
            "The repair should preserve evidence placement across future retriever changes.",
        ),
    ],
    "chunking_issue": [
        (
            "Adjust chunk boundaries, overlap, or parent-document expansion to include the supporting span.",
            "The retrieved source was relevant, but its selected chunk omitted required evidence.",
        ),
        (
            "Add the exact supporting span to chunking regression coverage.",
            "Document retrieval can pass while span-level retrieval still fails.",
        ),
    ],
    "corpus_gap": [
        (
            "Add a reviewed authoritative source that explicitly covers the missing fact.",
            "Neither retrieved contexts nor the audited corpus support the claim.",
        ),
        (
            "Require abstention until the corpus contains sufficient evidence.",
            "Generation must not fill a knowledge gap with an unsupported answer.",
        ),
    ],
    "answer_overreach": [
        (
            "Remove unsupported details or split the answer into independently verified atomic claims.",
            "Available evidence supports only part of the generated claim.",
        ),
        (
            "Gate generation on support for every required fact and abstain on uncovered details.",
            "A high-overlap source is not sufficient when material facts remain unmatched.",
        ),
    ],
    "conflicting_contexts": [
        (
            "Resolve the conflicting fact before generation and expose the conflict when it cannot be resolved.",
            "The selected evidence contradicts a material answer claim.",
        ),
        (
            "Apply source authority and freshness rules, then abstain when equally credible sources disagree.",
            "A deterministic source-selection policy prevents silent contradiction.",
        ),
    ],
    "stale_source": [
        (
            "Replace stale evidence or rank a newer authoritative source ahead of it.",
            "Corpus audit found stale or conflicting evidence.",
        ),
        (
            "Add freshness metadata and a maximum-age policy for time-sensitive claims.",
            "Freshness needs an explicit retrieval and verification constraint.",
        ),
    ],
    "wrong_source_cited": [
        (
            "Regenerate claim-level citations from the evidence span that actually supports the claim.",
            "The answer may be supportable, but its cited source is not the supporting source.",
        ),
        (
            "Reject citations whose source does not cover every required fact in the associated claim.",
            "Citation presence alone is not evidence alignment.",
        ),
    ],
    "missing_cited_source": [
        (
            "Preserve source IDs from retrieval through generation and reject references to unknown IDs.",
            "The citation cannot be resolved to a retrieved context.",
        ),
    ],
    "should_have_abstained": [
        (
            "Add an insufficient-evidence abstention gate before final-answer generation.",
            "The trace does not contain enough support for a responsible answer.",
        ),
    ],
    "insufficient_context": [
        (
            "Retrieve more specific evidence or qualify the answer and abstain on unsupported details.",
            "The closest evidence remains too weak or ambiguous to verify the claim.",
        ),
    ],
    "tool_result_contradicted_by_final_answer": [
        (
            "Gate final-answer generation on tool-result status and propagate failed or empty results.",
            "The final answer claims success despite a negative tool observation.",
        ),
        (
            "Add a replay test that fails whenever the final answer contradicts the tool result.",
            "Agent repairs need intermediate-state regression coverage.",
        ),
    ],
    "tool_result_not_reflected_in_final_answer": [
        (
            "Require the final answer to acknowledge failed, empty, or unavailable tool results.",
            "A negative tool observation was omitted from the user-visible answer.",
        ),
    ],
    "agent_error": [
        (
            "Propagate the agent error, retry under an explicit policy, or fail closed.",
            "The trace contains an unhandled agent or tool error.",
        ),
    ],
    "missing_final_answer": [
        (
            "Emit and persist a final-answer event after the agent completes or fails.",
            "The trace cannot connect intermediate work to a user-visible outcome.",
        ),
    ],
}


class RepairInputError(ValueError):
    """Raised when a repair plan cannot be built from the supplied trace."""


def build_repair_plan(
    trace_path: str | Path,
    *,
    corpus_path: str | Path | None = None,
    mode: str = "semantic",
    suite_path: str | Path = "contexttrace-suite.json",
) -> dict[str, Any]:
    """Build an evidence-backed repair plan for a RAG or agent trace."""

    source_path = Path(trace_path)
    try:
        diagnosis = diagnose_trace_file(source_path, mode=mode)
    except DiagnoseInputError as exc:
        raise RepairInputError(str(exc)) from exc

    qa = None
    if corpus_path is not None:
        try:
            trace = load_trace_file(source_path)
            qa = qa_trace(
                trace,
                trace_path=str(source_path),
                corpus_path=corpus_path,
                mode=mode,
            )
        except VerificationInputError as exc:
            raise RepairInputError(
                "Corpus repair audit requires a portable RAG trace: %s" % exc
            ) from exc

    root_causes = _root_causes(diagnosis, qa)
    primary_root_cause = root_causes[0] if root_causes else "no_failure_detected"
    repair_required = bool(
        (diagnosis.get("summary") or {}).get("status") != "passed"
        or ((qa or {}).get("summary") or {}).get("has_audit_failures")
    )
    actions = _repair_actions(root_causes, diagnosis, qa) if repair_required else []
    evidence = _repair_evidence(diagnosis, qa)
    commands = _verification_commands(
        source_path,
        corpus_path=Path(corpus_path) if corpus_path is not None else None,
        mode=mode,
        suite_path=Path(suite_path),
        trace_type=str(diagnosis.get("trace_type") or "trace"),
    )
    trace_type = str(diagnosis.get("trace_type") or "trace")
    verification_policy = (
        "Apply and recapture the fix before adding the trace to a must-pass suite."
        if trace_type in {"rag", "agent_rag"}
        else (
            "Preserve this failing trace and generate its diagnostic replay test before applying the app fix; "
            "then recapture a passing trace and rerun diagnosis."
        )
    )
    return {
        "schema_version": REPAIR_SCHEMA_VERSION,
        "status": "repair_required" if repair_required else "no_repair_needed",
        "trace_path": str(source_path),
        "trace_type": trace_type,
        "mode": mode,
        "corpus_audited": qa is not None,
        "corpus_path": str(corpus_path) if corpus_path is not None else None,
        "primary_root_cause": primary_root_cause,
        "root_causes": root_causes,
        "summary": {
            "repair_action_count": len(actions),
            "evidence_item_count": len(evidence),
            "diagnosis_status": (diagnosis.get("summary") or {}).get("status"),
            "high_risk_findings": (diagnosis.get("summary") or {}).get("high_risk_findings", 0),
            "audit_primary_label": ((qa or {}).get("summary") or {}).get("audit_primary_label"),
        },
        "evidence": evidence,
        "actions": actions,
        "verification": {
            "policy": verification_policy,
            "commands": commands,
        },
    }


def write_repair_plan(
    plan: dict[str, Any],
    *,
    markdown_path: str | Path,
    json_path: str | Path | None = None,
) -> dict[str, str]:
    markdown_output = Path(markdown_path)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_repair_plan(plan), encoding="utf-8")
    outputs = {"markdown": str(markdown_output)}
    if json_path is not None:
        json_output = Path(json_path)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        outputs["json"] = str(json_output)
    return outputs


def render_repair_plan(plan: dict[str, Any]) -> str:
    lines = [
        "# ContextTrace Repair Plan",
        "",
        "- Status: `%s`" % plan.get("status"),
        "- Trace type: `%s`" % plan.get("trace_type"),
        "- Primary root cause: `%s`" % plan.get("primary_root_cause"),
        "- Corpus audited: `%s`" % bool(plan.get("corpus_audited")),
        "",
        "## Evidence",
        "",
    ]
    evidence = plan.get("evidence") or []
    if not evidence:
        lines.append("No failure evidence was found.")
    for item in evidence:
        lines.append("### %s" % (item.get("root_cause") or "diagnostic finding"))
        lines.append("")
        if item.get("claim"):
            lines.append("Claim: %s" % item["claim"])
        if item.get("reason"):
            lines.append("Reason: %s" % item["reason"])
        if item.get("retrieved_evidence"):
            lines.append("Retrieved evidence: %s" % item["retrieved_evidence"])
        if item.get("corpus_evidence"):
            lines.append("Corpus evidence: %s" % item["corpus_evidence"])
        if item.get("corpus_document_id"):
            lines.append("Corpus document: `%s`" % item["corpus_document_id"])
        lines.append("")

    lines.extend(["## Recommended Changes", ""])
    actions = plan.get("actions") or []
    if not actions:
        lines.append("No repair is required by the current local diagnosis.")
    for action in actions:
        lines.append("%s. **%s**" % (action.get("priority"), action.get("action")))
        lines.append("")
        lines.append("   Root cause: `%s`. %s" % (action.get("root_cause"), action.get("rationale")))
        lines.append("")

    lines.extend(["## Verification And Regression", ""])
    lines.append(str((plan.get("verification") or {}).get("policy") or ""))
    lines.append("")
    for item in (plan.get("verification") or {}).get("commands") or []:
        lines.append("- %s:" % item.get("stage"))
        lines.append("")
        lines.append("  ```bash")
        lines.append("  %s" % item.get("command"))
        lines.append("  ```")
    lines.append("")
    return "\n".join(lines)


def _root_causes(diagnosis: dict[str, Any], qa: dict[str, Any] | None) -> list[str]:
    values: list[str] = []
    audit = (qa or {}).get("audit") or {}
    audit_summary = audit.get("summary") or {}
    _append_root(values, audit_summary.get("primary_audit_label"))
    for claim in audit.get("claims") or []:
        _append_root(values, claim.get("audit_label"))
    for finding in diagnosis.get("findings") or []:
        _append_root(values, finding.get("type"))
    if not values and (diagnosis.get("summary") or {}).get("status") != "passed":
        _append_root(values, (diagnosis.get("summary") or {}).get("primary_issue"))
    return values


def _append_root(values: list[str], value: Any) -> None:
    label = str(value or "").strip()
    if label and label != "no_failure_detected" and label not in values:
        values.append(label)


def _repair_actions(
    root_causes: list[str],
    diagnosis: dict[str, Any],
    qa: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    candidates: list[tuple[str, str, str, str]] = []
    audit_summary = (((qa or {}).get("audit") or {}).get("summary") or {})
    audit_root = str(audit_summary.get("primary_audit_label") or "")
    for item in audit_summary.get("top_recommended_actions") or []:
        action = str(item.get("action") or "").strip()
        if action:
            candidates.append(
                (
                    audit_root or "corpus_audit",
                    action,
                    "Corpus audit recommended this change for %s claim(s)." % item.get("claims", 1),
                    "corpus_audit",
                )
            )
    for root_cause in root_causes:
        for action, rationale in _ACTION_TEMPLATES.get(root_cause, []):
            candidates.append((root_cause, action, rationale, "root_cause_template"))
    for finding in diagnosis.get("findings") or []:
        action = str(finding.get("suggested_fix") or "").strip()
        root_cause = str(finding.get("type") or "diagnostic_finding")
        if action:
            candidates.append(
                (
                    root_cause,
                    action,
                    str(finding.get("reason") or "Diagnosis recommended this repair."),
                    "diagnosis",
                )
            )

    actions = []
    seen: set[str] = set()
    for root_cause, action, rationale, source in candidates:
        key = " ".join(action.lower().split()).rstrip(".")
        if not key or key in seen:
            continue
        seen.add(key)
        actions.append(
            {
                "priority": len(actions) + 1,
                "root_cause": root_cause,
                "action": action,
                "rationale": rationale,
                "source": source,
            }
        )
        if len(actions) >= 8:
            break
    return actions


def _repair_evidence(diagnosis: dict[str, Any], qa: dict[str, Any] | None) -> list[dict[str, Any]]:
    evidence = []
    audit = (qa or {}).get("audit") or {}
    for claim in audit.get("claims") or []:
        root_cause = str(claim.get("audit_label") or "")
        if root_cause == "no_failure_detected":
            continue
        retrieved = claim.get("retrieved") or {}
        corpus = claim.get("corpus") or {}
        evidence.append(
            {
                "source": "corpus_audit",
                "root_cause": root_cause,
                "claim": claim.get("claim"),
                "reason": claim.get("reason"),
                "failure_stage": claim.get("failure_stage"),
                "retrieved_context_id": retrieved.get("best_context_id"),
                "retrieved_evidence": retrieved.get("evidence"),
                "corpus_document_id": corpus.get("best_document_id"),
                "corpus_evidence": corpus.get("evidence"),
            }
        )
    audited_claims = {str(item.get("claim") or "") for item in evidence}
    for finding in diagnosis.get("findings") or []:
        claim = str(finding.get("claim") or "")
        if finding.get("source") == "rag" and claim in audited_claims:
            continue
        evidence.append(
            {
                "source": finding.get("source"),
                "root_cause": finding.get("type"),
                "claim": finding.get("claim"),
                "reason": finding.get("reason"),
                "retrieved_evidence": finding.get("evidence"),
                "tool": finding.get("tool"),
                "step_index": finding.get("step_index"),
            }
        )
    return evidence[:12]


def _verification_commands(
    trace_path: Path,
    *,
    corpus_path: Path | None,
    mode: str,
    suite_path: Path,
    trace_type: str,
) -> list[dict[str, str]]:
    trace_arg = _quote(trace_path)
    diagnosis_command = {
        "stage": "Re-run diagnosis after the fix",
        "command": "contexttrace diagnose %s --mode %s --fail-on any_issue" % (trace_arg, mode),
    }
    commands = [diagnosis_command]
    if corpus_path is not None:
        commands.append(
            {
                "stage": "Confirm retrieval and corpus repair",
                "command": "contexttrace audit %s --corpus %s --mode %s --fail-on any_failure"
                % (trace_arg, _quote(corpus_path), mode),
            }
        )
    if trace_type in {"rag", "agent_rag"}:
        corpus_option = " --corpus %s" % _quote(corpus_path) if corpus_path is not None else ""
        if suite_path.is_file():
            regression_command = {
                "stage": "Add the recaptured passing trace to the regression suite",
                "command": "contexttrace suite add %s %s --mode %s%s"
                % (_quote(suite_path), trace_arg, mode, corpus_option),
            }
        else:
            regression_command = {
                "stage": "Create a must-pass suite from the recaptured passing trace",
                "command": "contexttrace suite create %s --out %s --mode %s%s"
                % (trace_arg, _quote(suite_path), mode, corpus_option),
            }
        commands.append(regression_command)
    else:
        test_path = Path("tests") / "contexttrace" / ("test_%s_diagnosis.py" % _safe_name(trace_path.stem))
        commands = [
            {
                "stage": "Lock the captured agent failure into a diagnostic replay test",
                "command": "contexttrace diagnose %s --mode %s --generate-test --test-out %s"
                % (trace_arg, mode, _quote(test_path)),
            },
            diagnosis_command,
        ]
    return commands


def _quote(path: Path) -> str:
    value = path.as_posix().replace('"', '\\"')
    return '"%s"' % value


def _safe_name(value: str) -> str:
    cleaned = "_".join(
        part for part in "".join(char.lower() if char.isalnum() else "_" for char in value).split("_") if part
    )
    if not cleaned:
        return "trace"
    if cleaned[0].isdigit():
        cleaned = "trace_%s" % cleaned
    return cleaned[:80]
