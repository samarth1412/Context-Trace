# Bring Your Own RAG Endpoint

ContextTrace can capture and evaluate an existing RAG API without adding SDK
code to that service.

## Capture One Response

```bash
contexttrace capture endpoint \
  --endpoint http://localhost:8000/query \
  --query "What is the refund policy?" \
  --method POST \
  --input-key question \
  --answer-path $.answer \
  --contexts-path $.contexts \
  --citations-path $.citations \
  --out traces/refund_trace.json \
  --verify \
  --report
```

The resulting portable trace can be rerun with:

```bash
contexttrace verify traces/refund_trace.json
```

Capture a saved endpoint response without making a network request:

```bash
contexttrace capture response response.json \
  --query "What is the refund policy?" \
  --answer-path $.answer \
  --contexts-path $.contexts \
  --citations-path $.citations \
  --out traces/refund_trace.json \
  --verify \
  --report
```

## Evaluate A Dataset

```bash
contexttrace eval \
  --dataset evals/questions.json \
  --endpoint http://localhost:8000/query \
  --method POST \
  --input-key question \
  --answer-path $.answer \
  --contexts-path $.contexts \
  --citations-path $.citations
```

Dataset rows can include expected answers and sources:

```json
[
  {
    "id": "q1",
    "query": "What is the refund policy?",
    "expected_answer": "Refunds are available within 30 days.",
    "expected_sources": ["refund_policy.md"]
  }
]
```

For custom request bodies, use `{{query}}`, `{{expected_answer}}`, or
`{{metadata.key}}` substitutions:

```bash
contexttrace eval \
  --dataset evals/questions.json \
  --endpoint http://localhost:8000/query \
  --body-template '{"messages":[{"role":"user","content":"{{query}}"}]}' \
  --answer-path $.response.answer \
  --contexts-path $.response.contexts \
  --endpoint-header "Authorization: Bearer local-token"
```

## Response Mapping

Mappings support dotted fields, numeric indexes, and list projections:

```text
$.answer
$.contexts
$.sources[0].text
$.sources[*].id
```

Retrieved contexts may be strings or objects with IDs, content, source names,
scores, and metadata. Citations may identify a source through
`source_chunk_id`, `chunk_id`, `id`, or `source_id`.

## Hosted API And SDK

When running the optional ContextTrace API, register reusable endpoint
configurations at:

```text
POST /v1/projects/{project_id}/external-endpoints
POST /v1/external-endpoints/{endpoint_id}/test
POST /v1/external-endpoints/{endpoint_id}/run-eval
```

The SDK exposes the same operations:

```python
from contexttrace import ContextTrace

ct = ContextTrace(api_key="ctx_test", project="support-rag")
endpoint = ct.register_rag_endpoint(
    project_id="project_id",
    name="support-api",
    url="https://my-rag-app.com/query",
    headers={"Authorization": "Bearer ..."},
    body_template={"question": "{{query}}"},
    response_mapping={
        "answer": "$.answer",
        "citations": "$.sources",
        "retrieved_chunks": "$.contexts",
    },
)

test = ct.test_rag_endpoint(endpoint["id"], query="What is the refund policy?")
run = ct.evaluate_rag_endpoint(endpoint["id"], eval_set_id="eval_set_id")
```

CLI runs store local state under `.contexttrace/`; reports and databases are
ignored by Git by default.
