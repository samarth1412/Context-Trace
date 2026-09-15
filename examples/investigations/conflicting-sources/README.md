# Two retrieved runbooks disagree

This is a **constructed, fictional product investigation**. It uses no customer data and is separate from ContextTrace's research evaluation cases.

## Reproduce

```bash
contexttrace verify examples/investigations/conflicting-sources/broken.json --json
contexttrace verify examples/investigations/conflicting-sources/fixed.json --json
python examples/investigations/run.py --case conflicting-sources
```

The question is: **How many reviewers must approve a current Atlas production deploy?** The broken trace is expected to expose `grounded_but_conflicted`. The runner checks exact summary fields from `regression.json`, so a changed result exits nonzero.

## What happened

Two teams published contradictory runbooks without canonical ownership or precedence metadata. The broken artifact preserves the query, generated answer, selected chunks, citation mapping, and lifecycle metadata needed to reproduce the diagnosis locally.

## Fix

Assign one canonical runbook, retire the competing instruction, and reindex both source records. The repaired output is captured in `fixed.json`; it must satisfy every fixed assertion before this investigation is considered closed.

## Regression guard

Reject current operational answers while retrieved sources still contain unresolved disagreement. Run all six public cases with:

```bash
python examples/investigations/run.py --all --json-out .contexttrace/investigation-results.json
```

Start with the [five-minute quickstart](../../../README.md#quickstart), then use `contexttrace diagnose` or `contexttrace repair` on your own trace when the failing field is known.
