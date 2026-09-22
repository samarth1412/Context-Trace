# Local verification quality review report

## Decision

Keep `local_quality_v1_experimental` as an opt-in research path. The one-shot
synthetic held-out result supports a larger independently labeled evaluation,
but it is not enough to replace the stable default. Jev remains diagnostic only
and is not a dependency of this path.

## Pilot audit

The saved Jev artifacts confirm 8/10 correct for Jev and 3/10 for the stable
baseline. The baseline was the semantic `find_best_evidence` and
`classify_claim` path, not local NLI. The experiment selected spans first, gave
Jev the selected span list, then let the baseline select a single best span from
that list. The two systems therefore did not receive equivalent effective
evidence. Concatenating the selected spans did not repair the seven observed
baseline verdict errors, but the asymmetry limits the comparison.

The seven baseline failures were traced to these stages:

| Case | Gold / baseline | Responsible stage |
| --- | --- | --- |
| `dev_unsupported_refund_speed` | unsupported / unverifiable | Verdict policy did not map explicit absence of the asserted detail to unsupported. |
| `heldout_unsupported_backup_schedule` | unsupported / unverifiable | Span selection missed an explicit absence sentence because `backed` and `backup` were not aligned. |
| `dev_partial_refund_shipping` | partially supported / supported | Compound-claim decomposition failed; fuzzy whole-claim matching hid the unsupported addition. |
| `heldout_contradicted_remote_days` | contradicted / supported | Relation checks did not compare word-form numbers such as “three” and “two.” |
| `heldout_partial_travel_approval` | partially supported / contradicted | Decomposition failed and an over-broad legacy relation conflict dominated the mixed claim. |
| `dev_ambiguous_priority_support` | unverifiable / partially supported | Qualified evidence was over-interpreted instead of abstaining. |
| `heldout_ambiguous_beta_access` | unverifiable / partially supported | A universal claim over qualified evidence was over-interpreted instead of abstaining. |

Jev corrected the unsupported additions, partial-support cases, and held-out
number contradiction. Its two mistakes were the two ambiguous cases, which it
called contradicted. Those ten cases are debugging material, and Jev's answers
are not ground truth.

## Implementation

The explicit local path adds:

- conservative decomposition of coordinated predicates and required objects;
- exact span selection with provenance and topic normalization;
- word-number and unit-aware conflict checks;
- scoped semantic-negation, explicit-absence, exact-versus-approximate,
  universal-qualifier, and conflicting-evidence rules;
- the existing pinned `LocalNLIJudge` as an optional auxiliary signal;
- review and automatic-support fields, backend identity, atomic assessments,
  and separate support, truth, and source-condition output.

NLI thresholds of 0.70 entailment, 0.80 contradiction, and 0.70 neutral were
chosen on development data only. Raw NLI scores and the aggregate confidence are
not reported as calibrated correctness probabilities. The path performs no
network operation and contains no automatic download behavior.

## Fresh evaluation

Development and held-out files each have 15 synthetic author-labeled cases,
three per verdict. Scenario families are disjoint: development uses library,
clinic, cloud, warehouse, and conference cases; held-out uses education,
manufacturing, banking, transit, and agriculture cases. Expected labels, tags,
and evidence IDs are excluded from verifier inputs. The held-out file and scored
implementation were hashed before the first score.

No repository dataset qualifies as independent validation for this task. The
existing naturalistic holdout explicitly sets `independent_validation: false`,
and the CAIN research inventory records independent review as pending. The
results below must therefore remain labeled synthetic and author-labeled.

### One-shot held-out results

| Variant | Accuracy | Macro F1 | Incorrect supported | False alarms | Review rate | Auto-handled accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Stable semantic | 4/15 (26.67%) | 0.2133 | 5/12 | 1/3 | 40.00% | 33.33% |
| Decomposition only | 8/15 (53.33%) | 0.4234 | 2/12 | 1/3 | 0.00% | 53.33% |
| Relation rules only | 10/15 (66.67%) | 0.6000 | 1/12 | 1/3 | 20.00% | 58.33% |
| Decomposition + rules | 13/15 (86.67%) | 0.8667 | 1/12 | 1/3 | 20.00% | 83.33% |
| Decomposition + rules + local NLI | 14/15 (93.33%) | 0.9314 | 0/12 | 1/3 | 20.00% | 91.67% |

The full local path's per-label precision, recall, and F1 were:

| Label | Precision | Recall | F1 | Support |
| --- | ---: | ---: | ---: | ---: |
| supported | 1.0000 | 0.6667 | 0.8000 | 3 |
| partially_supported | 1.0000 | 1.0000 | 1.0000 | 3 |
| unsupported | 1.0000 | 1.0000 | 1.0000 | 3 |
| contradicted | 0.7500 | 1.0000 | 0.8571 | 3 |
| unverifiable | 1.0000 | 1.0000 | 1.0000 | 3 |

Context-level evidence localization was precision 1.0 and recall 1.0 on 16
labeled context selections. This set has simple, synthetic context boundaries,
so that figure should not be generalized to document-level retrieval.

The sole full-pipeline error was a supported banking claim with “within one
business day” versus evidence saying “no later than one business day.” The
semantic-negation rule incorrectly interpreted `no` as a contradiction. A
general parser fix now excludes comparative bounds such as `no later than`,
with a regression test. A post-hoc rerun reached 15/15; this is a regression
check, not untouched held-out evidence.

On development data, the stable path scored 5/15 with macro F1 0.3533 and six
incorrect-supported verdicts among 12 non-supported cases. The full local path
scored 15/15, had zero incorrect-supported decisions, and reviewed 4/15 cases.
These development figures are tuning evidence only.

## Runtime and artifact

The one-shot held-out run used macOS 26.6.2 on arm64, Python 3.14.6, PyTorch
2.13.0, four CPU threads, and CPU inference. MPS and CUDA were unavailable.

| Measurement | Stable semantic | Full local pipeline |
| --- | ---: | ---: |
| Warm latency p50 | 4.447 ms | 17.435 ms |
| Warm latency p95 | 6.438 ms | 65.274 ms |
| Model load + warmup | n/a | 2,818.095 ms |
| Peak RSS increase at initialization | n/a | 776.797 MB |

The artifact is `cross-encoder/nli-deberta-v3-small`, revision
`fa2804872c3b4bd748f38c0185cc85775361e735`, Transformers CPU float32, maximum
length 512. Its eight locked files total 578,732,649 bytes, and the pinned model
card declares Apache-2.0. Artifact manifest SHA-256 is
`330f0fd77aad129877e1a1a90d4a77e6f093ee238b97d535202816a116b9c9f3`.

## Limits and recommendation

The evaluation is small, English-only, synthetic, author-labeled, and has short
evidence passages. It does not measure long-context retrieval, adversarial
documents, domain shift, multilingual claims, calibration, or independently
reviewed production traffic. NLI adds roughly 579 MB of weights and a measured
peak RSS increase near 777 MB.

Adopt the path only as an optional experiment for offline users who explicitly
install and provision NLI. Before considering it for the default, freeze a
larger independently labeled corpus, calibrate review and NLI thresholds there,
measure long-document span localization, and define acceptable false-supported
and false-alarm gates. The current reduction from 5/12 to 0/12 incorrect
supported verdicts justifies that next evaluation; it does not establish SOTA
or general superiority.

## Validation performed

The following checks passed on the final working tree:

```text
451 passed in 11.74s
ruff: all checks passed
pinned NLI artifact: all eight hashes and manifest verified offline
frozen development, held-out, and result hashes: verified
```

The 451-test run covered the complete `packages/contexttrace/tests` suite plus
the local-quality benchmark integrity tests and the existing naturalistic
holdout tests. The first sandboxed run had six environment errors because local
HTTP fixtures could not bind to `127.0.0.1`; rerunning the identical suite with
loopback socket permission passed all 451 tests.

## Reproduction and review surface

Exact setup and offline commands are in [README.md](README.md). Primary review
files are:

- `packages/contexttrace/contexttrace/verify/local_quality.py`
- `packages/contexttrace/tests/test_local_quality.py`
- `benchmarks/local_verification_quality/run.py`
- `benchmarks/local_verification_quality/provision_model.py`
- `benchmarks/tests/test_local_verification_quality.py`
- the frozen case files, manifest, and three result JSON files in this directory
- `docs/local-quality-experimental.md`

The stable provider registry, stable runner defaults, package exports, version,
and release configuration were not changed for this experiment.
