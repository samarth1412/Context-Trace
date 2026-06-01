import pytest
import zipfile
from io import BytesIO

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


def test_document_parser_reads_docx_with_stdlib_zip_parser():
    parser = DocumentParser()
    buffer = BytesIO()
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>Refund policy text from DOCX.</w:t></w:r></w:p></w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)

    parsed = parser.parse(
        filename="policy.docx",
        content=buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    assert parsed.text == "Refund policy text from DOCX."


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
    assert "Refunds are available" in upload.json()["text_preview"]
    assert upload.json()["chunks"][0]["token_count"] > 0

    query = client.post(
        "/v1/playground/query",
        headers=auth_headers,
        json={"query": "What is the refund policy?", "top_k": 1, "strategy": "hybrid"},
    )

    assert query.status_code == 200
    body = query.json()
    assert "Refunds are available within 30 days" in body["answer"]
    assert body["strategy"] == "hybrid"
    assert len(body["retrieved_chunks"]) == 1
    assert len(body["selected_context"]) == 1
    assert body["metrics"]["latency_ms"] >= 0
    assert body["metrics"]["estimated_cost_usd"] >= 0
    assert body["evaluation"]["failure"]["failure_type"] == "no_failure_detected"

    fetched = client.get("/v1/traces/%s" % body["trace_id"], headers=auth_headers)
    assert fetched.status_code == 200
    trace = fetched.json()
    assert trace["project"] == "playground"
    assert trace["chunks"][0]["selected"] is True
    assert trace["citation_checks"][0]["support_status"] == "directly_supported"


def test_playground_compare_runs_selected_retrieval_strategies(client, auth_headers):
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
                (
                    b"Refunds are available within 30 days for eligible orders. "
                    b"Shipping windows depend on destination."
                ),
                "text/markdown",
            )
        },
    )
    assert upload.status_code == 201

    response = client.post(
        "/v1/playground/compare",
        headers=auth_headers,
        json={
            "query": "Refunds available within 30 days",
            "top_k": 1,
            "strategies": [
                "dense_top_k",
                "bm25_top_k",
                "hybrid",
                "hybrid_rerank",
                "corrective_rag",
                "contexttrace_adaptive",
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [result["strategy"] for result in body["results"]] == [
        "dense_top_k",
        "bm25_top_k",
        "hybrid",
        "hybrid_rerank",
        "corrective_rag",
        "contexttrace_adaptive",
    ]
    assert all(result["trace_id"] for result in body["results"])
    assert all(result["metrics"]["citation_support"] == 1.0 for result in body["results"])
    assert all(result["metrics"]["unsupported_claim_rate"] == 0.0 for result in body["results"])
    assert all(
        result["metrics"]["failure_type"] == "no_failure_detected"
        for result in body["results"]
    )
    assert all(result["metrics"]["latency_ms"] >= 0 for result in body["results"])
    assert all(result["metrics"]["estimated_cost_usd"] >= 0 for result in body["results"])


def test_playground_sample_datasets_load_and_query(client, auth_headers):
    vector_store = InMemoryVectorStore()
    client.app.dependency_overrides[get_vector_store] = lambda: vector_store
    client.app.dependency_overrides[get_embedding_provider] = lambda: HashEmbeddingProvider(
        dimensions=32
    )
    client.app.dependency_overrides[get_answer_provider] = lambda: MockAnswerProvider()

    samples = client.get("/v1/playground/samples", headers=auth_headers)
    assert samples.status_code == 200
    assert {sample["sample_id"] for sample in samples.json()["samples"]} >= {
        "employee_handbook",
        "refund_policy",
        "ai_paper_qa",
    }

    load = client.post("/v1/playground/samples/refund_policy/load", headers=auth_headers)
    assert load.status_code == 200
    body = load.json()
    assert body["sample_id"] == "refund_policy"
    assert body["chunk_count"] >= 1
    assert body["documents"][0]["chunks"][0]["metadata"]["sample_id"] == "refund_policy"

    query = client.post(
        "/v1/playground/query",
        headers=auth_headers,
        json={
            "query": body["suggested_queries"][0],
            "top_k": 2,
            "strategy": "contexttrace_adaptive",
        },
    )
    assert query.status_code == 200
    result = query.json()
    assert result["trace_id"]
    assert result["evaluation"]["failure"]["failure_type"] == "no_failure_detected"
    assert result["selected_context"]
