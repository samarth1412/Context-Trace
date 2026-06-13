from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contexttrace.verify.runner import verify_trace
from contexttrace.verify.schema import RAGTrace, TraceCitation, TraceContext, VerificationInputError, load_trace


class DiagnoseInputError(ValueError):
    """Raised when a trace cannot be diagnosed."""


def diagnose_trace_file(path: str | Path, *, mode: str = "semantic") -> dict[str, Any]:
    trace_path = Path(path)
    try:
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DiagnoseInputError("Could not read trace file %s: %s" % (trace_path, exc)) from exc
    except json.JSONDecodeError as exc:
        raise DiagnoseInputError(
            "Invalid JSON in %s at line %s column %s: %s"
            % (trace_path, exc.lineno, exc.colno, exc.msg)
        ) from exc
    return diagnose_payload(payload, mode=mode, trace_path=str(trace_path))


def write_diagnosis_regression_test(
    trace_path: str | Path,
    result: dict[str, Any],
    *,
    output_path: str | Path | None = None,
    mode: str = "semantic",
    overwrite: bool = False,
) -> str:
    input_path = Path(trace_path)
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DiagnoseInputError("Could not read trace file %s: %s" % (input_path, exc)) from exc
    except json.JSONDecodeError as exc:
        raise DiagnoseInputError(
            "Invalid JSON in %s at line %s column %s: %s"
            % (input_path, exc.lineno, exc.colno, exc.msg)
        ) from exc

    if output_path is None:
        output = Path("tests") / "contexttrace" / ("test_%s_diagnosis.py" % _safe_identifier(input_path.stem))
    else:
        output = Path(output_path)
    if output.exists() and not overwrite:
        raise DiagnoseInputError("Refusing to overwrite existing generated test %s. Pass --force-test to replace it." % output)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_regression_test_source(payload, result, mode=mode, test_name=input_path.stem), encoding="utf-8")
    return str(output)


def diagnose_payload(payload: dict[str, Any], *, mode: str = "semantic", trace_path: str | None = None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise DiagnoseInputError("Trace payload must be a JSON object.")

    rag_trace = _rag_trace_from_payload(payload)
    rag_result = verify_trace(rag_trace, mode=mode) if rag_trace is not None else None
    agent_result = _diagnose_agent_payload(payload)

    trace_type = _trace_type(rag_result, agent_result)
    findings = _findings(rag_result, agent_result)
    failure_types = _failure_types(rag_result, findings)
    summary = _summary(trace_type, rag_result, agent_result, findings, failure_types)

    return {
        "trace_path": trace_path or "",
        "trace_type": trace_type,
        "summary": summary,
        "findings": findings,
        "rag": rag_result,
        "agent": agent_result,
        "next_actions": _next_actions(summary, findings),
    }


def diagnose_failures(result: dict[str, Any], fail_on: tuple[str, ...]) -> list[str]:
    if not fail_on:
        return []
    summary = result.get("summary") or {}
    findings = result.get("findings") or []
    failure_types = set(summary.get("failure_types") or [])
    messages = []
    for raw_rule in fail_on:
        rule = str(raw_rule or "").strip().lower().replace("-", "_")
        if rule in {"any", "any_issue", "failure"} and summary.get("status") != "passed":
            messages.append("diagnosis found an issue")
        elif rule == "high_risk" and any(str(item.get("severity")) == "high" for item in findings):
            messages.append("high-risk diagnosis finding detected")
        elif rule == "agent_failure" and any(str(item.get("source")) == "agent" for item in findings):
            messages.append("agent failure detected")
        elif rule == "rag_failure" and any(str(item.get("source")) == "rag" for item in findings):
            messages.append("RAG failure detected")
        elif rule in failure_types:
            messages.append("%s detected" % rule)
        elif rule not in {"any", "any_issue", "failure", "high_risk", "agent_failure", "rag_failure"}:
            messages.append("unknown --fail-on rule %s" % raw_rule)
    return messages


def _regression_test_source(
    payload: dict[str, Any],
    result: dict[str, Any],
    *,
    mode: str,
    test_name: str,
) -> str:
    summary = result.get("summary") or {}
    findings = result.get("findings") or []
    expected_failure_types = list(summary.get("failure_types") or [])
    expected_finding_types = sorted({str(item.get("type")) for item in findings if item.get("type")})
    expected_finding_sources = sorted({str(item.get("source")) for item in findings if item.get("source")})
    payload_json = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True)
    function_name = "test_%s_diagnosis_regression" % _safe_identifier(test_name)
    lines = [
        "import json",
        "",
        "from contexttrace.diagnose import diagnose_payload",
        "",
        "",
        "TRACE_PAYLOAD = json.loads(%r)" % payload_json,
        "EXPECTED_STATUS = %r" % str(summary.get("status") or ""),
        "EXPECTED_PRIMARY_ISSUE = %r" % str(summary.get("primary_issue") or ""),
        "EXPECTED_FAILURE_TYPES = %r" % expected_failure_types,
        "EXPECTED_FINDING_TYPES = %r" % expected_finding_types,
        "EXPECTED_FINDING_SOURCES = %r" % expected_finding_sources,
        "",
        "",
        "def %s():" % function_name,
        "    result = diagnose_payload(TRACE_PAYLOAD, mode=%r)" % mode,
        "    assert result[\"summary\"][\"status\"] == EXPECTED_STATUS",
        "    assert result[\"summary\"][\"primary_issue\"] == EXPECTED_PRIMARY_ISSUE",
        "    failure_types = set(result[\"summary\"].get(\"failure_types\") or [])",
        "    assert set(EXPECTED_FAILURE_TYPES).issubset(failure_types)",
        "    finding_types = {item.get(\"type\") for item in result.get(\"findings\") or [] if item.get(\"type\")}",
        "    finding_sources = {item.get(\"source\") for item in result.get(\"findings\") or [] if item.get(\"source\")}",
        "    if EXPECTED_FINDING_TYPES:",
        "        assert set(EXPECTED_FINDING_TYPES).issubset(finding_types)",
        "    else:",
        "        assert result.get(\"findings\") == []",
        "    assert set(EXPECTED_FINDING_SOURCES).issubset(finding_sources)",
        "",
    ]
    return "\n".join(lines)


def _safe_identifier(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "_" for char in str(value or "trace"))
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    if not cleaned:
        cleaned = "trace"
    if cleaned[0].isdigit():
        cleaned = "trace_%s" % cleaned
    return cleaned[:80]


def _rag_trace_from_payload(payload: dict[str, Any]) -> RAGTrace | None:
    if _looks_like_portable_rag_trace(payload):
        try:
            return load_trace(payload, source="diagnose trace")
        except VerificationInputError as exc:
            raise DiagnoseInputError(str(exc)) from exc

    trace_payload = payload.get("trace") if isinstance(payload.get("trace"), dict) else None
    if trace_payload and _looks_like_portable_rag_trace(trace_payload):
        try:
            return load_trace(trace_payload, source="diagnose trace.trace")
        except VerificationInputError as exc:
            raise DiagnoseInputError(str(exc)) from exc

    api_trace = _api_trace_to_rag_trace(payload)
    if api_trace is not None:
        return api_trace
    return None


def _looks_like_portable_rag_trace(payload: dict[str, Any]) -> bool:
    return bool(payload.get("query") and payload.get("answer") and isinstance(payload.get("contexts"), list))


def _api_trace_to_rag_trace(payload: dict[str, Any]) -> RAGTrace | None:
    query = str(payload.get("query") or payload.get("goal") or "").strip()
    answer_payload = payload.get("answer")
    answer = ""
    if isinstance(answer_payload, dict):
        answer = str(answer_payload.get("answer") or answer_payload.get("content") or "").strip()
    elif answer_payload is not None:
        answer = str(answer_payload).strip()
    if not answer:
        answer = _final_answer_from_agent_payload(payload)

    chunks = payload.get("chunks") or payload.get("selected_contexts") or []
    contexts = []
    if isinstance(chunks, list):
        for index, chunk in enumerate(chunks):
            if not isinstance(chunk, dict):
                continue
            content = chunk.get("content") or chunk.get("text")
            if not str(content or "").strip():
                continue
            context_id = str(chunk.get("chunk_id") or chunk.get("id") or "chunk_%s" % (index + 1))
            metadata = dict(chunk.get("metadata") or {})
            if chunk.get("source"):
                metadata.setdefault("source", chunk.get("source"))
            contexts.append(TraceContext(id=context_id, text=str(content), metadata=metadata))
    if not query or not answer or not contexts:
        return None

    citations = []
    for item in payload.get("citation_checks") or payload.get("citations") or []:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim") or "").strip()
        source_id = item.get("source_chunk_id") or item.get("source_id") or item.get("chunk_id")
        if claim and source_id:
            citations.append(TraceCitation(claim=claim, source_id=str(source_id), metadata=dict(item.get("metadata") or {})))
    return RAGTrace(query=query, answer=answer, contexts=contexts, citations=citations, metadata=dict(payload.get("metadata") or {}))


def _diagnose_agent_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    events = _agent_events(payload)
    if not events:
        return None
    goal = str(payload.get("goal") or payload.get("query") or "").strip()
    final_answer = _final_answer_from_events(events) or _final_answer_from_agent_payload(payload)
    findings: list[dict[str, Any]] = []

    if not final_answer:
        findings.append(
            _agent_finding(
                finding_id="agent_1",
                finding_type="missing_final_answer",
                severity="medium",
                reason="Agent trace has steps or events but no final answer.",
                suggested_fix="Log a final_answer event so CI can compare tool results with user-visible output.",
            )
        )

    negative_events = []
    for index, event in enumerate(events):
        if event.get("event_type") in {"tool_result", "tool_call"}:
            reason = _negative_tool_result_reason(event.get("output_json"))
            if reason:
                negative_events.append((index, event, reason))
        if event.get("error_message"):
            findings.append(
                _agent_finding(
                    finding_id="agent_%s" % (len(findings) + 1),
                    finding_type="agent_error",
                    severity="high",
                    step_index=index,
                    tool=str(event.get("name") or ""),
                    evidence=str(event.get("error_message") or ""),
                    reason="Agent event logged an error.",
                    suggested_fix="Propagate tool or node errors into the final answer, retry, or fail closed.",
                )
            )

    if final_answer and _final_answer_claims_success(final_answer):
        for index, event, reason in negative_events:
            findings.append(
                _agent_finding(
                    finding_id="agent_%s" % (len(findings) + 1),
                    finding_type="tool_result_contradicted_by_final_answer",
                    severity="high",
                    step_index=index,
                    tool=str(event.get("name") or ""),
                    evidence=_preview_json(event.get("output_json")),
                    reason="Final answer claims success, but the tool result indicates %s." % reason,
                    suggested_fix=(
                        "Gate final-answer generation on tool-result status. If the tool returns no availability, "
                        "not found, or failed, answer with that failure instead of claiming completion."
                    ),
                )
            )

    if final_answer and negative_events and not _final_answer_acknowledges_negative(final_answer):
        if not any(item["type"] == "tool_result_contradicted_by_final_answer" for item in findings):
            index, event, reason = negative_events[0]
            findings.append(
                _agent_finding(
                    finding_id="agent_%s" % (len(findings) + 1),
                    finding_type="tool_result_not_reflected_in_final_answer",
                    severity="medium",
                    step_index=index,
                    tool=str(event.get("name") or ""),
                    evidence=_preview_json(event.get("output_json")),
                    reason="Final answer does not reflect a negative tool result: %s." % reason,
                    suggested_fix="Require the final answer to acknowledge failed or empty tool results.",
                )
            )

    return {
        "goal": goal,
        "final_answer": final_answer,
        "event_count": len(events),
        "tool_event_count": len([event for event in events if event.get("event_type") in {"tool_call", "tool_result"}]),
        "negative_tool_results": len(negative_events),
        "findings": findings,
        "events": events,
    }


def _agent_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_events = payload.get("agent_events")
    if raw_events is None:
        raw_events = payload.get("events")
    if raw_events is None:
        raw_events = payload.get("steps")
    if not isinstance(raw_events, list):
        return []
    return [_normalize_agent_event(item, index=index) for index, item in enumerate(raw_events) if isinstance(item, dict)]


def _normalize_agent_event(item: dict[str, Any], *, index: int) -> dict[str, Any]:
    event_type = str(item.get("event_type") or item.get("type") or "").strip().lower()
    if event_type == "final":
        event_type = "final_answer"
    name = item.get("name") or item.get("tool") or item.get("node")
    output = item.get("output_json")
    if output is None:
        output = item.get("output")
    if output is None:
        output = item.get("result")
    if output is None and event_type == "final_answer":
        output = {"answer": item.get("content") or item.get("answer")}
    input_json = item.get("input_json")
    if input_json is None:
        input_json = item.get("input")
    if input_json is None:
        input_json = item.get("args")
    if event_type == "tool_call" and output is not None:
        event_type = "tool_result"
    return {
        "index": index,
        "event_type": event_type or "step",
        "name": str(name or ""),
        "input_json": input_json if input_json is not None else {},
        "output_json": output if output is not None else {},
        "metadata": item.get("metadata_json") or item.get("metadata") or {},
        "latency_ms": item.get("latency_ms"),
        "error_message": str(item.get("error_message") or item.get("error") or "").strip(),
    }


def _final_answer_from_agent_payload(payload: dict[str, Any]) -> str:
    answer = payload.get("final_answer")
    if isinstance(answer, dict):
        return str(answer.get("content") or answer.get("answer") or "").strip()
    if answer is not None:
        return str(answer).strip()
    answer_payload = payload.get("answer")
    if isinstance(answer_payload, dict):
        return str(answer_payload.get("answer") or answer_payload.get("content") or "").strip()
    if answer_payload is not None:
        return str(answer_payload).strip()
    return ""


def _final_answer_from_events(events: list[dict[str, Any]]) -> str:
    for event in reversed(events):
        if event.get("event_type") != "final_answer":
            continue
        output = event.get("output_json")
        if isinstance(output, dict):
            answer = output.get("answer") or output.get("content")
            if str(answer or "").strip():
                return str(answer).strip()
        elif output is not None and str(output).strip():
            return str(output).strip()
    return ""


def _negative_tool_result_reason(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        for key in ("success", "matched", "found", "available", "booked", "created", "sent"):
            if key in value and value.get(key) is False:
                return "%s=false" % key
        for key in ("matches", "results", "items", "availability", "slots"):
            if key in value and isinstance(value.get(key), list) and not value.get(key):
                return "%s is empty" % key
        if value.get("error") or value.get("error_message"):
            return "an error: %s" % (value.get("error") or value.get("error_message"))
    text = _json_text(value)
    lowered = text.lower()
    phrases = [
        "no availability",
        "not available",
        "unavailable",
        "no results",
        "not found",
        "nothing found",
        "failed",
        "failure",
        "error",
        "declined",
        "cannot",
        "could not",
        "unable",
    ]
    for phrase in phrases:
        if phrase in lowered:
            return phrase
    return ""


def _final_answer_claims_success(answer: str) -> bool:
    lowered = answer.lower()
    negative_markers = ["not booked", "not scheduled", "could not", "couldn't", "unable", "no availability", "not available"]
    if any(marker in lowered for marker in negative_markers):
        return False
    success_terms = [
        "booked",
        "scheduled",
        "reserved",
        "confirmed",
        "created",
        "sent",
        "updated",
        "deleted",
        "completed",
        "resolved",
        "found",
        "submitted",
    ]
    return any(term in lowered for term in success_terms)


def _final_answer_acknowledges_negative(answer: str) -> bool:
    lowered = answer.lower()
    return any(
        phrase in lowered
        for phrase in [
            "no availability",
            "not available",
            "unavailable",
            "not found",
            "no results",
            "could not",
            "couldn't",
            "unable",
            "failed",
            "error",
        ]
    )


def _agent_finding(
    *,
    finding_id: str,
    finding_type: str,
    severity: str,
    reason: str,
    suggested_fix: str,
    step_index: int | None = None,
    tool: str = "",
    evidence: str = "",
) -> dict[str, Any]:
    return {
        "id": finding_id,
        "source": "agent",
        "type": finding_type,
        "severity": severity,
        "step_index": step_index,
        "tool": tool,
        "evidence": evidence,
        "reason": reason,
        "suggested_fix": suggested_fix,
    }


def _findings(rag_result: dict[str, Any] | None, agent_result: dict[str, Any] | None) -> list[dict[str, Any]]:
    findings = []
    if rag_result is not None:
        for index, claim in enumerate(rag_result.get("claims") or [], start=1):
            root = claim.get("root_cause") if isinstance(claim.get("root_cause"), dict) else {}
            root_label = str(root.get("label") or "no_failure_detected")
            if root_label == "no_failure_detected":
                continue
            findings.append(
                {
                    "id": "rag_%s" % index,
                    "source": "rag",
                    "type": root_label,
                    "severity": _rag_severity(claim),
                    "claim_id": claim.get("claim_id"),
                    "claim": claim.get("claim"),
                    "evidence": claim.get("evidence"),
                    "reason": root.get("reason") or claim.get("reason") or "",
                    "suggested_fix": root.get("suggested_fix") or (rag_result.get("summary") or {}).get("suggested_fix") or "",
                }
            )
    if agent_result is not None:
        findings.extend(agent_result.get("findings") or [])
    return findings


def _rag_severity(claim: dict[str, Any]) -> str:
    verdict = str(claim.get("verdict") or "")
    if verdict in {"unsupported", "contradicted"}:
        return "high"
    if verdict in {"partially_supported", "unverifiable"}:
        return "medium"
    return "low"


def _failure_types(rag_result: dict[str, Any] | None, findings: list[dict[str, Any]]) -> list[str]:
    values = []
    if rag_result is not None:
        values.extend((rag_result.get("summary") or {}).get("failure_types") or [])
    values.extend(str(item.get("type")) for item in findings if item.get("type"))
    deduped = []
    for value in values:
        if value and value != "no_failure_detected" and value not in deduped:
            deduped.append(value)
    return deduped or ["no_failure_detected"]


def _summary(
    trace_type: str,
    rag_result: dict[str, Any] | None,
    agent_result: dict[str, Any] | None,
    findings: list[dict[str, Any]],
    failure_types: list[str],
) -> dict[str, Any]:
    high = len([item for item in findings if item.get("severity") == "high"])
    medium = len([item for item in findings if item.get("severity") == "medium"])
    status = "passed" if failure_types == ["no_failure_detected"] and not findings else "failed"
    primary = _primary_issue(findings, rag_result)
    suggested_fix = _primary_fix(findings, rag_result)
    rag_summary = (rag_result or {}).get("summary") or {}
    return {
        "status": status,
        "trace_type": trace_type,
        "primary_issue": primary,
        "failure_types": failure_types,
        "total_findings": len(findings),
        "high_risk_findings": high,
        "medium_risk_findings": medium,
        "rag_failure_type": rag_summary.get("failure_type") or "not_run",
        "rag_support_rate": rag_summary.get("support_rate"),
        "rag_unsupported_claim_rate": rag_summary.get("unsupported_claim_rate"),
        "agent_findings": len((agent_result or {}).get("findings") or []),
        "agent_negative_tool_results": (agent_result or {}).get("negative_tool_results", 0),
        "suggested_fix": suggested_fix,
    }


def _trace_type(rag_result: dict[str, Any] | None, agent_result: dict[str, Any] | None) -> str:
    if rag_result is not None and agent_result is not None:
        return "agent_rag"
    if agent_result is not None:
        return "agent"
    if rag_result is not None:
        return "rag"
    raise DiagnoseInputError("Trace must be a portable RAG trace or an agent trace with steps/agent_events.")


def _primary_issue(findings: list[dict[str, Any]], rag_result: dict[str, Any] | None) -> str:
    for severity in ("high", "medium", "low"):
        for finding in findings:
            if finding.get("severity") == severity:
                return str(finding.get("type") or "diagnosis_issue")
    if rag_result is not None:
        return str((rag_result.get("summary") or {}).get("failure_type") or "no_failure_detected")
    return "no_failure_detected"


def _primary_fix(findings: list[dict[str, Any]], rag_result: dict[str, Any] | None) -> str:
    for severity in ("high", "medium", "low"):
        for finding in findings:
            if finding.get("severity") == severity and finding.get("suggested_fix"):
                return str(finding["suggested_fix"])
    if rag_result is not None:
        return str((rag_result.get("summary") or {}).get("suggested_fix") or "")
    return "No fix is needed for this trace based on local diagnosis."


def _next_actions(summary: dict[str, Any], findings: list[dict[str, Any]]) -> list[str]:
    if summary.get("status") == "passed":
        return ["Add this trace to a regression suite if it covers an important workflow."]
    actions = []
    if any(item.get("source") == "agent" for item in findings):
        actions.append("Add a regression test that replays the agent trace and fails when final_answer contradicts tool_result.")
    if any(item.get("source") == "rag" for item in findings):
        actions.append("Run contexttrace verify on the same trace with --report to inspect claim-level evidence spans.")
    actions.append("Fix the primary issue, then rerun contexttrace diagnose with --fail-on any_issue in CI.")
    return actions


def _json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True)
    except TypeError:
        return str(value)


def _preview_json(value: Any, *, limit: int = 500) -> str:
    text = _json_text(value)
    return text if len(text) <= limit else text[: limit - 1] + "..."
