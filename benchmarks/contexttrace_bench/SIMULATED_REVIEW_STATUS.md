# Simulated review status

Status: `simulated_pilots_complete_human_review_pending`.

These are controlled LLM-simulated pilots, not independent human review.

- Model: `gpt-4.1-nano-2025-04-14`
- Completed tasks: `1410/1410`
- Parse failures: `0`
- Estimated API cost: `$0.296`
- Suggested corrections: `214`
- Applied corrections: `0`

| Pilot | Cases | Unanimous | Disagreement | Frozen-label disagreement | Fleiss kappa |
| --- | ---: | ---: | ---: | ---: | ---: |
| ragtruth | 200 | 58 | 142 | 137 | 0.033 |
| diag150 | 150 | 121 | 29 | 77 | 0.679 |

## RQ4 simulated settings

| Setting | Root cause | Fix proxy | Actionability | False green |
| --- | ---: | ---: | ---: | ---: |
| raw_trace | 0.067 | 0.008 | 3.767 | 0.625 |
| score_only | 0.117 | 0.017 | 3.608 | 0.550 |
| contexttrace | 0.908 | 0.342 | 3.333 | 0.400 |

Registered positive RQ4 proxy claim supported: `False`.

Report these outputs only as controlled LLM-simulated pilots. They do not replace independent human review and cannot support broad SOTA language.
