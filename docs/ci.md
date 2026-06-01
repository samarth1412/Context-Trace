# CI And GitHub Actions

ContextTrace can fail pull requests when local RAG quality regresses.

## Composite Action

Use the bundled action:

```yaml
- uses: ./.github/actions/contexttrace-rag-eval
  with:
    dataset_path: datasets/demo/refund_policy
    fail_on: |
      failure_rate>0.25
      citation_support<0.80
    report_path: .contexttrace/reports/contexttrace-rag-eval.html
```

For endpoint mode:

```yaml
- uses: ./.github/actions/contexttrace-rag-eval
  with:
    dataset_path: evals/questions.json
    endpoint_url: http://localhost:8000/query
    fail_on: |
      failure_rate>0.25
      unsupported_claim_rate>0.15
```

## Outputs

The action exposes:

- `questions_tested`
- `reliability_score`
- `failure_rate`
- `citation_support`
- `unsupported_claim_rate`
- `report_path`

It also uploads the HTML report as an artifact and writes a GitHub markdown summary with pass/fail status.

No hosted dashboard or backend is required.
