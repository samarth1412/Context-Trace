# Jev v2 results

## Outcome

The original 15-case held-out result was unstable, but a subsequently frozen,
non-overlapping 72-case extension changes the conclusion. Jev reaches 75.00%
five-way accuracy and 0.7668 observed-label macro F1 on that extension. Its
binary projection reaches 88.89% accuracy, compared with 76.39% for the stable
verifier and 73.61% for MiniCheck RoBERTa.

The result identifies two distinct research problems:

1. ContextTrace's current local semantic judgment path does not transfer from
   short policy claims to abstractive RAGTruth sentences.
2. Jev is a strong experimental semantic judge on the larger extension, but
   its false-support risk and projected labels still preclude default use.

## Non-overlapping extension

The extension excludes all 30 sentence IDs used in the original experiment.
It contains 39 balanced development cases and 72 balanced held-out cases, with
equal supported, partially supported, and contradicted representation.

Held-out five-way results:

| System | Accuracy | Observed-label macro F1 | Incorrect supported | Supported false alarms |
|---|---:|---:|---:|---:|
| Jev | **75.00%** | **0.7668** | 4/48 | 4/24 |
| Stable semantic | 30.56% | 0.4078 | **1/48** | 16/24 |
| Local deterministic | 12.50% | 0.1895 | 3/48 | 19/24 |
| Local + NLI | 12.50% | 0.1826 | 3/48 | 19/24 |

Held-out binary results:

| System | Accuracy | Supported recall | False-support rate |
|---|---:|---:|---:|
| Jev | **88.89%** | **83.33%** | 8.33% |
| Stable semantic | 76.39% | 33.33% | **2.08%** |
| MiniCheck RoBERTa | 73.61% | 79.17% | 29.17% |

The exploratory exact McNemar p-values are 0.00738525 for Jev versus MiniCheck
binary correctness, 0.04904175 for Jev versus stable binary correctness, and
0.00000044 for Jev versus stable five-way correctness. See
`EXTENSION_RESULTS.md` and `results/ragtruth_sentence_extension_analysis.json`
for confidence intervals, development results, and explicit limitations.

## Protocol

- Source: the repository's frozen RAGTruth dev and test case packs.
- Units: five each of supported, partially supported, and contradicted sentence
  projections per split.
- Split: upstream response IDs are disjoint between development and held-out.
- Shared input: identical claim and up to eight locally selected evidence spans
  for every system.
- Jev question: one five-way Choice using the existing ContextTrace label
  definitions.
- Model request: `jev-latest`; resolved model: `jev-1.13.0`.
- Development was run first. The prompt and criteria were unchanged for the
  one-shot held-out run.
- Review threshold: selected on development only from 0.50–0.95, requiring at
  least 60% automatic coverage. The selected threshold was 0.50.

The labels are deterministic sentence projections from upstream human
answer-side spans. They are stronger than newly authored synthetic labels, but
they are not independently annotated claim labels. Inspection found at least
one projected conflict sentence that is close to verbatim source text, so label
noise is material.

## Results

Development, 15 cases:

| System | Accuracy | Macro F1 on observed labels | Incorrect supported | False alarms on supported | Review rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stable semantic | 20.00% | 0.2897 | 0/10 | 4/5 | 80.00% |
| Local deterministic | 13.33% | 0.1905 | 1/10 | 4/5 | 33.33% |
| Local deterministic + NLI | 6.67% | 0.0952 | 0/10 | 5/5 | 40.00% |
| Jev | **80.00%** | **0.8241** | 2/10 | 0/5 | 20.00% at the pre-calibration 0.60 threshold |

Held-out, 15 cases, using the development-selected 0.50 threshold:

| System | Accuracy | Macro F1 on observed labels | Incorrect supported | False alarms on supported | Review rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stable semantic | 20.00% | 0.3016 | 0/10 | 4/5 | 46.67% |
| Local deterministic | 13.33% | 0.1481 | 0/10 | 5/5 | 20.00% |
| Local deterministic + NLI | 13.33% | 0.1481 | 0/10 | 5/5 | 20.00% |
| Jev | **40.00%** | **0.4273** | **0/10** | 4/5 | **0.00%** |

Jev used 30,030 tokens on development and 37,022 on held-out. Held-out mean
request latency was 267.232 ms, p50 was 213.733 ms, and p95 was 519.302 ms.
Its held-out multiclass Brier score was 0.896800 and top-label ECE was 0.436000;
the small projected sample makes both estimates noisy. Raw probabilities are not
presented as probabilities that the final verdict is correct.

## Error interpretation

On held-out, Jev produced no dangerous supported verdicts. Four of five truly
supported projected sentences were instead labeled unsupported or partially
supported. It also reduced four of five projected contradictions to partial or
unsupported. This suggests that selected evidence often establishes relevance
without making the precise sentence-level relationship easy to classify.

The local NLI backend did not improve this track. Its transfer failure is
consistent with using a small sentence-pair NLI model on long, noisy retrieved
passages and abstractive claims. The next local experiment should compare a
grounding-specific verifier such as MiniCheck or AlignScore, and should evaluate
the selector separately from the semantic judge.

The development threshold did not transfer: every held-out Jev top probability
was at least 0.50, so no case was reviewed despite 60% error. Confidence gating
therefore needs a larger calibration set and risk-coverage analysis before any
automatic action.

## Evidence-availability diagnostic

The next planned diagnostic is complete. RAGTruth has no human source-side
evidence mappings, so this is deliberately named a complete-source-availability
ablation rather than an oracle-evidence experiment. The comparison exposes
either the shared selector's top eight spans or every deterministic source span.
The local-quality verifier retains its own internal selection in both
conditions. No Jev request was made.

Development, 15 cases:

| System | Selected accuracy | Complete-source accuracy | Recoveries | Regressions |
| --- | ---: | ---: | ---: | ---: |
| Stable semantic | 20.00% | 20.00% | 0 | 0 |
| Local deterministic | 13.33% | 13.33% | 0 | 0 |
| Local deterministic + NLI | 6.67% | 6.67% | 0 | 0 |

Post-hoc held-out diagnosis, 15 cases:

| System | Selected accuracy | Complete-source accuracy | Recoveries | Regressions |
| --- | ---: | ---: | ---: | ---: |
| Stable semantic | 20.00% | 26.67% | 2 | 1 |
| Local deterministic | 13.33% | 13.33% | 0 | 0 |
| Local deterministic + NLI | 13.33% | 13.33% | 0 | 0 |

The local-quality variants had no verdict changes or correctness recoveries on
either split. Their internal selectors received the same ordered span texts in
10/15 development cases and 12/15 held-out cases; the remaining span-sequence
changes still produced identical verdicts. The stable semantic verifier changed
seven held-out verdicts, but the net gain was only one case and introduced two
incorrect `supported` predictions among ten non-supported examples.

This evidence weakens the hypothesis that the top-eight preselection cap is the
main failure on this sample. It does not prove retrieval is solved: the complete
source condition still uses each verifier's internal scoring, and projected
labels are noisy. The strongest measured problem is now semantic judgment under
abstractive claims, followed by the lack of independently mapped claim-level
evidence and labels.

## Decision

The frozen stable-plus-Jev cascade improves the extension's retrospective
held-out replay to 76.39% five-way accuracy and 91.67% binary accuracy while
reducing false support from 4/48 to 1/48. It retains 79.17% supported recall,
down from Jev's 83.33%, and saves only three of 72 remote calls. See
`CASCADE_RESULTS.md` and the content-hashed `results/cascade_policy.json`.

This supports the cascade as an experimental safety policy, not as a mature
cost router. The policy was selected programmatically from development only,
but the held-out Jev results existed and were inspected before this follow-up;
the replay is not a pristine new confirmation.

The extension justifies implementing Jev as an experimental, explicitly opt-in
provider. It does not justify changing ContextTrace's stable default. The
provider must preserve `local_only`, transmit only selected evidence, expose
complete probabilities and resolved model identity, and require review for
risk-sensitive supported decisions. Independent claim labels and source-side
evidence mappings remain necessary before a production recommendation.

Any production-oriented Jev design should replace the single five-way Choice with independently
useful typed judgments for support coverage, direct conflict, and evidence
sufficiency, compose the final label in code, and evaluate it on a newly frozen
split. The current held-out set must not be reused to tune that design.

## MiniCheck grounding baseline

The official MiniCheck-RoBERTa-Large binary baseline ran offline on the same
selected claim-evidence inputs at its published 0.5 threshold. The verified
checkpoint produced 0.8000 development accuracy and 0.7847 binary macro F1,
then 0.7333 held-out accuracy and 0.5833 macro F1. Development had two false
support decisions among ten negative cases. Held-out had zero false support,
but rejected four of five supported claims.

On development, MiniCheck uniquely corrected three stable-verifier mistakes
and lost two cases the stable verifier got right. On held-out, its binary
decisions matched both the stable verifier and Jev on all 15 cases, so it adds
no held-out binary coverage. This supports MiniCheck as a reproducible research
baseline, not a runtime provider. Full probabilities, input tokens, latency,
hashed used chunks, exact model identity, and disagreement rows are recorded in
the two `results/*_minicheck_roberta.json` artifacts. The stronger 3.1 GB Flan
checkpoint remains pinned but unexecuted.

## Validation

The final working tree passed all 978 collected tests. Ruff, targeted whitespace
checks, the artifact-manifest hashes, and the no-label-leak input audit
passed. The two Jev runs resolved to `jev-1.13.0`, and the MiniCheck runs used
the exact pinned revision above. No explanation, evidence span, or matched fact
was synthesized from either model's outputs.
