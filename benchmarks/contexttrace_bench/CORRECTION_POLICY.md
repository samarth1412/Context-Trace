# Correction policy

1. Human-reviewed corrections override author labels after validation and documented adjudication.
2. Without human review, a simulated-agent majority creates only a `suggested_correction`.
3. If all three simulated agents agree and the frozen label disagrees, mark `high_priority_author_review`.
4. If two agents agree and one disagrees, mark `medium_priority_author_review`.
5. If no label receives two votes, mark the case `ambiguous`.
6. Never silently change a frozen label.
7. Every suggested correction records the old label, suggested label, evidence span, rationale, votes, and application state.

Simulated-only defaults are:

```text
applied = false
status = suggested_for_author_review
```

Simulated suggestions may be used for a separately labeled sensitivity analysis.
They cannot satisfy independent-review, paper-result, or broad-SOTA gates.
