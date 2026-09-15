# A retriever upgrade removes the only supporting chunk

This is a **constructed, fictional product investigation**. It uses no customer data and is separate from ContextTrace's research evaluation cases.

## Reproduce

```bash
contexttrace verify examples/investigations/retrieval-regression/broken.json --json
contexttrace verify examples/investigations/retrieval-regression/fixed.json --json
python examples/investigations/run.py --case retrieval-regression
```

The question is: **What is the Vega rollback target?** The broken trace is expected to expose `regression`. The runner checks exact summary fields from `regression.json`, so a changed result exits nonzero.

## What happened

The new embedding model ranked a retention document over the rollback runbook. The broken artifact preserves the query, generated answer, selected chunks, citation mapping, and lifecycle metadata needed to reproduce the diagnosis locally.

## Fix

Restore the runbook namespace boost and compare selected context IDs before deployment. The repaired output is captured in `fixed.json`; it must satisfy every fixed assertion before this investigation is considered closed.

## Regression guard

Use the passing trace as baseline and reject a current trace whose support rate falls. Run all six public cases with:

```bash
python examples/investigations/run.py --all --json-out .contexttrace/investigation-results.json
```

Start with the [five-minute quickstart](../../../README.md#quickstart), then use `contexttrace diagnose` or `contexttrace repair` on your own trace when the failing field is known.
