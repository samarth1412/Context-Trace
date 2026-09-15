# A correct sentence with the wrong citation

This is a **constructed, fictional product investigation**. It uses no customer data and is separate from ContextTrace's research evaluation cases.

## Reproduce

```bash
contexttrace verify examples/investigations/misleading-citation/broken.json --json
contexttrace verify examples/investigations/misleading-citation/fixed.json --json
python examples/investigations/run.py --case misleading-citation
```

The question is: **How long is the Northstar device warranty?** The broken trace is expected to expose `citation_mismatch`. The runner checks exact summary fields from `regression.json`, so a changed result exits nonzero.

## What happened

The answer generator used the right retrieved fact while the citation renderer attached the first result. The broken artifact preserves the query, generated answer, selected chunks, citation mapping, and lifecycle metadata needed to reproduce the diagnosis locally.

## Fix

Bind each emitted claim to the chunk that supports it after answer generation. The repaired output is captured in `fixed.json`; it must satisfy every fixed assertion before this investigation is considered closed.

## Regression guard

Fail CI when a supported claim cites a different source than its best evidence span. Run all six public cases with:

```bash
python examples/investigations/run.py --all --json-out .contexttrace/investigation-results.json
```

Start with the [five-minute quickstart](../../../README.md#quickstart), then use `contexttrace diagnose` or `contexttrace repair` on your own trace when the failing field is known.
