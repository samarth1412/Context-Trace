# ContextTrace-Unseen-v1 preregistration checklist

Complete and timestamp this file before unsealing labels.

- [ ] Unlabeled manifest URL and SHA-256 published.
- [ ] Calibration overlap report is empty for source document, normalized content,
  source family, domain, and publication window.
- [ ] `semantic_core_v2` commit and source archive SHA-256 recorded.
- [ ] Local NLI model name, immutable revision, local artifact hash, tokenizer
  revision, runtime, and numerical precision recorded.
- [ ] Deterministic/NLI routing thresholds and abstention thresholds frozen.
- [ ] Candidate output JSON Schema and taxonomy version frozen.
- [ ] Claim unitization and aggregation rules frozen.
- [ ] Bootstrap seed, confidence-interval method, and paired significance tests
  frozen.

Primary metrics are failure-label macro-F1, root-cause accuracy, unverifiable F1,
dangerous false-green rate, evidence-span token-F1 and character IoU, expected
calibration error, risk-coverage/AURC, p50/p95 latency, and NLI invocation rate.

Success gates are root-cause accuracy at least 0.75, unverifiable F1 at least
0.60, failure-label macro-F1 at least 0.15 absolute above
`semantic_v1_calibrated`, dangerous false-green rate at most 0.02, and NLI
invocation on fewer than 40% of claims. Report all metrics even if a gate fails.

The primary comparison is paired on identical traces. Bootstrap confidence
intervals resample source families, not individual claims, to avoid treating
correlated traces from one document as independent. The untouched test is scored
once; inspected errors are retired to future calibration data.
