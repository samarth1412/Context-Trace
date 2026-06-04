import json

import pytest

from contexttrace import capture_rag_trace, langchain_documents_to_contexts, write_rag_trace
from contexttrace.capture import context_to_trace_context


class MockDocument:
    def __init__(self, page_content, metadata=None, doc_id=None):
        self.page_content = page_content
        self.metadata = metadata or {}
        self.id = doc_id


def test_capture_rag_trace_from_dict_contexts_and_write_json(tmp_path):
    trace = capture_rag_trace(
        query="What vector store is used?",
        answer="The RAG engine uses FAISS.",
        contexts=[
            {
                "chunk_id": "chunk_1",
                "content": "The system performs vector search using FAISS.",
                "source": "main.py",
                "relevance_score": 0.91,
            }
        ],
        citations=[
            {
                "claim": "The RAG engine uses FAISS.",
                "source_chunk_id": "chunk_1",
            }
        ],
        metadata={"project": "real-rag"},
    )

    assert trace.contexts[0].id == "chunk_1"
    assert trace.contexts[0].text == "The system performs vector search using FAISS."
    assert trace.contexts[0].metadata["source"] == "main.py"
    assert trace.citations[0].source_id == "chunk_1"

    path = tmp_path / "trace.json"
    written = write_rag_trace(trace, path)

    assert written == str(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["query"] == "What vector store is used?"
    assert payload["contexts"][0]["id"] == "chunk_1"


def test_langchain_documents_to_contexts_uses_page_content_and_metadata():
    contexts = langchain_documents_to_contexts(
        [
            MockDocument(
                "Retrieved document text.",
                metadata={"source": "docs/readme.md", "chunk_id": "readme_1", "score": 0.88},
            )
        ]
    )

    assert contexts[0].id == "readme_1"
    assert contexts[0].text == "Retrieved document text."
    assert contexts[0].metadata["source"] == "docs/readme.md"


def test_context_capture_makes_source_chunk_ids_unique():
    contexts = langchain_documents_to_contexts(
        [
            MockDocument("Chunk one.", metadata={"source": "paper.txt", "chunk_index": 1}),
            MockDocument("Chunk two.", metadata={"source": "paper.txt", "chunk_index": 2}),
        ]
    )

    assert [context.id for context in contexts] == ["paper.txt:1", "paper.txt:2"]


def test_context_capture_rejects_empty_context_text():
    with pytest.raises(ValueError, match="text/content/page_content"):
        context_to_trace_context({"id": "empty", "text": ""})
