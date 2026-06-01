# Bring Your Own RAG API

ContextTrace can test an existing RAG endpoint without installing the SDK into that application. You register the endpoint, define how to send a query, map its response fields, then run one-off tests or an eval set.

## Endpoint Shape

Example external endpoint:

```text
POST https://my-rag-app.com/query
```

Configuration:

```json
{
  "name": "support-api",
  "url": "https://my-rag-app.com/query",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer ..."
  },
  "body_template": {
    "question": "{{query}}"
  },
  "response_mapping": {
    "answer": "$.answer",
    "citations": "$.sources",
    "retrieved_chunks": "$.contexts"
  }
}
```

`body_template` supports `{{query}}`, `{{expected_answer}}`, and `{{metadata.key}}` string substitution.

## Response Mapping

Mappings use a small JSONPath-style syntax:

```text
$.answer
$.contexts
$.sources[0].text
$.sources[*].id
```

Retrieved chunks can be strings or objects with fields such as:

```json
{
  "id": "chunk_1",
  "content": "Refunds are available within 30 days.",
  "source": "policy.md",
  "score": 0.94
}
```

Citations can include `claim` plus `source_chunk_id`, `chunk_id`, `id`, or `source_id`. If a citation does not include a claim, ContextTrace uses the mapped answer as the claim so the answer can still be checked against the cited chunk.

## API Usage

Register an endpoint for a project:

```bash
curl -X POST http://localhost:8000/v1/projects/{project_id}/external-endpoints \
  -H "Authorization: Bearer ctx_test" \
  -H "Content-Type: application/json" \
  -d @endpoint.json
```

Run a test query:

```bash
curl -X POST http://localhost:8000/v1/external-endpoints/{endpoint_id}/test \
  -H "Authorization: Bearer ctx_test" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the refund policy?"}'
```

Run an eval set through the endpoint:

```bash
curl -X POST http://localhost:8000/v1/external-endpoints/{endpoint_id}/run-eval \
  -H "Authorization: Bearer ctx_test" \
  -H "Content-Type: application/json" \
  -d '{"eval_set_id":"eval_set_id"}'
```

ContextTrace creates traces from the mapped external response and evaluates citation support and failure type during eval runs.

## SDK Usage

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

## Local-First CLI

For the local-first workflow, prefer the CLI:

```bash
contexttrace eval \
  --dataset evals/questions.json \
  --endpoint http://localhost:8000/query \
  --answer-path $.answer \
  --contexts-path $.contexts \
  --citations-path $.citations
```

The CLI stores traces in `.contexttrace/contexttrace.db` and writes an HTML report under `.contexttrace/reports/`.
