# V13 independent contradiction transfer

V13 tests the frozen V11 relation model and its already-selected thresholds on
independent evidence domains. The resource uses public WiCE, VitaminC, and
AmbiEnt cases covering complete support, partial support, unsupported evidence,
direct contradiction, and linguistic ambiguity.

## Protocol

The development and held-out packs each contain 125 cases, balanced with 25
cases per ContextTrace verdict. Their case IDs, normalized claims, and exact
selected inputs are disjoint. V11 was trained and selected on SciFact and
Climate-FEVER; neither V13 split was used to train the model or choose its
thresholds.

The held-out manifest was written before V11 inference. The local scorer sent
only each claim and the evidence selected by the existing deterministic
selector. Evaluation labels and source metadata remained outside the model
input. Inference used the verified local V11 artifact with offline model loading
and made zero remote requests.

The original four-way V11 output does not distinguish partial support from
ambiguity. For this transfer check, its outputs are interpreted as `supported`,
`contradicted`, `unresolved`, or `review`; partial-support and ambiguity cases
are expected to route to review.

## Result

| Measure | Development | Held-out |
|---|---:|---:|
| Support recall | 0.4000 | 0.7200 |
| Support precision | 0.1961 | 0.2857 |
| False-support rate | 0.4100 | 0.4500 |
| Contradiction false supports | 12 | 11 |
| Unsupported false supports | 3 | 5 |
| Contradiction recall | 0.4000 | 0.2800 |
| Partial/ambiguous review recall | 0.0800 | 0.0400 |
| Review rate | 0.0960 | 0.0800 |

On held-out data, 45 of 100 non-support cases were incorrectly accepted as
supported: 11 contradicted, 5 unsupported, 13 partially supported, and 16
ambiguous cases. Only the support-recall and review-budget gates passed. The
false-support, zero-contradiction-false-support, and review-coverage gates all
failed.

## Decision

V11 must not ship as the ContextTrace 1.3 verifier. The result shows that its
Climate-FEVER safety thresholds do not transfer to the five-way evidence task,
especially for ambiguity and partial support. This is useful evidence against
further tuning on the old 60-case set.

The next experiment may fit a new aggregation policy using only V13 development
signals. Any selected policy will require a new untouched confirmation pack;
the current held-out pack is consumed by this transfer result and cannot be
used again for promotion. Stable defaults remain unchanged, `local_only` makes
zero network calls, and no remote provider is enabled by default.
