# V17 decomposition and multi-span completeness

V17 implements the targeted follow-up from the V16 support-failure audit. It
improves deterministic requirement construction, scores evidence combinations,
and tests a narrow rescue policy over the already-consumed V13 development
split. It does not access the V13 held-out split.

## Method

For each claim, V17 compares three existing local deterministic decomposers:

- the Semantic Core v2.1 atomic unitizer;
- the experimental local-quality material-claim decomposer; and
- the V15 atomic-coverage decomposer.

It chooses the most detailed valid decomposition and rejects candidates that
produce fragmentary requirements beginning with relative or coordinating
terms. This fixes cases where a relative clause such as one beginning with
“who” was previously scored without its antecedent, while also splitting
coordinated clauses that have independent subjects.

Each requirement selects at most four local evidence spans. The frozen V11 NLI
model scores every singleton, pair, and triple among those spans. The external
score artifact contains 145 requirements and 1,217 evidence combinations for
125 cases. It records hashes and probability distributions rather than claim,
requirement, or evidence text.

The V16 diagnosis fixed the rescue rule before this evaluation:

1. start from the selected V15 prediction;
2. retain all V15 supported predictions;
3. consider a promotion only when V14 already predicts `supported`; and
4. require the weakest V17 requirement to have single-span entailment of at
   least 0.70.

The 0.70 boundary is inherited from the existing atomic-coverage profile. It
was not selected using evaluation labels. Requiring V14's supported route keeps
its contradiction and ambiguity guards intact. A separate 80-candidate
out-of-fold classifier screen was retained as a diagnostic comparison.

## Development result

| Measure | V15 | V17 |
|---|---:|---:|
| Accuracy | 0.7040 | 0.7280 |
| Macro-F1 | 0.7005 | 0.7276 |
| Support recall | 0.4000 | 0.5200 |
| False-support rate | 0.0400 | 0.0400 |
| Contradiction false supports | 0 | 0 |
| Partial/ambiguous review recall | 0.8000 | 0.8000 |
| Review rate | 0.4800 | 0.4560 |

The targeted rule promoted three cases, all three of which are labeled
supported. Development promotion precision is therefore 100%. V17 passes all
five development gates for the first time.

The generic classifier screen did not pass all gates. Its best safe model
reached 0.7153 macro-F1 but remained at 40% support recall. This supports the
narrow, interpretable rescue rather than adding a larger learned fusion layer.

## Decision

Freeze V17 as a development candidate. It is not eligible for packaging or a
release claim yet: it reaches the support-recall gate exactly and must be tested
once on a newly frozen, untouched confirmation set. The consumed V13 held-out
set cannot be reused for that decision.

Stable verifier behavior remains unchanged. Scoring is fully local, sends only
selected evidence to the local model, makes zero network calls, and does not
enable any remote provider.
