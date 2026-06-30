from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


MODULE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = MODULE_DIR / "schemas" / "review_response.schema.json"
PROMPT_DIR = MODULE_DIR / "prompts"

AGENTS = {
    "strict_evidence": {
        "file": "agent_a_strict_evidence.jsonl",
        "prompt": "strict_evidence.txt",
    },
    "developer_actionability": {
        "file": "agent_b_developer_actionability.jsonl",
        "prompt": "developer_actionability.txt",
    },
    "skeptical_arr": {
        "file": "agent_c_skeptical_arr.jsonl",
        "prompt": "skeptical_arr.txt",
    },
}
FAILURE_LABELS = {
    "supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "unverifiable",
    "unsure",
}
ROOT_CAUSES = {
    "retrieval_miss",
    "reranking_failure",
    "chunking_issue",
    "corpus_gap",
    "answer_overreach",
    "citation_mismatch",
    "conflicting_contexts",
    "stale_source",
    "should_have_abstained",
    "tool_result_ignored",
    "memory_contamination",
    "no_failure_detected",
    "unsure",
    "other",
}
CITATION_STATUSES = {"correct", "incorrect", "missing", "not_applicable", "unsure"}
RISK_LEVELS = {"low", "medium", "high"}
REQUIRED_RESPONSE_FIELDS = {
    "case_id",
    "agent_id",
    "failure_label",
    "root_cause",
    "evidence_span",
    "citation_status",
    "dangerous_false_green_risk",
    "fix_recommendation",
    "actionability_score",
    "confidence",
    "rationale",
    "overclaim_warning",
}
ANNOTATION_FORBIDDEN_KEYS = {
    "annotation",
    "benchmark_note",
    "expected",
    "expected_citation_statuses",
    "expected_evidence_spans",
    "expected_labels",
    "expected_primary_root_cause",
    "expected_should_abstain",
    "original_id",
    "predicted",
    "predictions",
}


def load_response_schema(path: str | Path = SCHEMA_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Review response schema must be a JSON object.")
    return payload


def validate_review_response(
    value: Any, *, expected_case_id: str | None = None, expected_agent_id: str | None = None
) -> list[str]:
    if not isinstance(value, dict):
        return ["response must be a JSON object"]
    errors: list[str] = []
    missing = sorted(REQUIRED_RESPONSE_FIELDS - set(value))
    extra = sorted(set(value) - REQUIRED_RESPONSE_FIELDS)
    if missing:
        errors.append("missing fields: %s" % ", ".join(missing))
    if extra:
        errors.append("unexpected fields: %s" % ", ".join(extra))
    if expected_case_id is not None and value.get("case_id") != expected_case_id:
        errors.append("case_id must be %s" % expected_case_id)
    if expected_agent_id is not None and value.get("agent_id") != expected_agent_id:
        errors.append("agent_id must be %s" % expected_agent_id)
    if value.get("agent_id") not in AGENTS:
        errors.append("invalid agent_id")
    if value.get("failure_label") not in FAILURE_LABELS:
        errors.append("invalid failure_label")
    if value.get("root_cause") not in ROOT_CAUSES:
        errors.append("invalid root_cause")
    if value.get("citation_status") not in CITATION_STATUSES:
        errors.append("invalid citation_status")
    if value.get("dangerous_false_green_risk") not in RISK_LEVELS:
        errors.append("invalid dangerous_false_green_risk")
    evidence_span = value.get("evidence_span")
    if evidence_span is not None and not isinstance(evidence_span, str):
        errors.append("evidence_span must be a string or null")
    overclaim = value.get("overclaim_warning")
    if overclaim is not None and not isinstance(overclaim, str):
        errors.append("overclaim_warning must be a string or null")
    for field in ("fix_recommendation", "rationale"):
        if not isinstance(value.get(field), str):
            errors.append("%s must be a string" % field)
    score = value.get("actionability_score")
    if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 5:
        errors.append("actionability_score must be an integer from 1 to 5")
    confidence = value.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        errors.append("confidence must be a number from 0 to 1")
    return errors


def annotation_prompt(case: dict[str, Any], agent_id: str) -> tuple[str, str, dict[str, Any]]:
    public_case = {
        "case_id": str(case.get("blind_id") or ""),
        "query": case.get("query"),
        "answer": case.get("answer"),
        "contexts": case.get("contexts") or [],
        "citations": case.get("citations") or [],
        "source_reference": case.get("source_reference"),
    }
    assert_no_forbidden_keys(public_case, ANNOTATION_FORBIDDEN_KEYS)
    system = _agent_prompt(agent_id)
    user_payload = {
        "task": "Review this blinded RAG trace. Evaluate the answer only against supplied contexts and citations.",
        "required_case_id": public_case["case_id"],
        "required_agent_id": agent_id,
        "trace": public_case,
    }
    user = json.dumps(user_payload, ensure_ascii=True, sort_keys=True)
    return system, user, user_payload


def rq4_prompt(
    case: dict[str, Any], *, agent_id: str, setting: str, evaluation_output: dict[str, Any] | None
) -> tuple[str, str, dict[str, Any]]:
    if setting not in {"raw_trace", "score_only", "contexttrace"}:
        raise ValueError("Unknown RQ4 setting: %s" % setting)
    trace = {
        "case_id": str(case.get("blind_id") or ""),
        "query": case.get("query"),
        "answer": case.get("answer"),
        "contexts": case.get("contexts") or [],
        "citations": case.get("citations") or [],
    }
    material: dict[str, Any] = {"trace": trace}
    if setting != "raw_trace":
        if not isinstance(evaluation_output, dict):
            raise ValueError("RQ4 %s requires an evaluator output." % setting)
        material["evaluation_output"] = evaluation_output
    if setting == "score_only":
        forbidden = {"root_cause", "primary_root_cause", "evidence_span", "suggested_fix", "failure_types"}
        leaked = sorted(nested_keys(evaluation_output or {}).intersection(forbidden))
        if leaked:
            raise ValueError("Score-only prompt leaks diagnostic fields: %s" % leaked)
    if setting == "raw_trace" and evaluation_output is not None:
        raise ValueError("Raw-trace prompt cannot include evaluator output.")
    assert_no_forbidden_keys(material, ANNOTATION_FORBIDDEN_KEYS | {"condition_by_option"})
    system = _agent_prompt(agent_id)
    user_payload = {
        "task": (
            "Assess whether the supplied material supports a correct, specific repair decision. "
            "When evaluator output is absent, reason from the raw trace only."
        ),
        "setting": setting,
        "required_case_id": trace["case_id"],
        "required_agent_id": agent_id,
        "material": material,
    }
    user = json.dumps(user_payload, ensure_ascii=True, sort_keys=True)
    if setting in {"raw_trace", "score_only"} and "ContextTrace" in user:
        raise ValueError("Non-treatment RQ4 prompt leaks the treatment name.")
    return system, user, user_payload


def assert_no_forbidden_keys(value: Any, forbidden: set[str]) -> None:
    leaked = sorted(nested_keys(value).intersection(forbidden))
    if leaked:
        raise ValueError("Prompt leaks forbidden fields: %s" % leaked)


def nested_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key))
            keys.update(nested_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            keys.update(nested_keys(nested))
    return keys


def request_sha256(*, model: str, system: str, user: str) -> str:
    payload = json.dumps(
        {"model": model, "system": system, "user": user},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        return []
    rows = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("%s:%s must be a JSON object" % (source, line_number))
        rows.append(value)
    return rows


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n" for row in rows)
    destination.write_text(payload, encoding="utf-8")


def _agent_prompt(agent_id: str) -> str:
    config = AGENTS.get(agent_id)
    if config is None:
        raise ValueError("Unknown simulated reviewer: %s" % agent_id)
    return (PROMPT_DIR / str(config["prompt"])).read_text(encoding="utf-8").strip()
