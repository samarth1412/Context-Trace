from __future__ import annotations

import json
from typing import Any, Dict, Type

from pydantic import BaseModel, ValidationError

from app.judge import LLMJudgeProvider


def parse_json_object(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str):
        raise ValueError("Judge response must be a JSON object or JSON string.")

    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        loaded = json.loads(text[start : end + 1])

    if not isinstance(loaded, dict):
        raise ValueError("Judge response must be a JSON object.")
    return loaded


async def request_validated_json(
    *,
    provider: LLMJudgeProvider,
    task: str,
    system_prompt: str,
    user_payload: Dict[str, Any],
    response_model: Type[BaseModel],
) -> BaseModel:
    last_error: Exception | None = None

    for attempt in range(2):
        payload = dict(user_payload)
        payload["attempt"] = attempt + 1
        if last_error is not None:
            payload["previous_validation_error"] = str(last_error)
            payload["retry_instruction"] = "Return only valid JSON matching the requested schema."

        raw = await provider.complete_json(
            task=task,
            system_prompt=system_prompt,
            user_payload=payload,
        )
        try:
            return response_model.model_validate(parse_json_object(raw))
        except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
            last_error = exc

    raise ValueError("Judge returned invalid JSON after retry: %s" % last_error)
