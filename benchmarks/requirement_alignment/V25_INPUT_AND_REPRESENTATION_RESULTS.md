# V25: input integrity and joint claim–evidence representations

V25 found a benchmark input defect and a promising development improvement.
It does not establish release readiness, held-out performance, or SOTA.
Protocol and source hashes were committed in `24af5e8` before scoring.

## Input audit

The V21 adapter serializes AVeriTeC QA records as question/answer text, then
the shared evidence selector splits and ranks sentence fragments. This can
select a question while dropping its answer. Upstream labels remain attached
to the resulting fragments, even when they no longer contain the facts needed
to reproduce the upstream judgment.

Of 400 AVeriTeC cases:

- 822 of 1,843 selected spans contain only the question portion.
- 181 cases have a selected question without a non-question span from that QA record.
- 32 cases contain only question portions: 11 supported, 8 contradicted,
  10 unsupported, and 3 unverifiable according to inherited labels.

These are structural flags, not automatic replacement labels. They show that
previous results mix evidence-selection errors, upstream-label alignment, and
verifier errors. All 100 partially-supported cases also come from WiCE, so
source style remains correlated with that class.
The restored QA answers are upstream annotations, not newly retrieved raw
documents. Public-checkpoint pretraining overlap is also unknown. Neither
limitation is resolved by the input repair.

The research repair restores the complete QA record for each already-selected
source record. It verifies exact source offsets, deduplicates selected QA roots,
and introduces no unselected QA records. WiCE evidence and every target label
remain unchanged. Questions, answers, and existing Boolean explanations are
copied from the pinned source, never generated. The repair expands evidence
within selected records; it is an input ablation, not a same-input model gain.

## Frozen experiment

Each of two input variants uses the same frozen local DeBERTa encoder,
768-dimensional joint evidence/claim CLS representation, and one logistic
regression configuration (`C=0.1`, balanced classes, standardized features).
Five-fold stratified out-of-fold predictions feed the unchanged policy grid.
There is no encoder fine-tuning or classifier hyperparameter search.
Policy thresholds are selected using these same out-of-fold development
predictions, so policy metrics remain selection-biased and require independent
confirmation after a valid candidate is frozen.

The existing stable benchmark adapter receives exactly the same selected
claim/evidence as the candidate within each variant. This compares claim-level
verification, not the complete trace/debugging product. Labels enter supervised
head training and evaluation only, not encoder inputs. The adapter's stable
score is not a five-class probability distribution; none is invented.

| System / input | Accuracy | Macro-F1 | Support recall | False-support rate | Contradiction false supports | Review recall | Review rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Stable / original | 21.0% | 0.2035 | 22% | 14.0% | 18 | 48.0% | 47.4% |
| V25 direct / original | 52.0% | 0.5213 | 50% | 14.0% | 15 | 67.5% | 40.4% |
| V25 safe policy / original | 46.6% | 0.4417 | 7% | 0.25% | 0 | 73.5% | 49.0% |
| Stable / restored QA | 22.4% | 0.2171 | 29% | 19.0% | 25 | 44.5% | 41.8% |
| V25 direct / restored QA | 58.2% | 0.5840 | 59% | 10.25% | 7 | 71.5% | 40.0% |
| V25 safe policy / restored QA | 52.6% | 0.5012 | 11% | 0.25% | 0 | 78.0% | 49.4% |

The repaired input raises direct accuracy by 6.2 percentage points and
macro-F1 by 0.0627 within V25. The safe policy still misses support recall
(11% versus 50%) and review recall (78% versus 80%). Gates are shown as
diagnostics against inherited labels, not validated release measurements.

On original inputs the selected candidate disagrees with the baseline on 390
cases. Its one false support is `averitec_train_0595`, inherited unsupported,
which the baseline calls unverifiable. With restored QA, there are 384
disagreements. The candidate's one false support is `averitec_train_2998`,
inherited unverifiable, which the baseline also calls supported. Raw text is
kept outside Git; these IDs locate the inspectable evidence in the local pack.

Encoding took 31.87 seconds for original inputs and 51.69 seconds for restored
QA. At the fixed 512-token limit, 1 original and 15 restored cases were
truncated. The totals processed were 73,654 and 92,338 input tokens; there are
no generated tokens, remote calls, or API charges. These are batch encoding
times, not production end-to-end request latency. Every row records token
counts; the report pins the model revision and full file-hash identity.

## Decision and correction to earlier conclusions

Do not promote, consume fresh confirmation data, or publish this candidate.
Review verdict alignment against the displayed selected evidence first.
The earlier V22–V24 conclusion that the feature family was exhausted was too
strong: those runs did not isolate the input defect. Their recorded metrics
remain reproducible, but are insufficient to attribute failure solely to the
model or estimate product quality. V19 uses the same QA selection pattern and
also needs that qualification; this does not turn its failed candidate into
a passing one.

The next work item is the prepared development annotation review, followed by
one preregistered rerun if the revised data justify it. The current cases are
consumed development data permanently, regardless of relabeling. Final release
still requires a separately frozen, valid confirmation set. Stable provider
selection, `local_only`, and runtime behavior were not changed.

## Reproduce

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v25_input_audit \
  --dataset /private/tmp/contexttrace_external_data/v21_development.json \
  --averitec-train /private/tmp/contexttrace_external_data/v19_sources/averitec_train.json \
  --dataset-output /private/tmp/contexttrace_external_data/v25_qa_development.json \
  --audit-output benchmarks/requirement_alignment/results/v25_input_audit.json

PYTHONPATH=packages/contexttrace:. HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv/bin/python -m benchmarks.requirement_alignment.v25_joint_representation \
  --original /private/tmp/contexttrace_external_data/v21_development.json \
  --restored /private/tmp/contexttrace_external_data/v25_qa_development.json \
  --protocol benchmarks/requirement_alignment/results/v25_protocol.json \
  --model-path /path/to/pinned/DeBERTa-v3-base-mnli-fever-anli \
  --model-manifest benchmarks/requirement_alignment/results/v23_stronger_nli_manifest.json \
  --output benchmarks/requirement_alignment/results/v25_joint_representation.json
```

The externally stored `v25_blinded_review.json` has 500 input-bound cases with
opaque IDs, no source IDs, no inherited verdicts, and no model predictions.
Source text styles may still reveal the source. `v25_review_key.json` is kept
separate. Export refuses to overwrite an existing pack or key. Fill verdict,
rationale, and reviewer for each case using the included definitions, then run:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v25_review validate \
  --review /private/tmp/contexttrace_external_data/v25_blinded_review.json \
  --key /private/tmp/contexttrace_external_data/v25_review_key.json \
  --output /private/tmp/contexttrace_external_data/v25_review_result.json
```

The validator checks coverage and input identity, not semantic correctness or
reviewer independence. Its output cannot authorize release.
