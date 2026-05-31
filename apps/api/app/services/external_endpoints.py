from __future__ import annotations

import json
import re
import time
from typing import Any, Iterable, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.judge import LLMJudgeProvider
from app.models import EvalSet, ExternalRAGEndpoint, Project, User
from app.schemas import (
    AnswerRequest,
    ChunkPayload,
    CitationPayload,
    CitationsRequest,
    ContextRequest,
    ExternalEndpointCreateRequest,
    ExternalEndpointEvalTrace,
    ExternalEndpointResponse,
    ExternalEndpointRunEvalRequest,
    ExternalEndpointRunEvalResponse,
    ExternalEndpointTestRequest,
    ExternalEndpointTestResponse,
    MappedExternalResponse,
    RetrievalRequest,
    TraceStartRequest,
)
from app.services.errors import BadRequestError, NotFoundError
from app.services.evals import aggregate_eval_set
from app.services.traces import TraceService


class ExternalEndpointService:
    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user

    def register_endpoint(
        self,
        project_id: str,
        request: ExternalEndpointCreateRequest,
    ) -> ExternalEndpointResponse:
        project = self._get_project(project_id)
        endpoint = self.db.scalar(
            select(ExternalRAGEndpoint).where(
                ExternalRAGEndpoint.project_id == project.id,
                ExternalRAGEndpoint.name == request.name,
            )
        )
        if endpoint is None:
            endpoint = ExternalRAGEndpoint(project_id=project.id, name=request.name)
            self.db.add(endpoint)

        endpoint.url = request.url
        endpoint.method = request.method
        endpoint.headers_json = request.headers
        endpoint.body_template_json = request.body_template
        endpoint.response_mapping_json = request.response_mapping
        self.db.commit()
        self.db.refresh(endpoint)
        return self._endpoint_response(endpoint)

    async def test_endpoint(
        self,
        endpoint_id: str,
        request: ExternalEndpointTestRequest,
    ) -> ExternalEndpointTestResponse:
        endpoint = self._get_endpoint(endpoint_id)
        result = await self._run_query(
            endpoint=endpoint,
            query=request.query,
            metadata=request.metadata,
        )
        return ExternalEndpointTestResponse(
            endpoint_id=endpoint.id,
            trace_id=result["trace_id"],
            mapped=result["mapped"],
        )

    async def run_eval(
        self,
        endpoint_id: str,
        request: ExternalEndpointRunEvalRequest,
        judge_provider: LLMJudgeProvider,
    ) -> ExternalEndpointRunEvalResponse:
        endpoint = self._get_endpoint(endpoint_id)
        eval_set = self._get_eval_set(request.eval_set_id)
        traces = []

        for question in eval_set.questions:
            result = await self._run_query(
                endpoint=endpoint,
                query=question.question,
                metadata={
                    "eval_set_id": eval_set.id,
                    "eval_question_id": question.id,
                    "expected_answer": question.expected_answer,
                    **(question.question_metadata or {}),
                },
                expected_answer=question.expected_answer,
            )
            question.trace_id = result["trace_id"]
            self.db.commit()
            evaluation = await TraceService(self.db, self.user).evaluate_trace(
                result["trace_id"],
                judge_provider,
            )
            traces.append(
                ExternalEndpointEvalTrace(
                    question_id=question.id,
                    question=question.question,
                    trace_id=result["trace_id"],
                    evaluation=evaluation,
                )
            )

        self.db.refresh(eval_set)
        return ExternalEndpointRunEvalResponse(
            endpoint_id=endpoint.id,
            eval_set_id=eval_set.id,
            traces=traces,
            summary=aggregate_eval_set(eval_set),
        )

    async def _run_query(
        self,
        *,
        endpoint: ExternalRAGEndpoint,
        query: str,
        metadata: dict[str, Any],
        expected_answer: Optional[str] = None,
    ) -> dict[str, Any]:
        body = render_body_template(
            endpoint.body_template_json or {},
            query=query,
            metadata=metadata,
            expected_answer=expected_answer,
        )
        started_at = time.perf_counter()
        raw_response = await call_external_endpoint(
            url=endpoint.url,
            method=endpoint.method,
            headers=endpoint.headers_json or {},
            body=body,
        )
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        mapped = map_external_response(raw_response, endpoint.response_mapping_json or {})
        trace_id = self._create_trace_from_mapped_response(
            endpoint=endpoint,
            query=query,
            mapped=mapped,
            metadata={
                "source": "external_rag_endpoint",
                "external_endpoint_id": endpoint.id,
                "external_endpoint_name": endpoint.name,
                "external_endpoint_url": endpoint.url,
                "latency_ms": latency_ms,
                **metadata,
            },
        )
        return {"trace_id": trace_id, "mapped": mapped}

    def _create_trace_from_mapped_response(
        self,
        *,
        endpoint: ExternalRAGEndpoint,
        query: str,
        mapped: MappedExternalResponse,
        metadata: dict[str, Any],
    ) -> str:
        trace_service = TraceService(self.db, self.user)
        started = trace_service.start_trace(
            TraceStartRequest(
                project=endpoint.project.name,
                query=query,
                metadata=metadata,
            )
        )
        trace_id = started.trace_id
        if mapped.retrieved_chunks:
            trace_service.log_retrieval(
                trace_id,
                RetrievalRequest(
                    chunks=mapped.retrieved_chunks,
                    retriever_name="external_rag_endpoint",
                    metadata={"external_endpoint_id": endpoint.id},
                ),
            )
            trace_service.log_context(
                trace_id,
                ContextRequest(
                    chunks=mapped.retrieved_chunks,
                    metadata={"source": "external_response_mapping"},
                ),
            )

        trace_service.log_answer(
            trace_id,
            AnswerRequest(
                answer=mapped.answer,
                model=mapped.model,
                usage=mapped.usage,
                metadata={"external_endpoint_id": endpoint.id},
            ),
        )
        trace_service.log_citations(
            trace_id,
            CitationsRequest(citations=mapped.citations),
        )
        return trace_id

    def _get_project(self, project_id: str) -> Project:
        project = self.db.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == self.user.id,
            )
        )
        if project is None:
            raise NotFoundError("Project not found.")
        return project

    def _get_endpoint(self, endpoint_id: str) -> ExternalRAGEndpoint:
        endpoint = self.db.scalar(
            select(ExternalRAGEndpoint)
            .join(Project)
            .where(
                ExternalRAGEndpoint.id == endpoint_id,
                Project.user_id == self.user.id,
            )
        )
        if endpoint is None:
            raise NotFoundError("External RAG endpoint not found.")
        return endpoint

    def _get_eval_set(self, eval_set_id: str) -> EvalSet:
        eval_set = self.db.scalar(
            select(EvalSet).where(
                EvalSet.id == eval_set_id,
                EvalSet.user_id == self.user.id,
            )
        )
        if eval_set is None:
            raise NotFoundError("Eval set not found.")
        return eval_set

    def _endpoint_response(self, endpoint: ExternalRAGEndpoint) -> ExternalEndpointResponse:
        return ExternalEndpointResponse(
            id=endpoint.id,
            project_id=endpoint.project_id,
            name=endpoint.name,
            url=endpoint.url,
            method=endpoint.method,
            headers=endpoint.headers_json or {},
            body_template=endpoint.body_template_json or {},
            response_mapping=endpoint.response_mapping_json or {},
            created_at=endpoint.created_at,
        )


async def call_external_endpoint(
    *,
    url: str,
    method: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout: float = 30.0,
) -> dict[str, Any]:
    method = method.upper()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                response = await client.get(url, headers=headers, params=body)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=body)
            else:
                raise BadRequestError("External endpoint method must be GET or POST.")
            response.raise_for_status()
            parsed = response.json()
    except httpx.HTTPStatusError as exc:
        raise BadRequestError(
            "External RAG endpoint returned HTTP %s." % exc.response.status_code
        ) from exc
    except httpx.HTTPError as exc:
        raise BadRequestError("External RAG endpoint request failed: %s" % exc) from exc
    except ValueError as exc:
        raise BadRequestError("External RAG endpoint returned invalid JSON.") from exc

    if not isinstance(parsed, dict):
        return {"value": parsed}
    return parsed


def render_body_template(
    template: Any,
    *,
    query: str,
    metadata: dict[str, Any],
    expected_answer: Optional[str],
) -> Any:
    if isinstance(template, dict):
        return {
            key: render_body_template(
                value,
                query=query,
                metadata=metadata,
                expected_answer=expected_answer,
            )
            for key, value in template.items()
        }
    if isinstance(template, list):
        return [
            render_body_template(
                value,
                query=query,
                metadata=metadata,
                expected_answer=expected_answer,
            )
            for value in template
        ]
    if isinstance(template, str):
        return _render_template_string(
            template,
            query=query,
            metadata=metadata,
            expected_answer=expected_answer,
        )
    return template


def map_external_response(
    raw_response: dict[str, Any],
    response_mapping: dict[str, str],
) -> MappedExternalResponse:
    mapping = {
        "answer": "$.answer",
        "retrieved_chunks": "$.retrieved_chunks",
        "citations": "$.citations",
        **response_mapping,
    }
    raw_answer = extract_json_path(raw_response, mapping["answer"])
    answer = _string_value(raw_answer)
    if not answer:
        raise BadRequestError("Mapped external response did not include an answer.")

    chunks = _normalize_chunks(extract_json_path(raw_response, mapping["retrieved_chunks"]))
    citations = _normalize_citations(
        extract_json_path(raw_response, mapping["citations"]),
        answer=answer,
        chunks=chunks,
    )
    usage = _dict_or_empty(extract_json_path(raw_response, mapping.get("usage", "$.usage")))
    model = _optional_string(extract_json_path(raw_response, mapping.get("model", "$.model")))

    return MappedExternalResponse(
        raw_response=raw_response,
        answer=answer,
        retrieved_chunks=chunks,
        citations=citations,
        usage=usage,
        model=model,
    )


def extract_json_path(data: Any, path: Optional[str]) -> Any:
    if not path:
        return None
    if path == "$":
        return data
    if not path.startswith("$"):
        raise BadRequestError("JSONPath must start with '$': %s" % path)

    current = [data]
    for token in _json_path_tokens(path[1:]):
        current = _apply_json_path_token(current, token)
    if not current:
        return None
    if len(current) == 1:
        return current[0]
    return current


def _json_path_tokens(path: str) -> list[Any]:
    tokens: list[Any] = []
    index = 0
    while index < len(path):
        char = path[index]
        if char == ".":
            index += 1
            start = index
            while index < len(path) and path[index] not in ".[":
                index += 1
            if start == index:
                raise BadRequestError("Invalid JSONPath: $.%s" % path)
            tokens.append(path[start:index])
            continue
        if char == "[":
            end = path.find("]", index)
            if end == -1:
                raise BadRequestError("Invalid JSONPath: missing ']'.")
            raw_token = path[index + 1 : end].strip()
            if raw_token == "*":
                tokens.append("*")
            elif raw_token.startswith(("'", '"')) and raw_token.endswith(("'", '"')):
                tokens.append(raw_token[1:-1])
            else:
                try:
                    tokens.append(int(raw_token))
                except ValueError as exc:
                    raise BadRequestError("Invalid JSONPath array index: %s" % raw_token) from exc
            index = end + 1
            continue
        raise BadRequestError("Invalid JSONPath near: %s" % path[index:])
    return tokens


def _apply_json_path_token(values: list[Any], token: Any) -> list[Any]:
    results = []
    for value in values:
        if token == "*":
            if isinstance(value, list):
                results.extend(value)
            elif isinstance(value, dict):
                results.extend(value.values())
        elif isinstance(token, int):
            if isinstance(value, list) and -len(value) <= token < len(value):
                results.append(value[token])
        elif isinstance(value, dict) and token in value:
            results.append(value[token])
    return results


def _normalize_chunks(value: Any) -> list[ChunkPayload]:
    items = _as_list(value)
    chunks = []
    for index, item in enumerate(items):
        if isinstance(item, str):
            chunks.append(
                ChunkPayload(
                    chunk_id="chunk_%s" % index,
                    content=item,
                    metadata={},
                )
            )
            continue
        if not isinstance(item, dict):
            continue
        chunk_id = (
            item.get("chunk_id")
            or item.get("id")
            or item.get("source_chunk_id")
            or item.get("source_id")
            or "chunk_%s" % index
        )
        content = (
            item.get("content")
            or item.get("text")
            or item.get("page_content")
            or item.get("context")
            or item.get("body")
        )
        if content is None:
            content = json.dumps(item, sort_keys=True)
        chunks.append(
            ChunkPayload(
                chunk_id=str(chunk_id),
                content=str(content),
                source=_optional_string(item.get("source") or item.get("url") or item.get("path")),
                metadata=_dict_or_empty(item.get("metadata")),
                relevance_score=_optional_float(
                    item.get("relevance_score")
                    if item.get("relevance_score") is not None
                    else item.get("score")
                ),
            )
        )
    return chunks


def _normalize_citations(
    value: Any,
    *,
    answer: str,
    chunks: list[ChunkPayload],
) -> list[CitationPayload]:
    citations = []
    for index, item in enumerate(_as_list(value)):
        if isinstance(item, str):
            source_chunk_id = chunks[index].chunk_id if index < len(chunks) else "chunk_%s" % index
            citations.append(
                CitationPayload(
                    claim=answer,
                    source_chunk_id=source_chunk_id or "chunk_%s" % index,
                    metadata={"external_citation": item, "inferred_claim": True},
                )
            )
            continue
        if not isinstance(item, dict):
            continue

        claim = item.get("claim") or item.get("statement") or item.get("answer_claim") or item.get("text")
        source_chunk_id = (
            item.get("source_chunk_id")
            or item.get("chunk_id")
            or item.get("id")
            or item.get("source_id")
            or item.get("document_id")
        )
        if source_chunk_id is None and index < len(chunks):
            source_chunk_id = chunks[index].chunk_id
        if not claim:
            claim = answer
        if source_chunk_id:
            citations.append(
                CitationPayload(
                    claim=str(claim),
                    source_chunk_id=str(source_chunk_id),
                    metadata=_dict_or_empty(item.get("metadata")) or {"external_citation": item},
                )
            )

    if not citations and chunks:
        citations.append(
            CitationPayload(
                claim=answer,
                source_chunk_id=chunks[0].chunk_id or "chunk_0",
                metadata={"inferred_from_context": True},
            )
        )
    return citations


def _render_template_string(
    template: str,
    *,
    query: str,
    metadata: dict[str, Any],
    expected_answer: Optional[str],
) -> str:
    replacements = {
        "query": query,
        "expected_answer": expected_answer or "",
    }

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key.startswith("metadata."):
            value = metadata.get(key.split(".", 1)[1], "")
            return "" if value is None else str(value)
        return str(replacements.get(key, ""))

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace, template)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
