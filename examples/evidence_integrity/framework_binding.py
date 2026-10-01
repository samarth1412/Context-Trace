from __future__ import annotations

import json
from importlib.metadata import version

from langchain_core.documents import Document
from llama_index.core.schema import NodeWithScore, TextNode

from contexttrace import (
    audit_evidence_integrity,
    bind_langchain_evidence_lineage,
    bind_llamaindex_evidence_lineage,
    capture_rag_trace,
)
from contexttrace.integrations.langchain import langchain_document_to_chunk
from contexttrace.integrations.llamaindex import llamaindex_node_to_chunk


def main() -> int:
    langchain_source = Document(
        id="refund_qa",
        page_content="Question: When are refunds issued? Answer: After approval.",
    )
    langchain_selected = Document(
        id="selected_question",
        page_content="Question: When are refunds issued?",
    )
    langchain_bound = bind_langchain_evidence_lineage(
        langchain_selected,
        source_document=langchain_source,
        linked_parts=[
            {
                "id": "question",
                "role": "question",
                "text": "Question: When are refunds issued?",
            },
            {"id": "answer", "role": "answer", "text": "Answer: After approval."},
        ],
        transformation="document_compressor",
    )

    llamaindex_source = NodeWithScore(
        node=TextNode(
            id_="returns_policy",
            text="Returns are accepted within 30 days. Only when unused.",
        ),
        score=0.97,
    )
    llamaindex_selected = NodeWithScore(
        node=TextNode(id_="selected_policy", text="Returns are accepted within 30 days."),
        score=0.91,
    )
    llamaindex_bound = bind_llamaindex_evidence_lineage(
        llamaindex_selected,
        source_node=llamaindex_source,
        material_spans=[
            {"id": "unused", "role": "condition", "text": "Only when unused."}
        ],
        transformation="node_postprocessor",
    )

    cases = [
        (
            "langchain",
            capture_rag_trace(
                query="When are refunds issued?",
                answer="After approval.",
                contexts=[langchain_document_to_chunk(langchain_bound)],
            ),
            "linked_part_dropped",
        ),
        (
            "llamaindex",
            capture_rag_trace(
                query="When are returns accepted?",
                answer="Within 30 days.",
                contexts=[llamaindex_node_to_chunk(llamaindex_bound)],
            ),
            "material_span_dropped",
        ),
    ]
    results = []
    for framework, trace, expected in cases:
        audit = audit_evidence_integrity(trace)
        observed = [item["type"] for item in audit["issues"]]
        results.append(
            {
                "framework": framework,
                "expected": expected,
                "observed": observed,
                "passed": observed == [expected],
                "network_calls": audit["network_calls"],
                "model_calls": audit["model_calls"],
            }
        )

    payload = {
        "versions": {
            "langchain-core": version("langchain-core"),
            "llama-index-core": version("llama-index-core"),
        },
        "inputs_unchanged": {
            "langchain": langchain_selected.metadata == {},
            "llamaindex": llamaindex_selected.node.metadata == {},
        },
        "passed": all(item["passed"] for item in results),
        "cases": results,
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["passed"] and all(payload["inputs_unchanged"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
