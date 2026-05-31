from __future__ import annotations

from typing import Any, Dict, Protocol


class LLMJudgeProvider(Protocol):
    async def complete_json(
        self,
        *,
        task: str,
        system_prompt: str,
        user_payload: Dict[str, Any],
    ) -> Any:
        """Return a structured JSON object or a JSON string for the requested judge task."""
