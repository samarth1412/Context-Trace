#!/usr/bin/env python3
"""Capture a LlamaIndex-style run and gate stale source use offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from contexttrace import ContextTrace, ContextTraceLlamaIndexCallbackHandler
from contexttrace.capture import capture_rag_trace, write_rag_trace
from contexttrace.verify import verify_trace


class Node:
    def __init__(self, text: str, node_id: str, metadata: dict) -> None:
        self.text = text
        self.node_id = node_id
        self.metadata = metadata

    def get_content(self) -> str:
        return self.text


class NodeWithScore:
    def __init__(self, node: Node, score: float) -> None:
        self.node = node
        self.score = score


class Response:
    def __init__(self, response: str, source_nodes: list[NodeWithScore]) -> None:
        self.response = response
        self.source_nodes = source_nodes

    def __str__(self) -> str:
        return self.response


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path(".contexttrace/llamaindex-source-demo"))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    query = "What is the current Acme Transit cancellation window?"
    answer = "Acme Transit passes may be cancelled within 45 days of purchase."
    node = Node(
        answer, "transit_policy_2024",
        {"source": "transit-cancellations.md", "version": "2024", "source_status": "stale"},
    )
    nodes = [NodeWithScore(node, 0.98)]
    client = ContextTrace(
        mode="local", project="llamaindex-source-demo",
        storage_path=str(args.out_dir / "contexttrace.db"),
    )
    handler = ContextTraceLlamaIndexCallbackHandler(client=client)
    handler.on_event_start("query", {"query_str": query}, event_id="query_1")
    handler.on_event_end("retrieve", {"nodes": nodes}, event_id="retrieve_1")
    handler.on_event_end("query", {"response": Response(answer, nodes)}, event_id="query_1")

    portable = capture_rag_trace(
        query=query, answer=answer, contexts=[node],
        citations=[{"claim": answer, "source_id": "transit_policy_2024"}],
        metadata={"integration": "llamaindex", "construction_status": "fictional_demo"},
    )
    trace_path = Path(write_rag_trace(portable, args.out_dir / "portable-trace.json"))
    result = verify_trace(portable)
    summary = {
        "integration": "llamaindex",
        "captured_trace_id": getattr(handler.trace, "trace_id", ""),
        "portable_trace": str(trace_path),
        "source_status": result["summary"]["source_status"],
        "should_abstain": result["summary"]["should_abstain"],
        "gate_passed": result["summary"]["source_status"] == "grounded_but_stale",
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
