from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional


class MockJudgeProvider:
    def __init__(
        self,
        *,
        citation_responses: Optional[Iterable[Any]] = None,
        failure_responses: Optional[Iterable[Any]] = None,
    ) -> None:
        self.citation_responses: List[Any] = list(citation_responses or [])
        self.failure_responses: List[Any] = list(failure_responses or [])
        self.calls: List[Dict[str, Any]] = []

    async def complete_json(
        self,
        *,
        task: str,
        system_prompt: str,
        user_payload: Dict[str, Any],
    ) -> Any:
        self.calls.append(
            {
                "task": task,
                "system_prompt": system_prompt,
                "user_payload": user_payload,
            }
        )

        if task == "citation_verification":
            return self._next(
                self.citation_responses,
                {
                    "verdict": "directly_supported",
                    "support_score": 1.0,
                    "reason": "Mock citation response.",
                },
            )
        if task == "failure_analysis":
            return self._next(
                self.failure_responses,
                {
                    "failure_type": "no_failure_detected",
                    "severity": "none",
                    "root_cause": "Mock failure response.",
                    "suggested_fix": "No fix required.",
                },
            )
        raise ValueError("Unknown judge task: %s" % task)

    def _next(self, responses: List[Any], default: Dict[str, Any]) -> Any:
        response = responses.pop(0) if responses else default
        if isinstance(response, dict):
            return json.dumps(response)
        return response
