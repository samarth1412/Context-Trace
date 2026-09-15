# From a failed CI gate to a repaired trace

This is a **constructed, fictional product investigation**. It uses no customer data and is separate from ContextTrace's research evaluation cases.

## Reproduce

```bash
contexttrace verify examples/investigations/ci-debugging-walkthrough/broken.json --json
contexttrace verify examples/investigations/ci-debugging-walkthrough/fixed.json --json
python examples/investigations/run.py --case ci-debugging-walkthrough
```

The question is: **At what error rate does Nimbus page the on-call engineer?** The broken trace is expected to expose `contradicted_claim`. The runner checks exact summary fields from `regression.json`, so a changed result exits nonzero.

## What happened

A prompt example still contained the retired four-percent threshold. The broken artifact preserves the query, generated answer, selected chunks, citation mapping, and lifecycle metadata needed to reproduce the diagnosis locally.

## Fix

Remove the stale prompt fact and generate the value only from the selected runbook span. The repaired output is captured in `fixed.json`; it must satisfy every fixed assertion before this investigation is considered closed.

## Regression guard

Run the saved trace pair in CI and display the claim, evidence, cause, and fix when it fails. Run all six public cases with:

```bash
python examples/investigations/run.py --all --json-out .contexttrace/investigation-results.json
```

Start with the [five-minute quickstart](../../../README.md#quickstart), then use `contexttrace diagnose` or `contexttrace repair` on your own trace when the failing field is known.
