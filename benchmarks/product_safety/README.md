# ContextTrace product-safety development baseline

This benchmark is the repeatable engineering loop for the v1.2 safety branch. It
does not replace CAIN, the sealed gold labels, or a future untouched evaluation.

It combines:

- ten controlled fixtures for expected support, source-condition, citation,
  abstention, failure-label, and root-cause behavior; and
- the existing 150-case public holdout, which is now treated as visible
  development data.

The runner uses `deterministic_only_v2`. An `unresolved` route therefore measures
the claims that would need the selective local-NLI stage, without downloading a
model or making a model call.

Run it from the repository root:

```bash
.venv/bin/python benchmarks/product_safety/run_baseline.py \
  --output benchmarks/product_safety/baseline-semantic-core-v2.json
```

Add `--enforce` only after the v1.2 targets have been reached. Before then, a
missed target is expected to produce a useful baseline rather than block the
measurement command.

The dangerous-false-green metric is case-level: an unsafe case is one whose
visible development label expects abstention, contradiction, unsupported, or
unverifiable; it is a false green if any claim in that case is green. The
abstention metric checks whether the verifier emits `must_abstain`, independently
of whether the answer itself abstained.
