import pytest

from app.api.deps import get_answer_provider, get_embedding_provider, get_vector_store
from app.playground.documents import DocumentParser, ParsedDocument, TokenAwareChunker
from app.playground.providers import HashEmbeddingProvider, MockAnswerProvider
from app.playground.vector_store import InMemoryVectorStore


def test_document_parser_reads_txt_and_markdown():
    parser = DocumentParser()

    txt = parser.parse(
        filename="policy.txt",
        content=b"Refunds are available within 30 days.\n\nProcessing varies.",
        content_type="text/plain",
    )
    md = parser.parse(
        filename="policy.md",
        content=b"# Refund Policy\n\nRefunds are available within 30 days.",
        content_type="text/markdown",
    )

    assert txt.text == "Refunds are available within 30 days. Processing varies."
    assert txt.content_type == "text/plain"
    assert "Refund Policy" in md.text
    assert md.content_type == "text/markdown"


def test_document_parser_rejects_unsupported_types():
    parser = DocumentParser()

    with pytest.raises(ValueError, match="Unsupported document type"):
        parser.parse(
            filename="image.png",
            content=b"not a document",
            content_type="image/png",
        )


def test_token_aware_chunker_respects_max_tokens_and_overlap():
    document = ParsedDocument(
        filename="tokens.txt",
        content_type="text/plain",
        text=" ".join("t%d" % index for index in range(12)),
    )
    chunks = TokenAwareChunker(max_tokens=5, overlap_tokens=2).chunk(document)

    assert len(chunks) == 4
    assert [chunk.metadata["token_start"] for chunk in chunks] == [0, 3, 6, 9]
    assert all(chunk.metadata["token_count"] <= 5 for chunk in chunks)
    assert chunks[1].content.startswith("t3 t4")


def test_playground_upload_query_and_trace_creation(client, auth_headers):
    vector_store = InMemoryVectorStore()
    client.app.dependency_overrides[get_vector_store] = lambda: vector_store
    client.app.dependency_overrides[get_embedding_provider] = lambda: HashEmbeddingProvider(
        dimensions=32
    )
    client.app.dependency_overrides[get_answer_provider] = lambda: MockAnswerProvider()

    upload = client.post(
        "/v1/playground/documents",
        headers=auth_headers,
        files={
            "file": (
                "refund-policy.md",
                b"Refunds are available within 30 days for eligible orders.",
                "text/markdown",
            )
        },
    )

    assert upload.status_code == 201
    assert upload.json()["chunk_count"] == 1

    query = client.post(
        "/v1/playground/query",
        headers=auth_headers,
        json={"query": "What is the refund policy?", "top_k": 1},
    )

    assert query.status_code == 200
    body = query.json()
    assert "Refunds are available within 30 days" in body["answer"]
    assert len(body["retrieved_chunks"]) == 1
    assert body["evaluation"]["failure"]["failure_type"] == "no_failure_detected"

    fetched = client.get("/v1/traces/%s" % body["trace_id"], headers=auth_headers)
    assert fetched.status_code == 200
    trace = fetched.json()
    assert trace["project"] == "playground"
    assert trace["chunks"][0]["selected"] is True
    assert trace["citation_checks"][0]["support_status"] == "directly_supported"
