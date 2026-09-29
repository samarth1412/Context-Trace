# Support and review recall: diagnosis and two controlled repair attempts

The current candidate has a support-discrimination problem that its safety
policy compensates for by rejecting most supported cases. Review misses are
concentrated in ambiguous evidence. Two bounded repair attempts did not produce
a qualifying candidate. Keep the stable verifier and release status unchanged.

These findings concern the research candidate on the consumed 500-case
development set, with inherited targets still under review. They are not
production accuracy measurements, validated replacement labels, or SOTA evidence.

## Where support recall is lost

The repaired-input V25 classifier directly identifies 59 of 100 inherited
supported cases. The policy retains 11 and rejects 48 of those 59. Another
41 supported targets are already missed by the classifier before routing.
None of the 100 supported-target inputs was truncated, so the 512-token limit
does not explain this support-recall loss on this set.

The selected support threshold is 0.95. Why so high? Three inherited
contradictions score above 0.92 for support:

| Case | Support score | Contradiction score |
|---|---:|---:|
| averitec_train_0348 | 0.94079 | 0.00802 |
| averitec_train_1305 | 0.93647 | 0.00264 |
| averitec_train_2345 | 0.92009 | 0.02426 |

Lowering the support threshold to 0.50 alone recovers 51 supported targets,
but also accepts 34 non-supported targets, including six contradictions.
At 0.90 it still accepts three contradictions. The unchanged zero-contradiction
gate therefore forces conservative decisions. A high softmax score is not a
reliable correctness guarantee here.

The old risk grid starts at 0.20, too coarse to distinguish the low contradiction
scores above. Its fallback objective maximizes macro-F1 among safety-eligible
policies, rather than explicitly maximizing both recalls under a review budget.
These are testable routing limitations, but V26 shows they are not the main
repair opportunity on these scores.

## Where review recall is lost

The policy reviews 91/100 partially supported targets and only 65/100
unverifiable targets. Their pooled recall is 156/200, or 78%.
Of the 44 missed review targets, 35 are unverifiable and nine partially
supported. They are routed to contradicted (25), unsupported (18), or supported
(one). Uncertainty is often treated as a definite rejection.

There are already 247 reviews among 500 cases. Reaching 80% requires four more
correct reviews, but the 50% budget has only three spare slots. A useful repair
must also remove unnecessary reviews. All partially supported examples come
from WiCE, while the other classes come from AVeriTeC; the apparent difference
between partial and ambiguous performance is confounded with source style.

## Checks against already-reviewed examples

These examples were examined only after their proposals were frozen. The
proposals remain model-assisted and unapproved; agreement with an inherited
label does not create independent ground truth.

- `review-0097` / `averitec_train_1305` is one high-confidence false-support
  candidate. The evidence distinguishes the virus on disinfectant labels from
  the new virus; it does not establish prior corporate knowledge. Its provisional
  proposal is unsupported rather than the inherited contradicted label. Both
  reject full support, so that particular proposed relabeling would not excuse
  the model's 0.936 support score.
- `review-0020` / `averitec_train_1700` has a supported proposal agreeing with
  the inherited target, but its 0.930 support score is rejected by the 0.95 gate.
  This illustrates policy suppression rather than a low support score.
- `review-0026` / `averitec_train_2464` has a matching unverifiable proposal:
  supplied counts are explicitly disputed or undated. The classifier instead
  assigns 0.827 to unsupported. That is an ambiguity-versus-insufficiency
  distinction that a generic confidence cutoff does not reliably recover.
- `review-0028` / `averitec_train_2601` mixes different length measures and a
  prospective statement. Its matching unverifiable proposal also becomes
  unsupported, illustrating unresolved measurement/time scope.

No unreviewed case text was opened for this error inspection. No review proposal
was adopted as a training target or used to select either repair attempt.

## V26: bounded routing repair

Protocol commit `9895475` froze the grids before the new policies were scored.
V26 reuses the exact V25 OOF probabilities and labels. It tests lower risk caps,
absolute versus conditional non-support risk, and an explicit review threshold
on the combined partial/unverifiable mass. It evaluates 21,504 configurations
plus the original policy. It changes no evidence, model, label, or safety gate.
Conditional ratios are routing scores, not newly calibrated probabilities.

Selection requires the existing safety limits, review rate at most 50%, and
neither recall below its baseline. Within that set, it maximizes support recall,
then review recall, then favors fewer false supports and higher macro-F1.
A second selection also forbids increasing the false-support count.

| Diagnostic policy | Support recall | Review recall | False supports / 400 | Contradiction false supports | Review rate |
|---|---:|---:|---:|---:|---:|
| V25 baseline | 11% | 78% | 1 | 0 | 49.4% |
| V26 selected trade-off | 12% | 79.5% | 2 | 0 | 49.4% |
| V26 without additional false supports | 11% | 78% | 1 | 0 | 48.0% |

No policy passes all gates. The selected trade-off uses support minimum 0.50,
conditional contradiction cap 0.02, conditional review-risk cap 1.0, and review
threshold 0.45. It is not a safe improvement at the original false-support
count. The alternative removes seven reviews while retaining the same recalls,
but does not solve either recall target.

As a threshold-instability diagnostic, selecting on four folds and applying to
the fifth gives 14% support recall, 78.5% review recall, nine false supports,
and two contradiction false supports. This is **not independent validation**:
the reused OOF model fits have overlapping training labels. Even that limited
check warns against promoting the small selected gain.

## V27: preserve the pretrained NLI decision signal

V25 uses raw CLS features and discards the checkpoint's trained NLI pooler and
classification head. V27 tests whether preserving that signal helps: append
the three frozen entailment/neutral/contradiction logits to the 768 CLS features.
This is a hypothesis test, not a claim that using CLS was an implementation bug.

Protocol commit `aba69d3` froze exactly two variants: the original 768-feature
control and the 771-feature augmentation. Both use the same pinned local model,
selected evidence, original targets, five folds, standardized logistic model
with C=0.1, and unchanged V14 policy search. The model is not fine-tuned.

The control reproduces every V25 probability exactly (maximum absolute
difference 0.0). Augmentation changes probabilities by at most approximately
0.00507, but changes **zero direct or routed verdicts**. Both retain direct
macro-F1 0.5840, safe support recall 11%, and review recall 78%. This particular
feature addition is rejected; it does not establish that other representations
or supervised training cannot help.

Before this run, a frozen lexical audit flagged ten evidence records containing
obvious fact-check assessment wording. It is not an exhaustive semantic audit.
The input policy retains exact V25 text to isolate the feature change and
reports the contamination risk explicitly. Removing flagged rows from the
evaluation summary alone produces 490 rows with 11/96 supported recall and
153/197 review recall, identical across variants. This does not remove those
records from training, establish valid labels, or justify release claims.

Encoding both feature sets together took 49.71 seconds for 92,338 processed
tokens; 15 cases were truncated. This is batch encoding time, not product
request latency. Per-batch timing, token counts, full five-way probabilities,
raw NLI logits, resolved model revision, and input hashes are recorded. There
were no remote inference calls or changes to local-only controls.

## Repair decision

Do not promote either attempt or keep searching this threshold grid. The
measured bottlenecks are unsafe high support scores and confusion between
ambiguous evidence and definite rejection, with unresolved target validity.
The discarded-head hypothesis did not repair either bottleneck.

The next meaningful model change should follow adjudication of selected-evidence
targets and train explicitly on matched contrasts: full versus missing material
support, direct conflict versus conflicting/undated evidence, reported speech
versus truth of the embedded statement, and consistent versus mismatched
measurement scope. Include both supported and non-supported versions of each
contrast and split by source/claim family to prevent near-duplicate leakage.
Use the same existing verdict definitions. Owner adjudication preserves sole
ownership but must not be reported as independent annotation.

Freeze that development set and training recipe before fitting a local model.
Keep source verdict prose out of the new model inputs using a separately
versioned, source-bound input policy. Measure per-class review recall as well
as the pooled metric, and compare at the unchanged safety/review limits.
Only a qualifying, frozen candidate should consume untouched confirmation data.
These are actions within the existing data-quality and candidate checkpoints;
the release gates have not changed.

## Reproduce

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v26_routing_diagnosis \
  --source benchmarks/requirement_alignment/results/v25_joint_representation.json \
  --protocol benchmarks/requirement_alignment/results/v26_protocol.json \
  --output benchmarks/requirement_alignment/results/v26_routing_diagnosis.json

PYTHONPATH=packages/contexttrace:. HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv/bin/python -m benchmarks.requirement_alignment.v27_preserved_nli_signal \
  --dataset /private/tmp/contexttrace_external_data/v25_qa_development.json \
  --source benchmarks/requirement_alignment/results/v25_joint_representation.json \
  --protocol benchmarks/requirement_alignment/results/v27_protocol.json \
  --model-path /path/to/pinned/DeBERTa-v3-base-mnli-fever-anli \
  --model-manifest benchmarks/requirement_alignment/results/v23_stronger_nli_manifest.json \
  --output benchmarks/requirement_alignment/results/v27_preserved_nli_signal.json
```

V26 needs no text-bearing external dataset or model. V27 requires the preserved
development dataset and pinned local model files. Reports contain no raw claims,
evidence, or reviewer rationales. Focused tests verify routing edge cases,
metric equivalence, safety selection, frozen input bindings, and feature assembly.
