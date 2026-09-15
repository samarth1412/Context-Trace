# A grounded answer backed by an expired policy

This is a **constructed, fictional product investigation**. It uses no customer data and is separate from ContextTrace's research evaluation cases.

## Reproduce

```bash
contexttrace verify examples/investigations/stale-but-supported/broken.json --json
contexttrace verify examples/investigations/stale-but-supported/fixed.json --json
python examples/investigations/run.py --case stale-but-supported
```

The question is: **What is the current Acme Transit cancellation window?** The broken trace is expected to expose `grounded_but_stale`. The runner checks exact summary fields from `regression.json`, so a changed result exits nonzero.

## What happened

The retriever selected an archived but lexically perfect policy, so ordinary groundedness looked healthy. The broken artifact preserves the query, generated answer, selected chunks, citation mapping, and lifecycle metadata needed to reproduce the diagnosis locally.

## Fix

Filter inactive documents before ranking and preserve lifecycle metadata on every selected chunk. The repaired output is captured in `fixed.json`; it must satisfy every fixed assertion before this investigation is considered closed.

## Regression guard

Require a canonical current source for operational queries and keep the broken trace as a source-condition regression. Run all six public cases with:

```bash
python examples/investigations/run.py --all --json-out .contexttrace/investigation-results.json
```

Start with the [five-minute quickstart](../../../README.md#quickstart), then use `contexttrace diagnose` or `contexttrace repair` on your own trace when the failing field is known.
