# Reliability Score

ContextTrace includes a practical diagnostic reliability score to make trace reports and eval summaries easier to scan.

It is not a scientific benchmark and should not replace the underlying metrics. Treat it as a triage signal that points you toward the traces and projects most worth reviewing.

## Output

```json
{
  "score": 78,
  "grade": "B",
  "strengths": ["Citations are usually supported by the cited evidence."],
  "weaknesses": ["Unsupported claims are present at a noticeable rate."],
  "recommendations": ["Review low-support citations and improve source selection."],
  "components": {
    "citation_support": 82,
    "unsupported_claim_rate": 88,
    "failure_rate": 75
  }
}
```

`score` is an integer from 0 to 100. Grades are:

```text
A: 90-100
B: 75-89
C: 60-74
D: 45-59
F: 0-44
```

## Components

The scorer uses the metrics that are available for the trace or eval summary:

- `citation_support`: higher is better.
- `unsupported_claim_rate`: lower is better.
- `failure_rate`: lower is better.
- `retrieval_quality`: optional, based on logged relevance scores when available.
- `abstention_quality`: optional, currently used when the failure analyzer reports `should_have_abstained`.
- `token_efficiency`: optional, based on logged `total_tokens`.

Unavailable optional components are skipped rather than treated as zero. This avoids penalizing older traces that did not log relevance scores or token usage.

## Weights

Default weights are intentionally simple:

| Component | Weight |
| --- | ---: |
| Citation support | 35% |
| Unsupported claim rate | 25% |
| Failure rate | 25% |
| Retrieval quality | 10% |
| Abstention quality | 10% |
| Token efficiency | 5% |

Weights are normalized across the metrics present in a given score.

## Where It Appears

The score is included in:

- trace evaluation responses
- local HTML reports
- eval-set summaries
- CLI batch eval markdown reports
- dashboard summary cards and trace detail views

The raw metrics remain visible next to the score so teams can see why the diagnostic changed.
