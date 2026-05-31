from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple


@dataclass
class VectorRecord:
    chunk_id: str
    content: str
    source: Optional[str]
    metadata: Dict[str, Any]
    score: float = 0.0


class VectorStore(Protocol):
    async def upsert(self, *, vectors: List[List[float]], payloads: List[Dict[str, Any]]) -> None:
        ...

    async def search(
        self,
        *,
        vector: List[float],
        limit: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorRecord]:
        ...


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.records: List[Tuple[List[float], Dict[str, Any]]] = []

    async def upsert(self, *, vectors: List[List[float]], payloads: List[Dict[str, Any]]) -> None:
        for vector, payload in zip(vectors, payloads):
            self.records.append((vector, payload))

    async def search(
        self,
        *,
        vector: List[float],
        limit: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorRecord]:
        scored = []
        for stored_vector, payload in self.records:
            if filters and any(payload.get(key) != value for key, value in filters.items()):
                continue
            scored.append((_cosine(vector, stored_vector), payload))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            VectorRecord(
                chunk_id=payload["chunk_id"],
                content=payload["content"],
                source=payload.get("source"),
                metadata=payload.get("metadata") or {},
                score=score,
            )
            for score, payload in scored[:limit]
        ]


class QdrantVectorStore:
    def __init__(
        self,
        *,
        url: str,
        collection: str,
        dimensions: int,
        api_key: Optional[str] = None,
    ) -> None:
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError("qdrant-client is required for Qdrant vector storage.") from exc

        self.collection = collection
        self.client = QdrantClient(url=url, api_key=api_key)
        existing = [item.name for item in self.client.get_collections().collections]
        if collection not in existing:
            self.client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=dimensions, distance=Distance.COSINE),
            )

    async def upsert(self, *, vectors: List[List[float]], payloads: List[Dict[str, Any]]) -> None:
        from qdrant_client.models import PointStruct

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=payload,
            )
            for vector, payload in zip(vectors, payloads)
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    async def search(
        self,
        *,
        vector: List[float],
        limit: int,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[VectorRecord]:
        query_filter = None
        if filters:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            query_filter = Filter(
                must=[
                    FieldCondition(key=key, match=MatchValue(value=value))
                    for key, value in filters.items()
                ]
            )
        results = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            query_filter=query_filter,
            limit=limit,
        )
        records: List[VectorRecord] = []
        for result in results:
            payload = result.payload or {}
            records.append(
                VectorRecord(
                    chunk_id=payload["chunk_id"],
                    content=payload["content"],
                    source=payload.get("source"),
                    metadata=payload.get("metadata") or {},
                    score=float(result.score or 0.0),
                )
            )
        return records


def _cosine(left: List[float], right: List[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    denominator = left_norm * right_norm
    if not denominator:
        return 0.0
    return numerator / denominator
