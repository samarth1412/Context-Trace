# Bring Your Own RAG Endpoint

Use ContextTrace to evaluate an existing RAG API without adding SDK code to that service.

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

Dataset format:

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

Endpoint response mapping uses a small JSONPath subset:

- `$.answer`
- `$.contexts`
- `$.citations`
- dotted fields such as `$.data.answer`
- numeric indexes such as `$.results[0].answer`

The evaluator will:

1. call your endpoint for each question
2. extract the answer, contexts, and citations
3. create local ContextTrace traces
4. run local citation/failure diagnostics
5. save traces in `.contexttrace/contexttrace.db`
6. generate an HTML eval report under `.contexttrace/reports/`

For custom request bodies, pass JSON with `{{query}}`:

```bash
contexttrace eval \
  --dataset evals/questions.json \
  --endpoint http://localhost:8000/query \
  --body-template '{"messages":[{"role":"user","content":"{{query}}"}]}' \
  --answer-path $.response.answer \
  --contexts-path $.response.contexts
```

Headers can be repeated:

```bash
contexttrace eval \
  --dataset evals/questions.json \
  --endpoint http://localhost:8000/query \
  --endpoint-header "Authorization: Bearer local-token"
```
