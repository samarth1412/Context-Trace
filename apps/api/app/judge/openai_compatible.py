from __future__ import annotations

import json
from typing import Any, Dict

import httpx


class OpenAICompatibleJudgeProvider:
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def complete_json(
        self,
        *,
        task: str,
        system_prompt: str,
        user_payload: Dict[str, Any],
    ) -> Any:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "%s/chat/completions" % self.base_url,
                headers={"Authorization": "Bearer %s" % self.api_key},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": json.dumps(user_payload, ensure_ascii=True),
                        },
                    ],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            body = response.json()
        return body["choices"][0]["message"]["content"]
