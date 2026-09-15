#!/usr/bin/env python3
"""Capture a LangChain-style run and gate its citation alignment offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from contexttrace import ContextTrace, ContextTraceCallbackHandler
from contexttrace.capture import capture_rag_trace, write_rag_trace
from contexttrace.verify import verify_trace


class Document:
    def __init__(self, text: str, chunk_id: str, source: str) -> None:
        self.page_content = text
        self.metadata = {"chunk_id": chunk_id, "source": source}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path(".contexttrace/langchain-ci-demo"))
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    query = "How long is the Northstar device warranty?"
    answer = "Northstar devices include a two-year warranty."
    documents = [
        Document("Northstar devices ship within two business days.", "shipping_faq", "shipping.md"),
        Document("Northstar devices include a two-year warranty.", "warranty_terms", "warranty.md"),
    ]
    citations = [{"claim": answer, "source_id": "shipping_faq"}]
    client = ContextTrace(
        mode="local", project="langchain-ci-demo",
        storage_path=str(args.out_dir / "contexttrace.db"),
    )
    handler = ContextTraceCallbackHandler(client=client)
    handler.on_chain_start({"name": "RetrievalQA"}, {"query": query})
    handler.on_retriever_start({"name": "VectorStoreRetriever"}, query)
    handler.on_retriever_end(documents)
    handler.on_chain_end({"answer": answer, "citations": citations})

    portable = capture_rag_trace(
        query=query, answer=answer, contexts=documents, citations=citations,
        metadata={"integration": "langchain", "construction_status": "fictional_demo"},
    )
    trace_path = Path(write_rag_trace(portable, args.out_dir / "portable-trace.json"))
    result = verify_trace(portable)
    summary = {
        "integration": "langchain",
        "captured_trace_id": getattr(handler.trace, "trace_id", ""),
        "portable_trace": str(trace_path),
        "failure_type": result["summary"]["failure_type"],
        "citation_mismatches": result["summary"]["citation_mismatches"],
        "gate_passed": result["summary"]["citation_mismatches"] == 1,
    }
    print(json.dumps(summary, indent=2))
    return 0 if summary["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
