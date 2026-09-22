# Non-overlapping sentence-extension results

## Scope

This extension tests whether the 15-case findings persist on substantially more
RAGTruth material. It deterministically projects upstream human answer-side
hallucination spans onto sentence units, then excludes every sentence ID used by
the earlier development or held-out experiments.

The frozen extension contains:

- 39 development cases: 13 supported, 13 partially supported, 13 contradicted;
- 72 held-out cases: 24 supported, 24 partially supported, 24 contradicted;
- zero overlap with the earlier 30 evaluated cases;
- zero overlap between extension development and held-out;
- identical selected claim-evidence inputs across compared systems.

This is stronger external coverage, but it is not independent claim-level
annotation. RAGTruth has no `unverifiable` class, and this extension contains no
`unsupported` class. Five-way macro F1 over all five ContextTrace labels would
therefore understate performance; observed-label macro F1 is reported alongside
fixed-label metrics in the raw artifact.

## Five-way results

| Split | System | Accuracy | Observed-label macro F1 | Incorrect supported | Supported false alarms |
|---|---|---:|---:|---:|---:|
| Development (39) | Jev | 0.6667 | 0.7205 | 3/26 | 3/13 |
| Development (39) | Stable semantic | 0.2308 | 0.3053 | 1/26 | 10/13 |
| Development (39) | Local deterministic | 0.1538 | 0.2105 | 2/26 | 12/13 |
| Development (39) | Local + NLI | 0.1282 | 0.1656 | 1/26 | 12/13 |
| Held-out (72) | Jev | **0.7500** | **0.7668** | 4/48 | 4/24 |
| Held-out (72) | Stable semantic | 0.3056 | 0.4078 | 1/48 | 16/24 |
| Held-out (72) | Local deterministic | 0.1250 | 0.1895 | 3/48 | 19/24 |
| Held-out (72) | Local + NLI | 0.1250 | 0.1826 | 3/48 | 19/24 |

On held-out, Jev is correct on 37 cases that the stable verifier misses, while
the stable verifier is uniquely correct on five. The exploratory exact McNemar
test is `p = 0.00000044` for five-way correctness.

## Binary grounding projection

The binary projection treats only `supported` as positive and groups every
other verdict as `not_supported`.

| Split | System | Accuracy | 95% Wilson CI | Supported recall | False-support rate |
|---|---|---:|---:|---:|---:|
| Development (39) | Jev | 0.8462 | [0.7027, 0.9275] | 0.7692 | 0.1154 |
| Development (39) | MiniCheck RoBERTa | 0.7179 | [0.5622, 0.8346] | 0.5385 | 0.1923 |
| Development (39) | Stable semantic | 0.7179 | [0.5622, 0.8346] | 0.2308 | 0.0385 |
| Held-out (72) | Jev | **0.8889** | [0.7958, 0.9426] | **0.8333** | 0.0833 (4/48) |
| Held-out (72) | MiniCheck RoBERTa | 0.7361 | [0.6242, 0.8241] | 0.7917 | 0.2917 (14/48) |
| Held-out (72) | Stable semantic | 0.7639 | [0.6540, 0.8470] | 0.3333 | **0.0208 (1/48)** |

On held-out binary correctness, Jev is uniquely correct on 13 cases versus two
for MiniCheck (`p = 0.00738525`) and uniquely correct on 13 versus four for the
stable verifier (`p = 0.04904175`). These exact paired tests are exploratory,
uncorrected for multiple comparisons, and do not account for source-response
clustering.

## Decision

The extension changes the earlier conclusion. It provides credible evidence for
an **experimental, explicitly opt-in JevJudge**, because Jev generalizes to the
non-overlapping held-out extension and materially improves both five-way and
binary correctness. It does not justify making Jev the default:

- four of 48 held-out negative claims are incorrectly marked supported;
- labels are projected rather than independently assigned at claim level;
- source-side evidence spans are not independently mapped;
- remote inference must remain disabled under `local_only`;
- confidence calibration and review policy require a new untouched set.

The safe implementation target is therefore an optional remote provider that
preserves the stable default, sends only selected evidence, exposes complete
probabilities and resolved model identity, and routes low-confidence or
`supported` decisions to review. Threshold or policy tuning must use a new
development set and a new untouched evaluation split, not this held-out set.

The subsequent development-only cascade calibration and retrospective frozen
held-out replay are reported in [CASCADE_RESULTS.md](CASCADE_RESULTS.md). The
cascade reduces held-out false support from 4/48 to 1/48 and raises binary
accuracy from 0.8889 to 0.9167, but saves only 3/72 Jev calls. Because the
held-out outcomes were already inspected before the cascade study, that replay
is useful design evidence rather than a new confirmatory result.
