# Regression Suite Example

Create a local suite from a saved failing trace:

```bash
contexttrace suite create examples/suite/refund_processing_failure.json \
  --out .contexttrace/suites/refund-suite.json
```

Replay it against a running RAG endpoint:

```bash
contexttrace suite run .contexttrace/suites/refund-suite.json \
  --endpoint http://localhost:8000/query \
  --report
```

The saved case expects the endpoint response to pass current evidence QA. If the endpoint still answers with unsupported refund-processing timing, the suite exits non-zero and the report explains the failing case.

Manage the suite as more failures are found or fixed:

```bash
contexttrace suite add .contexttrace/suites/refund-suite.json traces/new_failure.json
contexttrace suite list .contexttrace/suites/refund-suite.json
contexttrace suite remove .contexttrace/suites/refund-suite.json refund_processing_failure
contexttrace suite prune .contexttrace/suites/refund-suite.json --results .contexttrace/suites/refund-suite_results.json --status passed
```
