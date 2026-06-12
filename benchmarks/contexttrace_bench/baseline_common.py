from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_candidate_inputs(path: str | Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    input_path = Path(path)
    rows = [
        item
        for item in (
            json.loads(line)
            for line in input_path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        )
        if isinstance(item, dict)
    ]
    return rows[:limit] if limit is not None else rows


def load_raw_rows(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    if not input_path.exists():
        return []
    payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    return [item for item in rows if isinstance(item, dict)] if isinstance(rows, list) else []


def trace_payload(row: dict[str, Any]) -> dict[str, Any]:
    trace = row.get("trace")
    return trace if isinstance(trace, dict) else {}


def user_input(row: dict[str, Any]) -> str:
    return str(trace_payload(row).get("query") or "")


def response(row: dict[str, Any]) -> str:
    return str(trace_payload(row).get("answer") or "")


def retrieved_contexts(row: dict[str, Any]) -> list[str]:
    contexts = trace_payload(row).get("contexts") or []
    return [
        str(context.get("text") or "")
        for context in contexts
        if isinstance(context, dict) and str(context.get("text") or "").strip()
    ]


def write_json(payload: Any, path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(output_path)


def score_value(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if hasattr(value, "value"):
        return score_value(getattr(value, "value"))
    if hasattr(value, "score"):
        return score_value(getattr(value, "score"))
    if isinstance(value, dict):
        for key in ("value", "score", "faithfulness", "context_recall"):
            if key in value:
                return score_value(value[key])
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def metric_reason(metric: Any, result: Any = None) -> str:
    for value in (result, metric):
        if value is None:
            continue
        if isinstance(value, dict):
            reason = value.get("reason")
            if reason:
                return str(reason)
        reason = getattr(value, "reason", None)
        if reason:
            return str(reason)
    return ""
