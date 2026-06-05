# Regression Suite Validation Story

This is the intended v0.7.0 workflow: turn a saved RAG failure into a local regression case and keep replaying it until the evidence chain is fixed.

## Failure

The saved trace in `examples/suite/refund_processing_failure.json` contains this answer:

```text
Refunds are processed within 5 business days.
```

The retrieved context only says customers may request refunds within 30 days. It does not mention processing time, so ContextTrace marks the claim unsupported and says the answer should have abstained.

## Add The Failure To A Suite

```bash
contexttrace suite create examples/suite/refund_processing_failure.json \
  --name refund-suite \
  --out .contexttrace/suites/refund-suite.json
```

For later failures, add them without rebuilding the whole suite:

```bash
contexttrace suite add .contexttrace/suites/refund-suite.json traces/new_failure.json
contexttrace suite list .contexttrace/suites/refund-suite.json
```

## Replay Against The Current Endpoint

```bash
contexttrace suite run .contexttrace/suites/refund-suite.json \
  --endpoint http://localhost:8000/query \
  --report \
  --fail-on failed_case \
  --fail-on error
```

If the endpoint still returns an unsupported processing-time claim, the suite fails. If the endpoint retrieves context that states the processing time, the case passes and the report shows a resolved failure.

## Keep The Suite Useful

Remove cases manually when they no longer represent useful risk:

```bash
contexttrace suite remove .contexttrace/suites/refund-suite.json refund_processing_failure
```

Or prune fixed cases from a saved run result:

```bash
contexttrace suite prune .contexttrace/suites/refund-suite.json \
  --results .contexttrace/suites/refund-suite_results.json \
  --status passed
```

The practical loop is:

```text
capture failure -> add to suite -> fix RAG -> replay endpoint -> keep CI gate
```
