# ContextTrace-Diag-150 Audit Packet

Generated: `2026-06-23T21:17:47+00:00`
Commit: `a2f44be`
Status: `pending_human_signoff`
Reviewer: `Pending`

This packet is for independent human review of the `public_holdout` split. Do not call the split frozen until every case is signed off.

## Summary

| Field | Value |
| --- | ---: |
| Cases | 150 |
| Generated cases | 0 |
| Candidate input rows | 150 |
| Failure macro-F1 | 1.000 |
| Root-cause accuracy | 1.000 |
| Citation error F1 | 1.000 |
| Evidence span overlap | 0.950 |

## Label Distribution

| Label | Count |
| --- | ---: |
| `citation_mismatch` | 21 |
| `contradicted_answer` | 29 |
| `no_failure_detected` | 73 |
| `partial_support` | 26 |
| `should_have_abstained` | 30 |
| `unsupported_answer` | 1 |

## Source Family Balance

| Source family | Contexts |
| --- | ---: |
| `docs.langchain.com` | 16 |
| `github.com` | 11 |
| `qdrant.tech` | 11 |
| `docs.pinecone.io` | 10 |
| `docs.haystack.deepset.ai` | 9 |
| `developers.llamaindex.ai` | 8 |
| `docs.trychroma.com` | 8 |
| `docs.weaviate.io` | 8 |
| `milvus.io` | 8 |
| `opentelemetry.io` | 8 |
| `arize.com` | 6 |
| `developers.openai.com` | 6 |
| `docs.lancedb.com` | 6 |
| `docs.opensearch.org` | 6 |
| `docs.vespa.ai` | 6 |
| `elastic.co` | 6 |
| `learn.microsoft.com` | 6 |
| `mongodb.com` | 6 |
| `redis.io` | 6 |
| `trulens.org` | 6 |
| `dspy.ai` | 5 |
| `deepeval.com` | 3 |
| `docs.ragas.io` | 3 |
| `guardrailsai.com` | 2 |

## Reviewer Instructions

For each case, verify that the source URL opens, the context is fair to the source, the expected labels are correct, and the evidence span is the minimum source text needed to justify the label.

Required signoff fields: `source_url_opened`, `context_fair`, `label_correct`, `evidence_span_minimal`, `reviewer`, `reviewed_at`, `notes`.

## Cases

### Case 1: `holdout_otel_span_supported`

- Source family: `opentelemetry.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://opentelemetry.io/docs/concepts/signals/traces/

**Query:** What information does an OpenTelemetry span carry?

**Answer:** An OpenTelemetry span records information about an operation, such as a request in a service.

**Expected Evidence Spans**

- A tracer creates spans that carry information about what is happening during an operation, such as a service request.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 2: `holdout_otel_exporter_partial_support`

- Source family: `opentelemetry.io`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://opentelemetry.io/docs/concepts/signals/traces/

**Query:** Where can OpenTelemetry trace exporters send traces?

**Answer:** OpenTelemetry trace exporters can send traces to the Collector, stdout for debugging, or any backend, and they must always use Kafka.

**Expected Evidence Spans**

- Trace exporters send traces to a consumer.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 3: `holdout_weaviate_hybrid_supported`

- Source family: `docs.weaviate.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.weaviate.io/weaviate/search/hybrid

**Query:** What does Weaviate hybrid search combine?

**Answer:** Weaviate hybrid search combines vector search with keyword BM25F search and fuses the result sets.

**Expected Evidence Spans**

- Hybrid search in Weaviate combines vector search and keyword search using BM25F.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 4: `holdout_weaviate_hybrid_contradicted`

- Source family: `docs.weaviate.io`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://docs.weaviate.io/weaviate/search/hybrid

**Query:** Does Weaviate hybrid search use vector search?

**Answer:** Weaviate hybrid search never uses vector search; it only runs BM25 keyword search.

**Expected Evidence Spans**

- Hybrid search in Weaviate combines vector search and keyword search using BM25F.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 5: `holdout_llamaindex_retriever_supported`

- Source family: `developers.llamaindex.ai`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://developers.llamaindex.ai/python/framework/module_guides/querying/retriever/

**Query:** What does a LlamaIndex retriever return for a question?

**Answer:** A LlamaIndex retriever can retrieve relevant nodes from an index for a question.

**Expected Evidence Spans**

- A retriever is created from an index and retrieves relevant context for a question.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 6: `holdout_llamaindex_retriever_overclaim`

- Source family: `developers.llamaindex.ai`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://developers.llamaindex.ai/python/framework/module_guides/querying/retriever/

**Query:** What does a LlamaIndex retriever do?

**Answer:** A LlamaIndex retriever gets nodes from an index, reranks them, and writes the selected nodes back into the document store.

**Expected Evidence Spans**

- A retriever is created from an index and retrieves relevant context for a question.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 7: `holdout_milvus_range_search_supported`

- Source family: `milvus.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://milvus.io/docs/single-vector-search.md

**Query:** What can Milvus range search restrict?

**Answer:** Milvus range search can restrict returned entities by requiring their distance or score to fall within a configured range.

**Expected Evidence Spans**

- Milvus range search improves result relevance by limiting returned entities to embeddings whose distance or score fits inside the requested range.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 8: `holdout_milvus_wrong_source_citation`

- Source family: `milvus.io`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://docs.weaviate.io/weaviate/search/hybrid, https://milvus.io/docs/single-vector-search.md

**Query:** What can Milvus range search restrict?

**Answer:** Milvus range search can restrict returned entities by requiring their distance or score to fall within a configured range.

**Expected Evidence Spans**

- Milvus range search improves result relevance by limiting returned entities to embeddings whose distance or score fits inside the requested range.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 9: `holdout_langchain_retriever_supported`

- Source family: `docs.langchain.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.langchain.com/oss/python/integrations/retrievers

**Query:** What does a LangChain retriever return?

**Answer:** A LangChain retriever returns Document objects for an unstructured query.

**Expected Evidence Spans**

- Retrievers accept a string query as input and return a list of Document objects as output.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 10: `holdout_langchain_retriever_contradicted`

- Source family: `docs.langchain.com`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://docs.langchain.com/oss/python/integrations/retrievers

**Query:** Does a LangChain retriever need to store documents?

**Answer:** A LangChain retriever must store documents.

**Expected Evidence Spans**

- A LangChain retriever does not need to be able to store documents, only to return or retrieve them.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 11: `holdout_langchain_retriever_partial_rerank`

- Source family: `docs.langchain.com`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://docs.langchain.com/oss/python/integrations/retrievers

**Query:** What does a LangChain retriever do?

**Answer:** A LangChain retriever returns Document objects for an unstructured query. It always reranks results with a cross-encoder.

**Expected Evidence Spans**

- A LangChain retriever is an interface that returns documents given an unstructured query.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 12: `holdout_haystack_pipeline_supported`

- Source family: `docs.haystack.deepset.ai`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.haystack.deepset.ai/docs/pipelines

**Query:** What is a Haystack pipeline?

**Answer:** A Haystack pipeline is a directed multigraph of components and integrations.

**Expected Evidence Spans**

- Haystack pipelines are directed multigraphs of different Haystack components and integrations.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 13: `holdout_haystack_document_store_supported`

- Source family: `docs.haystack.deepset.ai`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.haystack.deepset.ai/docs/document-store

**Query:** What does a Haystack Document Store do?

**Answer:** A Haystack Document Store stores Documents.

**Expected Evidence Spans**

- A Document Store is an object that stores your Documents.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 14: `holdout_haystack_document_writer_partial`

- Source family: `docs.haystack.deepset.ai`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://docs.haystack.deepset.ai/docs/documentwriter

**Query:** What does Haystack DocumentWriter do?

**Answer:** Haystack DocumentWriter writes documents into a Document Store. It sends each written document to Slack.

**Expected Evidence Spans**

- DocumentWriter writes a list of documents into a Document Store of your choice.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 15: `holdout_qdrant_collection_supported`

- Source family: `qdrant.tech`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://qdrant.tech/documentation/manage-data/collections/

**Query:** What is a Qdrant collection?

**Answer:** A Qdrant collection is a named set of points with vectors and payload.

**Expected Evidence Spans**

- A collection is a named set of points, which are vectors with a payload, among which you can search.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 16: `holdout_qdrant_payload_filter_supported`

- Source family: `qdrant.tech`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://qdrant.tech/documentation/manage-data/payload/

**Query:** What is Qdrant payload used for?

**Answer:** Qdrant payload stores JSON information alongside vectors for filtering.

**Expected Evidence Spans**

- Qdrant allows JSON payload data and supports filters during search based on payload values.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 17: `holdout_qdrant_point_contradicted`

- Source family: `qdrant.tech`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://qdrant.tech/documentation/manage-data/points/

**Query:** Does a Qdrant point contain a vector?

**Answer:** A Qdrant point has no vector.

**Expected Evidence Spans**

- A point is a record consisting of a vector and an optional payload.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 18: `holdout_pinecone_record_metadata_supported`

- Source family: `docs.pinecone.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.pinecone.io/guides/index-data/indexing-overview

**Query:** What must a Pinecone record contain?

**Answer:** A Pinecone record must contain an ID and a vector.

**Expected Evidence Spans**

- Every record in a Pinecone index must contain an ID and a vector.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 19: `holdout_pinecone_metadata_filter_partial`

- Source family: `docs.pinecone.io`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://docs.pinecone.io/guides/search/filter-by-metadata

**Query:** What does Pinecone metadata filtering do?

**Answer:** A Pinecone metadata filter limits search to matching records. It re-embeds every record during search.

**Expected Evidence Spans**

- When you search the Pinecone index, you can include a metadata filter to limit the search to records matching the filter expression.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 20: `holdout_pinecone_namespace_supported`

- Source family: `docs.pinecone.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.pinecone.io/guides/index-data/indexing-overview

**Query:** What happens when Pinecone search has no metadata filter?

**Answer:** A Pinecone search without metadata filters searches the entire namespace.

**Expected Evidence Spans**

- When querying a Pinecone index, searches without metadata filters do not consider metadata and search the entire namespace.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 21: `holdout_chroma_collection_supported`

- Source family: `docs.trychroma.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.trychroma.com/docs/collections/manage-collections

**Query:** What is a Chroma collection?

**Answer:** A Chroma collection is the fundamental unit of storage and querying.

**Expected Evidence Spans**

- Collections are the fundamental unit of storage and querying in Chroma.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 22: `holdout_chroma_query_supported`

- Source family: `docs.trychroma.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.trychroma.com/docs/querying-collections/query-and-get

**Query:** How does Chroma handle text queries?

**Answer:** Chroma embeds text queries with the collection embedding function before vector similarity search.

**Expected Evidence Spans**

- Chroma uses the collection's embedding function to embed text queries and uses the output to run a vector similarity search against the collection.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 23: `holdout_chroma_update_contradicted`

- Source family: `docs.trychroma.com`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://docs.trychroma.com/docs/collections/update-data

**Query:** Does Chroma recompute embeddings when update documents omit embeddings?

**Answer:** Chroma never recomputes embeddings when documents are supplied without embeddings.

**Expected Evidence Spans**

- If documents are supplied without corresponding embeddings, the embeddings will be recomputed with the collection's embedding function.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 24: `holdout_ragas_faithfulness_supported`

- Source family: `docs.ragas.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/

**Query:** What does RAGAS Faithfulness measure?

**Answer:** RAGAS Faithfulness measures factual consistency of a response with retrieved context.

**Expected Evidence Spans**

- The RAGAS Faithfulness metric measures how factually consistent a response is with the retrieved context.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 25: `holdout_ragas_context_precision_supported`

- Source family: `docs.ragas.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/context_precision/

**Query:** What does RAGAS Context Precision evaluate?

**Answer:** RAGAS Context Precision evaluates whether relevant chunks are ranked higher than irrelevant ones.

**Expected Evidence Spans**

- Context Precision evaluates the retriever's ability to rank relevant chunks higher than irrelevant chunks for a given query in the retrieved context.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 26: `holdout_ragas_answer_relevancy_contradicted`

- Source family: `docs.ragas.io`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/

**Query:** Does RAGAS Answer Relevancy evaluate factual accuracy?

**Answer:** RAGAS Answer Relevancy evaluates factual accuracy.

**Expected Evidence Spans**

- It focuses on how well the answer matches the intent of the question without evaluating factual accuracy.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 27: `holdout_deepeval_faithfulness_supported`

- Source family: `deepeval.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://deepeval.com/docs/metrics-faithfulness

**Query:** What does DeepEval faithfulness evaluate?

**Answer:** DeepEval faithfulness evaluates whether actual_output factually aligns with retrieval_context.

**Expected Evidence Spans**

- DeepEval's faithfulness metric uses LLM-as-a-judge to evaluate whether the actual_output factually aligns with the contents of the retrieval_context.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 28: `holdout_deepeval_contextual_relevancy_supported`

- Source family: `deepeval.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://deepeval.com/docs/metrics-contextual-relevancy

**Query:** What does DeepEval contextual relevancy evaluate?

**Answer:** DeepEval contextual relevancy evaluates retrieval_context relevance for a given input.

**Expected Evidence Spans**

- The contextual relevancy metric uses LLM-as-a-judge to measure the relevance of the information presented in retrieval_context for a given input.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 29: `holdout_deepeval_hallucination_partial`

- Source family: `deepeval.com`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://deepeval.com/docs/metrics-hallucination

**Query:** What does DeepEval hallucination compare?

**Answer:** DeepEval hallucination compares actual_output to the provided context. It updates the retrieval context.

**Expected Evidence Spans**

- The hallucination metric uses LLM-as-a-judge to determine whether an LLM generates factually correct information by comparing the actual_output to the provided context.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 30: `holdout_otel_logs_supported`

- Source family: `opentelemetry.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://opentelemetry.io/docs/concepts/signals/logs/

**Query:** What is an OpenTelemetry log?

**Answer:** An OpenTelemetry log is a timestamped text record with optional metadata.

**Expected Evidence Spans**

- A log is a timestamped text record, either structured or unstructured, with optional metadata.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 31: `holdout_otel_baggage_supported`

- Source family: `opentelemetry.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://opentelemetry.io/docs/concepts/context-propagation/

**Query:** What does OpenTelemetry baggage propagate?

**Answer:** OpenTelemetry baggage propagates arbitrary key-value pairs across service boundaries.

**Expected Evidence Spans**

- Baggage allows you to propagate arbitrary key-value pairs. This data is propagated across service boundaries.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 32: `holdout_otel_resource_partial_encryption`

- Source family: `opentelemetry.io`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://opentelemetry.io/docs/concepts/resources/

**Query:** What does an OpenTelemetry resource represent?

**Answer:** An OpenTelemetry resource represents the entity producing telemetry. It encrypts telemetry payloads by default.

**Expected Evidence Spans**

- A resource represents the entity producing telemetry as resource attributes. For example, a process producing telemetry in Kubernetes can include process name, pod name, namespace, and deployment name.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 33: `holdout_otel_metrics_contradicted`

- Source family: `opentelemetry.io`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://opentelemetry.io/docs/specs/otel/metrics/

**Query:** Can the OpenTelemetry Metrics API capture raw measurements?

**Answer:** The OpenTelemetry Metrics API cannot capture raw measurements.

**Expected Evidence Spans**

- The OpenTelemetry Metrics API serves two purposes: capturing raw measurements efficiently and decoupling instrumentation from the SDK.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 34: `holdout_otel_baggage_wrong_source_citation`

- Source family: `opentelemetry.io`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://opentelemetry.io/docs/concepts/context-propagation/, https://opentelemetry.io/docs/concepts/signals/logs/

**Query:** What does OpenTelemetry baggage propagate?

**Answer:** OpenTelemetry baggage propagates arbitrary key-value pairs across service boundaries.

**Expected Evidence Spans**

- Baggage allows you to propagate arbitrary key-value pairs. This data is propagated across service boundaries.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 35: `holdout_langchain_vectorstore_supported`

- Source family: `docs.langchain.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.langchain.com/oss/python/integrations/vectorstores

**Query:** What can LangChain vector stores do?

**Answer:** LangChain vector stores store embedded data and perform similarity search.

**Expected Evidence Spans**

- A vector store stores embedded data and performs similarity search. LangChain provides a unified interface for vector stores.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 36: `holdout_langchain_text_splitter_supported`

- Source family: `docs.langchain.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.langchain.com/oss/python/integrations/splitters

**Query:** What do LangChain text splitters do?

**Answer:** LangChain text splitters break large documents into smaller retrievable chunks.

**Expected Evidence Spans**

- Text splitters break large docs into smaller chunks that will be retrievable individually and fit within model context window limit.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 37: `holdout_langchain_chat_model_supported`

- Source family: `docs.langchain.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.langchain.com/oss/python/integrations/chat

**Query:** What input and output do LangChain chat models use?

**Answer:** LangChain chat models use a sequence of messages as inputs and return messages as outputs.

**Expected Evidence Spans**

- Chat models are language models that use a sequence of messages as inputs and return messages as outputs.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 38: `holdout_langchain_structured_output_partial_xml`

- Source family: `docs.langchain.com`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://docs.langchain.com/oss/python/langchain/structured-output

**Query:** What does LangChain structured output return?

**Answer:** LangChain structured output can return JSON objects, Pydantic models, or dataclasses. It only supports XML.

**Expected Evidence Spans**

- Structured output allows agents to return data in a specific, predictable format. Instead of parsing natural language responses, you get structured data in the form of JSON objects, Pydantic models, or dataclasses.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 39: `holdout_langchain_vectorstore_delete_contradicted`

- Source family: `docs.langchain.com`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://docs.langchain.com/oss/python/integrations/vectorstores

**Query:** Can LangChain vector stores delete stored documents?

**Answer:** LangChain vector stores cannot delete stored documents.

**Expected Evidence Spans**

- LangChain provides a unified interface for vector stores, allowing you to add documents, delete stored documents by ID, and run similarity search.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 40: `holdout_langchain_text_splitter_wrong_source_citation`

- Source family: `docs.langchain.com`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://docs.langchain.com/oss/python/integrations/chat, https://docs.langchain.com/oss/python/integrations/splitters

**Query:** What do LangChain text splitters do?

**Answer:** LangChain text splitters break large documents into smaller retrievable chunks.

**Expected Evidence Spans**

- Text splitters break large docs into smaller chunks that will be retrievable individually and fit within model context window limit.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 41: `holdout_haystack_retrievers_supported`

- Source family: `docs.haystack.deepset.ai`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.haystack.deepset.ai/docs/retrievers

**Query:** What do Haystack retrievers do?

**Answer:** Haystack retrievers select documents from a Document Store that match the user query.

**Expected Evidence Spans**

- Retrievers go through all the documents in a Document Store and select the ones that match the user query.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 42: `holdout_haystack_generators_supported`

- Source family: `docs.haystack.deepset.ai`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.haystack.deepset.ai/docs/generators

**Query:** What are Haystack generators responsible for?

**Answer:** Haystack generators generate text after receiving a prompt.

**Expected Evidence Spans**

- Generators are responsible for generating text after you give them a prompt. They are specific for each LLM technology.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 43: `holdout_haystack_document_splitter_supported`

- Source family: `docs.haystack.deepset.ai`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.haystack.deepset.ai/docs/documentsplitter

**Query:** What does Haystack DocumentSplitter do?

**Answer:** Haystack DocumentSplitter divides text documents into shorter documents.

**Expected Evidence Spans**

- DocumentSplitter divides a list of text documents into a list of shorter text documents.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 44: `holdout_haystack_rankers_supported`

- Source family: `docs.haystack.deepset.ai`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.haystack.deepset.ai/docs/rankers

**Query:** What do Haystack rankers do?

**Answer:** Haystack rankers order documents by given criteria to improve retrieval results.

**Expected Evidence Spans**

- Rankers are a group of components that order Documents by given criteria. Their goal is to improve your document retrieval results.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 45: `holdout_haystack_document_store_run_contradicted`

- Source family: `docs.haystack.deepset.ai`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://docs.haystack.deepset.ai/docs/document-store

**Query:** Does a Haystack Document Store have the run method?

**Answer:** A Haystack Document Store has the run method.

**Expected Evidence Spans**

- In Haystack, a Document Store is different from a component, as it does not have the run method.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 46: `holdout_haystack_generator_partial_vectorstore`

- Source family: `docs.haystack.deepset.ai`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://docs.haystack.deepset.ai/docs/generators

**Query:** What does a Haystack generator output?

**Answer:** A Haystack generator creates text after a prompt. It writes the generated text into every vector store.

**Expected Evidence Spans**

- Generators are responsible for generating text after you give them a prompt. They are specific for each LLM technology.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 47: `holdout_qdrant_filtering_supported`

- Source family: `qdrant.tech`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://qdrant.tech/documentation/search/filtering/

**Query:** What can Qdrant filters constrain?

**Answer:** Qdrant filters can impose conditions on payload and point IDs during search or retrieval.

**Expected Evidence Spans**

- With Qdrant, you can set conditions when searching or retrieving points. For example, you can impose conditions on both the payload and the id of the point.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 48: `holdout_qdrant_quantization_supported`

- Source family: `qdrant.tech`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://qdrant.tech/documentation/manage-data/quantization/

**Query:** What does Qdrant product quantization do?

**Answer:** Qdrant product quantization compresses vectors to minimize memory usage.

**Expected Evidence Spans**

- Product quantization is a method of compressing vectors to minimize their memory usage by dividing them into chunks and quantizing each segment individually.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 49: `holdout_qdrant_snapshots_supported`

- Source family: `qdrant.tech`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://qdrant.tech/documentation/snapshots/

**Query:** What can Qdrant snapshots do?

**Answer:** Qdrant snapshots can be used to recover a collection from a URL or local file.

**Expected Evidence Spans**

- To recover from a URL or local file, use the snapshot recovery endpoint. If the target collection does not exist, it will be created.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 50: `holdout_qdrant_hybrid_queries_supported`

- Source family: `qdrant.tech`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://qdrant.tech/documentation/search/hybrid-queries/

**Query:** What can Qdrant hybrid queries fuse?

**Answer:** Qdrant hybrid queries can fuse dense, sparse, and multivector results.

**Expected Evidence Spans**

- Hybrid queries in Qdrant can fuse dense, sparse, and multivector results with RRF or DBSF.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 51: `holdout_qdrant_filtering_partial_encryption`

- Source family: `qdrant.tech`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://qdrant.tech/documentation/search/filtering/

**Query:** What can Qdrant filters do?

**Answer:** Qdrant filters can impose conditions on payload values and point IDs. They rotate encryption keys for matching points.

**Expected Evidence Spans**

- With Qdrant, you can set conditions when searching or retrieving points. For example, you can impose conditions on both the payload and the id of the point.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 52: `holdout_qdrant_quantization_contradicted`

- Source family: `qdrant.tech`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://qdrant.tech/documentation/manage-data/quantization/

**Query:** Does Qdrant product quantization compress vectors?

**Answer:** Qdrant product quantization does not compress vectors.

**Expected Evidence Spans**

- Product quantization is a method of compressing vectors to minimize their memory usage.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 53: `holdout_qdrant_snapshot_wrong_source_citation`

- Source family: `qdrant.tech`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://qdrant.tech/documentation/manage-data/quantization/, https://qdrant.tech/documentation/snapshots/

**Query:** What can Qdrant snapshots do?

**Answer:** Qdrant snapshots can be used to recover a collection from a URL or local file.

**Expected Evidence Spans**

- To recover from a URL or local file, use the snapshot recovery endpoint. If the target collection does not exist, it will be created.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 54: `holdout_pinecone_upsert_supported`

- Source family: `docs.pinecone.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.pinecone.io/reference/api/2024-07/data-plane/upsert

**Query:** What does Pinecone upsert do?

**Answer:** Pinecone upsert writes vectors into a namespace.

**Expected Evidence Spans**

- The upsert operation writes vectors into a namespace. If a new value is upserted for an existing vector ID, it will overwrite the previous value.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 55: `holdout_pinecone_delete_metadata_supported`

- Source family: `docs.pinecone.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.pinecone.io/guides/manage-data/delete-data

**Query:** Can Pinecone delete records by metadata?

**Answer:** Pinecone can delete records from a namespace using a metadata filter expression.

**Expected Evidence Spans**

- To delete records from a namespace based on their metadata values, pass a metadata filter expression to the delete operation.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 56: `holdout_pinecone_hybrid_search_supported`

- Source family: `docs.pinecone.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.pinecone.io/guides/search/hybrid-search

**Query:** What can Pinecone hybrid search combine?

**Answer:** Pinecone hybrid search can combine dense vectors for semantic search with sparse vectors for lexical search.

**Expected Evidence Spans**

- You can start with dense vectors for semantic search and add sparse vectors for lexical search later. You can do sparse-only queries and rerank at multiple levels.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 57: `holdout_pinecone_upsert_overwrite_contradicted`

- Source family: `docs.pinecone.io`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://docs.pinecone.io/reference/api/2024-07/data-plane/upsert

**Query:** Does Pinecone upsert overwrite an existing vector ID?

**Answer:** Pinecone upsert never overwrites an existing vector ID.

**Expected Evidence Spans**

- If a new value is upserted for an existing vector ID, it will overwrite the previous value.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 58: `holdout_pinecone_sparse_only_contradicted`

- Source family: `docs.pinecone.io`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://docs.pinecone.io/guides/search/hybrid-search

**Query:** Can Pinecone hybrid search do sparse-only queries?

**Answer:** Pinecone hybrid search cannot do sparse-only queries.

**Expected Evidence Spans**

- Pinecone hybrid search can use dense vectors for semantic search, sparse vectors for lexical search, and sparse-only queries.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 59: `holdout_pinecone_delete_wrong_source_citation`

- Source family: `docs.pinecone.io`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://docs.pinecone.io/guides/manage-data/delete-data, https://docs.pinecone.io/reference/api/2024-07/data-plane/upsert

**Query:** Can Pinecone delete records by metadata?

**Answer:** Pinecone can delete records from a namespace using a metadata filter expression.

**Expected Evidence Spans**

- To delete records from a namespace based on their metadata values, pass a metadata filter expression to the delete operation.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 60: `holdout_chroma_metadata_filter_supported`

- Source family: `docs.trychroma.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.trychroma.com/docs/querying-collections/metadata-filtering

**Query:** What does Chroma's where argument do?

**Answer:** Chroma's where argument filters records by metadata in get and query.

**Expected Evidence Spans**

- The where argument in get and query is used to filter records by their metadata.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 61: `holdout_chroma_delete_supported`

- Source family: `docs.trychroma.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.trychroma.com/docs/collections/delete-data

**Query:** What happens when Chroma deletes items by ID?

**Answer:** Chroma delete removes the embeddings, documents, and metadata associated with the deleted item IDs.

**Expected Evidence Spans**

- Chroma supports deleting items from a collection by id using delete. The embeddings, documents, and metadata associated with each item will be deleted.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 62: `holdout_chroma_embedding_functions_supported`

- Source family: `docs.trychroma.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.trychroma.com/docs/embeddings/embedding-functions

**Query:** When can Chroma use embedding functions?

**Answer:** Chroma embedding functions can be used when calling add, update, upsert, or query.

**Expected Evidence Spans**

- Embedding functions can be linked to a collection and used whenever you call add, update, upsert or query.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 63: `holdout_chroma_delete_where_contradicted`

- Source family: `docs.trychroma.com`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://docs.trychroma.com/docs/collections/delete-data

**Query:** Can Chroma delete use a where filter?

**Answer:** Chroma delete cannot use a where filter.

**Expected Evidence Spans**

- Chroma delete supports the where filter. It will delete all items in the collection that match the where filter.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 64: `holdout_chroma_embedding_partial_delete`

- Source family: `docs.trychroma.com`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://docs.trychroma.com/docs/embeddings/embedding-functions

**Query:** How does Chroma use embedding functions?

**Answer:** Chroma embedding functions can be linked to a collection and used for add, update, upsert, or query. They delete records automatically.

**Expected Evidence Spans**

- Embedding functions can be linked to a collection and used whenever you call add, update, upsert or query.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 65: `holdout_weaviate_filters_supported`

- Source family: `docs.weaviate.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.weaviate.io/weaviate/search/filters

**Query:** What do Weaviate filters do?

**Answer:** Weaviate filters include or exclude objects from a result set based on conditions.

**Expected Evidence Spans**

- Filters let you include, or exclude, particular objects from your result set based on provided conditions.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 66: `holdout_weaviate_reranking_supported`

- Source family: `docs.weaviate.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.weaviate.io/weaviate/search/rerank

**Query:** What do Weaviate reranking modules do?

**Answer:** Weaviate reranking modules reorder search results using a different set of criteria or algorithm.

**Expected Evidence Spans**

- Reranking modules reorder the search result set according to a different set of criteria or a different algorithm.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 67: `holdout_weaviate_rag_supported`

- Source family: `docs.weaviate.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.weaviate.io/weaviate/search/generative

**Query:** What are the two parts of a Weaviate RAG query?

**Answer:** A Weaviate RAG query consists of a search query and a prompt for the model.

**Expected Evidence Spans**

- In Weaviate, a RAG query consists of two parts: a search query, and a prompt for the model.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 68: `holdout_weaviate_multitenancy_supported`

- Source family: `docs.weaviate.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.weaviate.io/weaviate/manage-collections/multi-tenancy

**Query:** What does Weaviate multi-tenancy provide?

**Answer:** Weaviate multi-tenancy provides data isolation by storing each tenant on a separate shard.

**Expected Evidence Spans**

- Multi-tenancy provides data isolation. Each tenant is stored on a separate shard. Data stored in one tenant is not visible to another tenant.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 69: `holdout_weaviate_filters_contradicted`

- Source family: `docs.weaviate.io`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://docs.weaviate.io/weaviate/search/filters

**Query:** Do Weaviate filters include or exclude objects?

**Answer:** Weaviate filters do not include or exclude objects from result sets.

**Expected Evidence Spans**

- Filters let you include, or exclude, particular objects from your result set based on provided conditions.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 70: `holdout_milvus_scalar_filter_supported`

- Source family: `milvus.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://milvus.io/docs/boolean.md

**Query:** How does Milvus conduct scalar filtering?

**Answer:** Milvus conducts scalar filtering by searching with predicates.

**Expected Evidence Spans**

- Milvus conducts scalar filtering by searching with predicates. A predicate expression returns either TRUE or FALSE.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 71: `holdout_milvus_full_text_supported`

- Source family: `milvus.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://milvus.io/docs/full-text-search.md

**Query:** What does Milvus full text search retrieve?

**Answer:** Milvus full text search retrieves documents containing specific terms or phrases and ranks results by relevance.

**Expected Evidence Spans**

- Full text search retrieves documents containing specific terms or phrases in text datasets, then ranks the results based on relevance.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 72: `holdout_milvus_reranking_supported`

- Source family: `milvus.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://milvus.io/docs/reranking.md

**Query:** What does Milvus hybrid search use reranking for?

**Answer:** Milvus hybrid search uses reranking strategies to refine results from multiple AnnSearchRequest instances.

**Expected Evidence Spans**

- Milvus enables hybrid search capabilities using the hybrid_search API, incorporating sophisticated reranking strategies to refine search results from multiple AnnSearchRequest instances.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 73: `holdout_milvus_full_text_contradicted`

- Source family: `milvus.io`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://milvus.io/docs/full-text-search.md

**Query:** Can Milvus full text search retrieve documents containing specific terms?

**Answer:** Milvus full text search cannot retrieve documents containing specific terms or phrases.

**Expected Evidence Spans**

- Full text search retrieves documents containing specific terms or phrases in text datasets, then ranks the results based on relevance.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 74: `holdout_milvus_reranking_wrong_source_citation`

- Source family: `milvus.io`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://milvus.io/docs/boolean.md, https://milvus.io/docs/reranking.md

**Query:** What does Milvus hybrid search use reranking for?

**Answer:** Milvus hybrid search uses reranking strategies to refine results from multiple AnnSearchRequest instances.

**Expected Evidence Spans**

- Milvus enables hybrid search capabilities using the hybrid_search API, incorporating sophisticated reranking strategies to refine search results from multiple AnnSearchRequest instances.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 75: `holdout_langsmith_evaluation_workflow_supported`

- Source family: `docs.langchain.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.langchain.com/langsmith/evaluation

**Query:** What are the main steps in a LangSmith evaluation workflow?

**Answer:** LangSmith evaluations start by creating a dataset, defining evaluators, and running an experiment.

**Expected Evidence Spans**

- LangSmith evaluations start by creating a dataset, defining evaluators, and running an experiment.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 76: `holdout_langsmith_evaluators_supported`

- Source family: `docs.langchain.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.langchain.com/langsmith/evaluators

**Query:** How are LangSmith evaluators managed?

**Answer:** LangSmith evaluators are workspace-level resources that can be attached to multiple tracing projects and datasets.

**Expected Evidence Spans**

- Evaluators in LangSmith are workspace-level resources. You can attach a single evaluator to multiple tracing projects and datasets.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 77: `holdout_langsmith_dataset_partial_prompt_rewrite`

- Source family: `docs.langchain.com`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://docs.langchain.com/langsmith/evaluation

**Query:** How can LangSmith evaluation datasets be created?

**Answer:** LangSmith datasets can be created from manually curated test cases. They automatically rewrite production prompts.

**Expected Evidence Spans**

- Create a dataset with examples from manually curated test cases, historical production traces, or synthetic data generation.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 78: `holdout_langsmith_llm_judge_contradicted`

- Source family: `docs.langchain.com`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://docs.langchain.com/langsmith/evaluation

**Query:** Can LangSmith evaluations use LLM-as-judge evaluators?

**Answer:** LangSmith evaluations cannot use LLM-as-judge evaluators.

**Expected Evidence Spans**

- LangSmith evaluators can score performance using human review, code rules, LLM-as-judge, or pairwise comparison.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 79: `holdout_langsmith_evaluator_wrong_source_citation`

- Source family: `docs.langchain.com`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://docs.langchain.com/langsmith/evaluation, https://docs.langchain.com/langsmith/evaluators

**Query:** How are LangSmith evaluators managed?

**Answer:** LangSmith evaluators are workspace-level resources that can be attached to multiple tracing projects and datasets.

**Expected Evidence Spans**

- Evaluators in LangSmith are workspace-level resources. You can attach a single evaluator to multiple tracing projects and datasets.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 80: `holdout_phoenix_tracing_supported`

- Source family: `arize.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://arize.com/docs/phoenix

**Query:** What can Phoenix traces capture?

**Answer:** Phoenix traces capture model calls, retrieval, tool use, and custom logic.

**Expected Evidence Spans**

- Tracing lets you see what happened during a single run of your AI application. A trace captures model calls, retrieval, tool use, and custom logic.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 81: `holdout_phoenix_otlp_supported`

- Source family: `arize.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://arize.com/docs/phoenix

**Query:** How can Phoenix receive traces?

**Answer:** Phoenix accepts traces over OpenTelemetry OTLP.

**Expected Evidence Spans**

- Phoenix accepts traces over OpenTelemetry (OTLP) and provides auto-instrumentation for popular frameworks, providers, and languages.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 82: `holdout_phoenix_dataset_partial_delete`

- Source family: `arize.com`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://arize.com/docs/phoenix/datasets-and-experiments/overview-datasets

**Query:** What do Phoenix datasets contain?

**Answer:** Phoenix datasets contain examples with inputs and optional reference outputs. They delete production spans automatically.

**Expected Evidence Spans**

- Datasets are collections of examples that provide the inputs and, optionally, expected reference outputs for assessing your application.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 83: `holdout_phoenix_retrieval_contradicted`

- Source family: `arize.com`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://arize.com/docs/phoenix

**Query:** Can Phoenix traces capture retrieval?

**Answer:** Phoenix traces cannot capture retrieval.

**Expected Evidence Spans**

- A trace captures model calls, retrieval, tool use, and custom logic so you can debug behavior and understand where time is spent.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 84: `holdout_phoenix_dataset_wrong_source_citation`

- Source family: `arize.com`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://arize.com/docs/phoenix, https://arize.com/docs/phoenix/datasets-and-experiments/overview-datasets

**Query:** What do Phoenix datasets contain?

**Answer:** Phoenix datasets contain examples with inputs and optional reference outputs.

**Expected Evidence Spans**

- Datasets are collections of examples that provide the inputs and, optionally, expected reference outputs for assessing your application.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 85: `holdout_trulens_rag_triad_supported`

- Source family: `trulens.org`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://www.trulens.org/getting_started/core_concepts/rag_triad/

**Query:** What evaluations make up the TruLens RAG triad?

**Answer:** The TruLens RAG triad is made up of context relevance, groundedness, and answer relevance.

**Expected Evidence Spans**

- The RAG triad is made up of three evaluations: context relevance, groundedness, and answer relevance.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 86: `holdout_trulens_feedback_functions_supported`

- Source family: `trulens.org`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://www.trulens.org/getting_started/core_concepts/feedback_functions/

**Query:** What kinds of feedback functions does TruLens provide?

**Answer:** TruLens provides feedback functions such as groundedness NLI, sentiment, language match, and moderation.

**Expected Evidence Spans**

- TruLens provides feedback functions such as groundedness NLI, sentiment, language match, moderation, and more.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 87: `holdout_trulens_rag_triad_partial_guarantee`

- Source family: `trulens.org`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://www.trulens.org/getting_started/core_concepts/rag_triad/

**Query:** What does the TruLens RAG triad evaluate?

**Answer:** The TruLens RAG triad evaluates context relevance, groundedness, and answer relevance. It guarantees every LLM app is hallucination-free.

**Expected Evidence Spans**

- The RAG triad is made up of three evaluations: context relevance, groundedness, and answer relevance.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 88: `holdout_trulens_groundedness_contradicted`

- Source family: `trulens.org`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://www.trulens.org/getting_started/core_concepts/rag_triad/

**Query:** Does the TruLens RAG triad include groundedness?

**Answer:** The TruLens RAG triad does not include groundedness.

**Expected Evidence Spans**

- The RAG triad is made up of three evaluations: context relevance, groundedness, and answer relevance.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 89: `holdout_trulens_feedback_wrong_source_citation`

- Source family: `trulens.org`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://www.trulens.org/getting_started/core_concepts/feedback_functions/, https://www.trulens.org/getting_started/core_concepts/rag_triad/

**Query:** What kinds of feedback functions does TruLens provide?

**Answer:** TruLens provides feedback functions such as groundedness NLI, sentiment, language match, and moderation.

**Expected Evidence Spans**

- TruLens provides feedback functions such as groundedness NLI, sentiment, language match, moderation, and more.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 90: `holdout_dspy_signatures_supported`

- Source family: `dspy.ai`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://dspy.ai/

**Query:** How does DSPy express tasks?

**Answer:** DSPy lets you express tasks as structured signatures, not prompts.

**Expected Evidence Spans**

- DSPy is a Python framework for building AI systems. It lets you express tasks as structured signatures, not prompts.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 91: `holdout_dspy_assertions_supported`

- Source family: `dspy.ai`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://dspy.ai/faqs/

**Query:** What can DSPy Assert and Suggest define?

**Answer:** DSPy Assert and Suggest can define constraints within a DSPy program.

**Expected Evidence Spans**

- Use dspy.Assert and dspy.Suggest to define constraints within your DSPy program.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 92: `holdout_dspy_optimizers_partial_dns`

- Source family: `github.com`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://github.com/stanfordnlp/dspy

**Query:** What can DSPy optimize?

**Answer:** DSPy offers algorithms for optimizing prompts and weights. It provisions Kubernetes load balancers.

**Expected Evidence Spans**

- DSPy offers algorithms for optimizing prompts and weights for modular AI systems.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 93: `holdout_dspy_prompts_contradicted`

- Source family: `dspy.ai`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://dspy.ai/

**Query:** Does DSPy require tasks to be expressed as hand-written prompts?

**Answer:** DSPy requires tasks to be expressed only as hand-written prompts instead of structured signatures.

**Expected Evidence Spans**

- DSPy lets you express tasks as structured signatures, not prompts.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 94: `holdout_dspy_assertions_wrong_source_citation`

- Source family: `dspy.ai`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://dspy.ai/, https://dspy.ai/faqs/

**Query:** What can DSPy Assert and Suggest define?

**Answer:** DSPy Assert and Suggest can define constraints within a DSPy program.

**Expected Evidence Spans**

- Use dspy.Assert and dspy.Suggest to define constraints within your DSPy program.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 95: `holdout_lancedb_search_supported`

- Source family: `docs.lancedb.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.lancedb.com/

**Query:** What search modes does LanceDB support?

**Answer:** LanceDB supports vector search, full-text search, and hybrid search with secondary indexes.

**Expected Evidence Spans**

- LanceDB supports vector search, full-text search, and hybrid search with secondary indexes.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 96: `holdout_lancedb_full_text_filter_supported`

- Source family: `docs.lancedb.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.lancedb.com/search/full-text-search

**Query:** Can LanceDB full-text search use filters?

**Answer:** LanceDB full-text search supports filtering with pre-filtering and post-filtering using where syntax.

**Expected Evidence Spans**

- LanceDB full text search supports filtering search results by a condition. Both pre-filtering and post-filtering are supported using where syntax.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 97: `holdout_lancedb_vector_partial_encryption`

- Source family: `docs.lancedb.com`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://docs.lancedb.com/search/vector-search

**Query:** What does LanceDB vector-search postfiltering do?

**Answer:** LanceDB postfiltering searches the full dataset first and then applies metadata filters. It encrypts every vector automatically.

**Expected Evidence Spans**

- Use postfiltering to prioritize vector similarity by searching the full dataset first, then applying metadata filters to the top results.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 98: `holdout_lancedb_full_text_filter_contradicted`

- Source family: `docs.lancedb.com`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://docs.lancedb.com/search/full-text-search

**Query:** Can LanceDB full-text search use filters?

**Answer:** LanceDB full-text search cannot use filtering conditions.

**Expected Evidence Spans**

- LanceDB full text search supports filtering search results by a condition. Both pre-filtering and post-filtering are supported.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 99: `holdout_lancedb_full_text_wrong_source_citation`

- Source family: `docs.lancedb.com`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://docs.lancedb.com/search/full-text-search, https://docs.lancedb.com/search/vector-search

**Query:** Can LanceDB full-text search use filters?

**Answer:** LanceDB full-text search supports filtering with pre-filtering and post-filtering using where syntax.

**Expected Evidence Spans**

- LanceDB full text search supports filtering search results by a condition. Both pre-filtering and post-filtering are supported using where syntax.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 100: `holdout_elasticsearch_knn_supported`

- Source family: `elastic.co`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://www.elastic.co/docs/solutions/search/vector/knn

**Query:** What does Elasticsearch kNN search find?

**Answer:** Elasticsearch kNN search finds the k nearest vectors to a query vector using a similarity metric.

**Expected Evidence Spans**

- A k-nearest neighbor search finds the k nearest vectors to a query vector using a similarity metric such as cosine or L2 norm.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 101: `holdout_elasticsearch_semantic_supported`

- Source family: `elastic.co`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://www.elastic.co/docs/solutions/search/vector/knn

**Query:** What can Elasticsearch kNN retrieve results based on?

**Answer:** Elasticsearch kNN can retrieve results based on semantic meaning rather than exact keyword matches.

**Expected Evidence Spans**

- With Elasticsearch kNN search, you can retrieve results based on semantic meaning rather than exact keyword matches.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 102: `holdout_elasticsearch_knn_partial_mapping`

- Source family: `elastic.co`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://www.elastic.co/docs/solutions/search/vector/knn

**Query:** What is a common use case for Elasticsearch kNN?

**Answer:** Common use cases for Elasticsearch kNN vector similarity search include semantic text search. It rewrites index mappings automatically for every query.

**Expected Evidence Spans**

- Common use cases for kNN vector similarity search include semantic text search, image and video similarity, and recommendations.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 103: `holdout_elasticsearch_keyword_contradicted`

- Source family: `elastic.co`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://www.elastic.co/docs/solutions/search/vector/knn

**Query:** Does Elasticsearch kNN only support exact keyword matches?

**Answer:** Elasticsearch kNN search does not retrieve results based on semantic meaning.

**Expected Evidence Spans**

- With Elasticsearch kNN search, you can retrieve results based on semantic meaning rather than exact keyword matches.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 104: `holdout_elasticsearch_knn_wrong_source_citation`

- Source family: `elastic.co`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://www.elastic.co/docs/solutions/search/vector/knn, https://www.elastic.co/search-labs/blog/hybrid-search-elasticsearch

**Query:** What does Elasticsearch kNN search find?

**Answer:** Elasticsearch kNN search finds the k nearest vectors to a query vector using a similarity metric.

**Expected Evidence Spans**

- A k-nearest neighbor search finds the k nearest vectors to a query vector using a similarity metric such as cosine or L2 norm.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 105: `holdout_redis_vector_concepts_supported`

- Source family: `redis.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://redis.io/docs/latest/develop/ai/search-and-query/vectors/

**Query:** What vector query strategies does Redis support?

**Answer:** Redis supports k-nearest neighbor, vector range queries, and metadata filters for vector fields.

**Expected Evidence Spans**

- Redis supports advanced querying strategies with vector fields including k-nearest neighbor, vector range queries, and metadata filters.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 106: `holdout_redis_ft_search_knn_supported`

- Source family: `redis.io`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://redis.io/docs/latest/develop/ai/search-and-query/query/vector-search/

**Query:** What does a Redis FT.SEARCH KNN query include?

**Answer:** A Redis FT.SEARCH KNN query includes the number of nearest neighbors, the vector field name, and the vector binary representation.

**Expected Evidence Spans**

- For KNN, FT.SEARCH needs the number of nearest neighbors, the vector field name, and the vector's binary representation.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 107: `holdout_redis_vector_partial_training`

- Source family: `redis.io`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://redis.io/docs/latest/develop/ai/search-and-query/vectors/

**Query:** What filtering can Redis vector search use?

**Answer:** Redis supports advanced querying strategies with vector fields including metadata filters. It provisions Kubernetes load balancers.

**Expected Evidence Spans**

- Redis supports advanced querying strategies with vector fields including k-nearest neighbor, vector range queries, and metadata filters.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 108: `holdout_redis_knn_contradicted`

- Source family: `redis.io`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://redis.io/docs/latest/develop/ai/search-and-query/vectors/

**Query:** Does Redis support KNN vector queries?

**Answer:** Redis vector fields do not include k-nearest neighbor queries.

**Expected Evidence Spans**

- Redis supports advanced querying strategies with vector fields including k-nearest neighbor, vector range queries, and metadata filters.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 109: `holdout_redis_ft_search_wrong_source_citation`

- Source family: `redis.io`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://redis.io/docs/latest/develop/ai/search-and-query/query/vector-search/, https://redis.io/docs/latest/develop/ai/search-and-query/vectors/

**Query:** What does a Redis FT.SEARCH KNN query include?

**Answer:** A Redis FT.SEARCH KNN query includes the number of nearest neighbors, the vector field name, and the vector binary representation.

**Expected Evidence Spans**

- For KNN, FT.SEARCH needs the number of nearest neighbors, the vector field name, and the vector's binary representation.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 110: `holdout_pgvector_exact_supported`

- Source family: `github.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://github.com/pgvector/pgvector

**Query:** What search does pgvector perform by default?

**Answer:** By default, pgvector performs exact nearest neighbor search with perfect recall.

**Expected Evidence Spans**

- By default, pgvector performs exact nearest neighbor search, which provides perfect recall.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 111: `holdout_pgvector_hnsw_supported`

- Source family: `github.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://github.com/pgvector/pgvector/blob/master/README.md

**Query:** What are pgvector HNSW index tradeoffs?

**Answer:** A pgvector HNSW index creates a multilayer graph and has better query performance than IVFFlat, but slower build times and more memory use.

**Expected Evidence Spans**

- An HNSW index creates a multilayer graph. It has better query performance than IVFFlat, but has slower build times and uses more memory.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 112: `holdout_pgvector_ivfflat_partial_encryption`

- Source family: `github.com`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://github.com/pgvector/pgvector

**Query:** How does pgvector IVFFlat work?

**Answer:** A pgvector IVFFlat index divides vectors into lists and searches a subset of those lists. It encrypts embeddings automatically.

**Expected Evidence Spans**

- An IVFFlat index divides vectors into lists, and then searches a subset of those lists that are closest to the query vector.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 113: `holdout_pgvector_exact_contradicted`

- Source family: `github.com`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://github.com/pgvector/pgvector

**Query:** Does pgvector perform exact nearest neighbor search by default?

**Answer:** pgvector cannot perform exact nearest neighbor search by default.

**Expected Evidence Spans**

- By default, pgvector performs exact nearest neighbor search, which provides perfect recall.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 114: `holdout_pgvector_hnsw_wrong_source_citation`

- Source family: `github.com`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://github.com/pgvector/pgvector, https://github.com/pgvector/pgvector/blob/master/README.md

**Query:** What does a pgvector HNSW index create?

**Answer:** A pgvector HNSW index creates a multilayer graph.

**Expected Evidence Spans**

- An HNSW index creates a multilayer graph.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 115: `holdout_opensearch_knn_supported`

- Source family: `docs.opensearch.org`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.opensearch.org/latest/vector-search/vector-search-techniques/index/

**Query:** What does OpenSearch k-NN search find?

**Answer:** OpenSearch k-NN search finds the k neighbors closest to a query point across an index of vectors.

**Expected Evidence Spans**

- OpenSearch implements vector search as k-nearest neighbors, or k-NN, search. k-NN search finds the k neighbors closest to a query point across an index of vectors.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 116: `holdout_opensearch_filtering_supported`

- Source family: `docs.opensearch.org`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.opensearch.org/latest/vector-search/filter-search-knn/index/

**Query:** How does efficient OpenSearch k-NN filtering work?

**Answer:** Efficient OpenSearch k-NN filtering applies filtering during vector search.

**Expected Evidence Spans**

- Efficient k-nearest neighbors filtering applies filtering during the vector search, as opposed to before or after the vector search.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 117: `holdout_opensearch_approx_partial_sql`

- Source family: `docs.opensearch.org`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://docs.opensearch.org/latest/vector-search/vector-search-techniques/approximate-knn/

**Query:** What is needed to use OpenSearch approximate k-NN?

**Answer:** To use OpenSearch approximate search, create a vector index with index.knn set to true. It provisions Kubernetes load balancers.

**Expected Evidence Spans**

- To use approximate search, create a vector index with index.knn set to true. This setting tells OpenSearch to create native library indexes for the index.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 118: `holdout_opensearch_knn_contradicted`

- Source family: `docs.opensearch.org`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://docs.opensearch.org/latest/vector-search/vector-search-techniques/index/

**Query:** Is OpenSearch vector search implemented as k-NN search?

**Answer:** OpenSearch vector search is not k-nearest neighbor search.

**Expected Evidence Spans**

- OpenSearch implements vector search as k-nearest neighbors, or k-NN, search.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 119: `holdout_opensearch_filter_wrong_source_citation`

- Source family: `docs.opensearch.org`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://docs.opensearch.org/latest/vector-search/filter-search-knn/index/, https://docs.opensearch.org/latest/vector-search/vector-search-techniques/index/

**Query:** How does efficient OpenSearch k-NN filtering work?

**Answer:** Efficient OpenSearch k-NN filtering applies filtering during vector search.

**Expected Evidence Spans**

- Efficient k-nearest neighbors filtering applies filtering during the vector search, as opposed to before or after the vector search.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 120: `holdout_mongodb_vector_overview_supported`

- Source family: `mongodb.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://www.mongodb.com/docs/vector-search/

**Query:** What can MongoDB Vector Search combine?

**Answer:** MongoDB Vector Search can combine vector search with full-text search and filters on collection fields.

**Expected Evidence Spans**

- MongoDB Vector Search enables you to query data based on semantic meaning, combine vector search with full-text search, and filter your queries on other fields in your collection.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 121: `holdout_mongodb_vector_filter_supported`

- Source family: `mongodb.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://www.mongodb.com/docs/vector-search/query/aggregation-stages/vector-search-stage/

**Query:** Can MongoDB vector search use $and in a filter?

**Answer:** MongoDB vector search can use the $and MQL operator to specify an array of filters in one query.

**Expected Evidence Spans**

- You can use the $and MQL operator to specify an array of filters in a single query.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 122: `holdout_mongodb_vector_partial_external_service`

- Source family: `mongodb.com`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://www.mongodb.com/docs/vector-search/

**Query:** What can MongoDB Vector Search filter on?

**Answer:** MongoDB Vector Search can filter queries on fields in a collection. It stores vectors only in a separate non-MongoDB service.

**Expected Evidence Spans**

- MongoDB Vector Search enables you to search and index vector data alongside your other MongoDB data and filter queries on other fields in your collection.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 123: `holdout_mongodb_full_text_contradicted`

- Source family: `mongodb.com`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://www.mongodb.com/docs/vector-search/

**Query:** Can MongoDB Vector Search combine vector search with full-text search?

**Answer:** MongoDB Vector Search cannot combine vector search with full-text search.

**Expected Evidence Spans**

- MongoDB Vector Search enables you to combine vector search with full-text search.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 124: `holdout_mongodb_filter_wrong_source_citation`

- Source family: `mongodb.com`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://www.mongodb.com/docs/vector-search/, https://www.mongodb.com/docs/vector-search/query/aggregation-stages/vector-search-stage/

**Query:** Can MongoDB vector search use $and in a filter?

**Answer:** MongoDB vector search can use the $and MQL operator to specify an array of filters in one query.

**Expected Evidence Spans**

- You can use the $and MQL operator to specify an array of filters in a single query.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 125: `holdout_azure_hybrid_search_supported`

- Source family: `learn.microsoft.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview

**Query:** What does Azure AI Search hybrid search combine?

**Answer:** Azure AI Search hybrid search combines vector and full-text queries in a single request.

**Expected Evidence Spans**

- Hybrid search in Azure AI Search combines vector and full-text queries in a single request for more relevant results.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 126: `holdout_azure_rrf_supported`

- Source family: `learn.microsoft.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://learn.microsoft.com/en-us/azure/search/hybrid-search-how-to-query

**Query:** How does Azure AI Search combine hybrid results?

**Answer:** The results are merged and reordered using Reciprocal Rank Fusion.

**Expected Evidence Spans**

- Hybrid search combines text and vector queries in a single search request. The results are merged and reordered using Reciprocal Rank Fusion.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 127: `holdout_azure_hybrid_partial_redis`

- Source family: `learn.microsoft.com`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview

**Query:** What capabilities can Azure AI Search hybrid queries use?

**Answer:** Azure AI Search hybrid queries can use filtering, faceting, sorting, scoring profiles, and semantic ranking. They store embeddings in Redis automatically.

**Expected Evidence Spans**

- Hybrid queries can take advantage of text-based functionality like filtering, faceting, sorting, scoring profiles, and semantic ranking while executing similarity search against vectors.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 128: `holdout_azure_parallel_contradicted`

- Source family: `learn.microsoft.com`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview

**Query:** How does Azure AI Search run full-text and vector search in hybrid search?

**Answer:** Azure AI Search hybrid search does not run full-text search and vector search in parallel.

**Expected Evidence Spans**

- Hybrid search runs full-text search and vector search in parallel and merges results from each query by using Reciprocal Rank Fusion.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 129: `holdout_azure_rrf_wrong_source_citation`

- Source family: `learn.microsoft.com`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://learn.microsoft.com/en-us/azure/search/hybrid-search-how-to-query, https://learn.microsoft.com/en-us/azure/search/search-get-started-vector

**Query:** How does Azure AI Search combine hybrid results?

**Answer:** Azure AI Search hybrid search merges and reorders text and vector results using Reciprocal Rank Fusion.

**Expected Evidence Spans**

- Hybrid search combines text and vector queries in a single search request. The results are merged and reordered using Reciprocal Rank Fusion.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 130: `holdout_vespa_hybrid_supported`

- Source family: `docs.vespa.ai`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.vespa.ai/en/learn/tutorials/hybrid-search.html

**Query:** What approaches does the Vespa hybrid-search tutorial combine?

**Answer:** The Vespa hybrid-search tutorial combines lexical and embedding-based approaches.

**Expected Evidence Spans**

- This tutorial demonstrates building a hybrid search application with Vespa that leverages both lexical and embedding-based approaches.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 131: `holdout_vespa_nearest_neighbor_supported`

- Source family: `docs.vespa.ai`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://docs.vespa.ai/en/querying/nearest-neighbor-search-guide.html

**Query:** What does the Vespa nearest-neighbor search guide cover?

**Answer:** The Vespa nearest-neighbor search guide covers using the nearest neighbor operator and combining it with other query operators.

**Expected Evidence Spans**

- The guide introduces using Vespa nearest neighbor search query operator and how to combine nearest neighbor search with other Vespa query operators.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 132: `holdout_vespa_candidate_partial_exact`

- Source family: `docs.vespa.ai`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://docs.vespa.ai/en/querying/nearest-neighbor-search-guide.html

**Query:** What can Vespa candidate retrievers be used in?

**Answer:** Vespa candidate retrievers can be used in a multiphase ranking funnel. They always run only exact search.

**Expected Evidence Spans**

- The guide covers diverse, efficient candidate retrievers that can be used as candidate retrievers in a multiphase ranking funnel.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 133: `holdout_vespa_hybrid_contradicted`

- Source family: `docs.vespa.ai`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://docs.vespa.ai/en/learn/tutorials/hybrid-search.html

**Query:** Does Vespa hybrid search use only lexical search?

**Answer:** Vespa hybrid search does not leverage both lexical and embedding-based approaches.

**Expected Evidence Spans**

- This tutorial demonstrates building a hybrid search application with Vespa that leverages both lexical and embedding-based approaches.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 134: `holdout_vespa_nearest_wrong_source_citation`

- Source family: `docs.vespa.ai`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://docs.vespa.ai/en/learn/tutorials/hybrid-search.html, https://docs.vespa.ai/en/querying/nearest-neighbor-search-guide.html

**Query:** What does the Vespa nearest-neighbor search guide cover?

**Answer:** The Vespa nearest-neighbor search guide covers using the nearest neighbor operator and combining it with other query operators.

**Expected Evidence Spans**

- The guide introduces using Vespa nearest neighbor search query operator and how to combine nearest neighbor search with other Vespa query operators.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 135: `holdout_openai_evals_supported`

- Source family: `developers.openai.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://developers.openai.com/api/docs/guides/evals

**Query:** What do OpenAI evals test?

**Answer:** OpenAI evals test model outputs against style and content criteria that you specify.

**Expected Evidence Spans**

- Evaluations, often called evals, test model outputs to ensure they meet style and content criteria that you specify.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 136: `holdout_openai_graders_supported`

- Source family: `developers.openai.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://developers.openai.com/api/docs/guides/graders

**Query:** What are OpenAI graders used for?

**Answer:** OpenAI graders evaluate model performance against reference answers.

**Expected Evidence Spans**

- Graders are a way to evaluate your model's performance against reference answers.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 137: `holdout_openai_evals_partial_deploy`

- Source family: `developers.openai.com`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://developers.openai.com/api/docs/guides/evals

**Query:** What do OpenAI evals help with?

**Answer:** OpenAI evals help you understand how LLM applications perform against expectations. They deploy applications to Kubernetes automatically.

**Expected Evidence Spans**

- Writing evals helps you understand how your LLM applications are performing against your expectations, especially when upgrading or trying new models.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 138: `holdout_openai_variability_contradicted`

- Source family: `developers.openai.com`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://developers.openai.com/api/docs/guides/evaluation-best-practices

**Query:** Why are evals useful for generative AI systems?

**Answer:** Generative AI is not variable.

**Expected Evidence Spans**

- Generative AI is variable. Evaluations are a way to test your AI system despite this variability.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 139: `holdout_openai_graders_wrong_source_citation`

- Source family: `developers.openai.com`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://developers.openai.com/api/docs/guides/evals, https://developers.openai.com/api/docs/guides/graders

**Query:** What are OpenAI graders used for?

**Answer:** OpenAI graders evaluate model performance against reference answers.

**Expected Evidence Spans**

- Graders are a way to evaluate your model's performance against reference answers.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 140: `holdout_guardrails_io_guards_supported`

- Source family: `github.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://github.com/guardrails-ai/guardrails

**Query:** What do Guardrails input and output guards do?

**Answer:** Guardrails input and output guards detect, quantify, and mitigate specific risks.

**Expected Evidence Spans**

- Guardrails runs Input and Output Guards in your application that detect, quantify, and mitigate specific types of risks.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 141: `holdout_guardrails_validators_supported`

- Source family: `guardrailsai.com`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://guardrailsai.com/guardrails/docs/concepts/validators

**Query:** What can custom Guardrails validators do?

**Answer:** Custom Guardrails validators can extend Guardrails beyond the Hub.

**Expected Evidence Spans**

- Custom validators can extend the ability of Guardrails beyond the hub.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 142: `holdout_guardrails_structured_partial_runtime`

- Source family: `github.com`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://github.com/guardrails-ai/guardrails

**Query:** What else does Guardrails help generate?

**Answer:** Guardrails helps generate structured data from LLMs. It replaces all model calls with deterministic code.

**Expected Evidence Spans**

- Guardrails helps you generate structured data from LLMs.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 143: `holdout_guardrails_io_contradicted`

- Source family: `github.com`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://github.com/guardrails-ai/guardrails

**Query:** Can Guardrails run input and output guards?

**Answer:** Guardrails cannot run input or output guards.

**Expected Evidence Spans**

- Guardrails runs Input and Output Guards in your application.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 144: `holdout_guardrails_validators_wrong_source_citation`

- Source family: `guardrailsai.com`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://github.com/guardrails-ai/guardrails, https://guardrailsai.com/guardrails/docs/concepts/validators

**Query:** What can custom Guardrails validators do?

**Answer:** Custom Guardrails validators can extend Guardrails beyond the Hub.

**Expected Evidence Spans**

- Custom validators can extend the ability of Guardrails beyond the hub.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 145: `holdout_llamaindex_observability_supported`

- Source family: `developers.llamaindex.ai`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://developers.llamaindex.ai/python/framework/module_guides/observability/

**Query:** What does LlamaIndex observability help developers build?

**Answer:** LlamaIndex observability helps developers build principled LLM applications in production settings.

**Expected Evidence Spans**

- LlamaIndex provides one-click observability to allow you to build principled LLM applications in a production setting.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 146: `holdout_llamaindex_evaluation_supported`

- Source family: `developers.llamaindex.ai`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`
- Benchmark pass: `True`
- Source URLs: https://developers.llamaindex.ai/python/framework/optimizing/evaluation/evaluation/

**Query:** Why does LlamaIndex discuss evaluation?

**Answer:** LlamaIndex evaluation provides tools for identifying issues and receiving useful diagnostic signals.

**Expected Evidence Spans**

- LlamaIndex aims to provide tools to make identifying issues and receiving useful diagnostic signals easy.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 147: `holdout_llamaindex_observability_partial_sqlite`

- Source family: `developers.llamaindex.ai`
- Expected labels: `partial_support`
- Expected root cause: `answer_overreach`
- Benchmark pass: `True`
- Source URLs: https://developers.llamaindex.ai/python/framework/understanding/tracing_and_debugging/tracing_and_debugging/

**Query:** What can LlamaIndex observability integrate with?

**Answer:** LlamaIndex observability can integrate with partner observability and evaluation tools. It stores traces only in SQLite.

**Expected Evidence Spans**

- LlamaIndex observability lets you integrate with observability and evaluation tools offered by partners.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 148: `holdout_llamaindex_debug_contradicted`

- Source family: `developers.llamaindex.ai`
- Expected labels: `contradicted_answer`, `should_have_abstained`
- Expected root cause: `conflicting_contexts`
- Benchmark pass: `True`
- Source URLs: https://developers.llamaindex.ai/python/framework/understanding/tracing_and_debugging/tracing_and_debugging/

**Query:** Can LlamaIndex observability help debug and evaluate components?

**Answer:** LlamaIndex observability cannot help debug or evaluate components.

**Expected Evidence Spans**

- LlamaIndex observability lets you observe, debug, and evaluate your system as a whole and for each component.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 149: `holdout_llamaindex_evaluation_wrong_source_citation`

- Source family: `developers.llamaindex.ai`
- Expected labels: `citation_mismatch`
- Expected root cause: `wrong_source_cited`
- Benchmark pass: `True`
- Source URLs: https://developers.llamaindex.ai/python/framework/module_guides/observability/, https://developers.llamaindex.ai/python/framework/optimizing/evaluation/evaluation/

**Query:** Why does LlamaIndex discuss evaluation?

**Answer:** LlamaIndex evaluation provides tools for identifying issues and receiving useful diagnostic signals.

**Expected Evidence Spans**

- LlamaIndex aims to provide tools to make identifying issues and receiving useful diagnostic signals easy.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

### Case 150: `holdout_no_context_should_abstain`

- Source family: `public docs holdout empty retrieval`
- Expected labels: `should_have_abstained`, `unsupported_answer`
- Expected root cause: `should_have_abstained`
- Benchmark pass: `True`
- Source URLs: `missing`

**Query:** What does Weaviate hybrid search combine?

**Answer:** Weaviate hybrid search combines vector search with keyword BM25F search and fuses both result sets.

**Expected Evidence Spans**

- No expected evidence span recorded.

**Reviewer Signoff**

- [ ] Source URL opens
- [ ] Context excerpt is fair to source
- [ ] Expected labels are correct
- [ ] Evidence span is minimal and sufficient
- Reviewer:
- Reviewed at:
- Notes:

