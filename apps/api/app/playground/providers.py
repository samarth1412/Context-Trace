from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

import httpx


class EmbeddingProvider(Protocol):
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        ...


class AnswerProvider(Protocol):
    async def generate_answer(
        self,
        *,
        query: str,
        chunks: List[Dict[str, Any]],
    ) -> "GeneratedAnswer":
        ...


@dataclass
class GeneratedAnswer:
    answer: str
    citations: List[Dict[str, str]]
    model: Optional[str] = None
    usage: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class HashEmbeddingProvider:
    def __init__(self, *, dimensions: int = 128) -> None:
        self.dimensions = dimensions

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> List[float]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class OpenAICompatibleEmbeddingProvider:
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "%s/embeddings" % self.base_url,
                headers={"Authorization": "Bearer %s" % self.api_key},
                json={"model": self.model, "input": texts},
            )
            response.raise_for_status()
            data = response.json()
        return [item["embedding"] for item in data["data"]]


class MockAnswerProvider:
    async def generate_answer(
        self,
        *,
        query: str,
        chunks: List[Dict[str, Any]],
    ) -> GeneratedAnswer:
        if not chunks:
            return GeneratedAnswer(
                answer="I do not have enough indexed context to answer this question.",
                citations=[],
                model="mock-answer-provider",
            )

        source_lines = []
        citations = []
        for chunk in chunks[:3]:
            source_lines.append(chunk["content"])
            citations.append(
                {
                    "claim": chunk["content"][:240],
                    "source_chunk_id": chunk["chunk_id"],
                }
            )
        prompt_tokens = sum(len(chunk["content"].split()) for chunk in chunks) + len(query.split())
        completion_tokens = sum(len(line.split()) for line in source_lines)

        return GeneratedAnswer(
            answer=" ".join(source_lines),
            citations=citations,
            model="mock-answer-provider",
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            metadata={"provider": "mock", "query": query},
        )


class OpenAICompatibleAnswerProvider:
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def generate_answer(
        self,
        *,
        query: str,
        chunks: List[Dict[str, Any]],
    ) -> GeneratedAnswer:
        prompt = {
            "query": query,
            "chunks": chunks,
            "instructions": (
                "Answer using only the chunks. Return JSON with keys answer and citations. "
                "Each citation must include claim and source_chunk_id."
            ),
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "%s/chat/completions" % self.base_url,
                headers={"Authorization": "Bearer %s" % self.api_key},
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a RAG answer generator. Return only valid JSON.",
                        },
                        {"role": "user", "content": json.dumps(prompt, ensure_ascii=True)},
                    ],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        payload = json.loads(content)
        return GeneratedAnswer(
            answer=str(payload.get("answer") or ""),
            citations=list(payload.get("citations") or []),
            model=self.model,
            usage=data.get("usage") or {},
            metadata={"provider": "openai_compatible"},
        )
