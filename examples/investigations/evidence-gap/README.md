# The answer invents a detail absent from retrieval

This is a **constructed, fictional product investigation**. It uses no customer data and is separate from ContextTrace's research evaluation cases.

## Reproduce

```bash
contexttrace verify examples/investigations/evidence-gap/broken.json --json
contexttrace verify examples/investigations/evidence-gap/fixed.json --json
python examples/investigations/run.py --case evidence-gap
```

The question is: **How long are Bluebird support logs retained?** The broken trace is expected to expose `unsupported_claim`. The runner checks exact summary fields from `regression.json`, so a changed result exits nonzero.

## What happened

Retrieval found a topically related access-control page but no retention duration. The broken artifact preserves the query, generated answer, selected chunks, citation mapping, and lifecycle metadata needed to reproduce the diagnosis locally.

## Fix

Route retention questions to the policy namespace and abstain when the duration is absent. The repaired output is captured in `fixed.json`; it must satisfy every fixed assertion before this investigation is considered closed.

## Regression guard

Keep the missing-evidence trace and require zero unsupported claims before release. Run all six public cases with:

```bash
python examples/investigations/run.py --all --json-out .contexttrace/investigation-results.json
```

Start with the [five-minute quickstart](../../../README.md#quickstart), then use `contexttrace diagnose` or `contexttrace repair` on your own trace when the failing field is known.
