# V19 independent confirmation result

**V25 qualification:** the adapter uses the same QA fragmentation pattern
documented in [the V25 input audit](V25_INPUT_AND_REPRESENTATION_RESULTS.md).
V19 has not been rescored or relabeled. Its failure remains a failed release
gate, but should not be attributed solely to verifier quality without auditing
the selected inputs and inherited labels.

The frozen V18 candidate was evaluated once on the frozen V19 five-way set.
No case, feature, estimator, threshold, or policy changed after the set was
frozen. The candidate fails confirmation and is not eligible for packaging or
release.

## Protocol

The set contains 125 cases, balanced across the five ContextTrace verdicts.
The candidate artifact was frozen at SHA-256
`bcc5f0d2e66edbb5a400c5c54bb59a31a39ac1a6ce02ff38602b5f0af6288009`
before the V19 data was accessed. The dataset was then frozen at SHA-256
`2fa52ad909c62cee9b610191aea89d5ab74523446a411070c0a96c387f36050c`
before any prediction was generated.

Scoring ran locally with the pinned V11 NLI model. It processed 684 selected
evidence spans, 146 V15 atomic requirements, and 1,578 V17 evidence
combinations. Evaluation labels were excluded from model inputs. No remote
inference or network call occurred, and stable ContextTrace defaults were not
changed.

## Confirmation result

| Measure | Frozen gate | V19 result | Pass |
|---|---:|---:|:---:|
| Support recall | at least 50% | **36.0%** | No |
| False-support rate | at most 5% | **22.0%** | No |
| Contradiction false supports | zero | **7** | No |
| Partial/ambiguous review recall | at least 75% | **38.0%** | No |
| Review rate | at most 60% | **33.6%** | Yes |

Accuracy is 23.2% and macro-F1 is 0.2003. The candidate never predicts
`unverifiable`, so recall for that verdict is zero. Its prediction distribution
is 31 supported, 42 partially supported, 22 contradicted, 30 unsupported, and
zero unverifiable.

Label-stratified 95% bootstrap intervals over 10,000 samples are:

| Measure | Lower | Upper |
|---|---:|---:|
| Accuracy | 0.1680 | 0.3040 |
| Macro-F1 | 0.1415 | 0.2614 |
| Support recall | 0.2000 | 0.5600 |
| False-support rate | 0.1400 | 0.3000 |
| Partial/ambiguous review recall | 0.2600 | 0.5200 |
| Review rate | 0.2560 | 0.4160 |

The earlier V17 development result was 72.8% accuracy and 0.7276 macro-F1,
with all five gates passing. The V19 result shows that performance did not
transfer to the new claim and evidence distribution. The two values describe
different datasets and must not be presented as a direct improvement test.

## Rescue analysis

On this confirmation set, the frozen V15 baseline reaches 21.6% accuracy,
0.1858 macro-F1, 28% support recall, and a 21% false-support rate. The V17 rule
promotes three cases and correctly promotes two supported claims, raising
support recall to 36% and macro-F1 to 0.2003. Its third promotion is the
contradicted case `averitec_dev_0037`. The rescue therefore has 66.67%
promotion precision and increases contradiction false supports from six to
seven. This trade is unsafe under the frozen release gates.

## Decision

Do not package or release the V18/V17 candidate. It does not support a
state-of-the-art quality claim. Stable verifier behavior remains unchanged,
remote providers remain optional and disabled by default, and `local_only`
continues to make zero network calls.

V19 is now consumed. It can be used as development diagnostic data, but it
cannot be reused as fresh confirmation after changes. The next experiment
should target the observed domain-transfer failures, especially conflict and
insufficient-evidence recognition, using disjoint training data. Any revised
candidate then needs another newly frozen, untouched source for confirmation.

The machine-readable result is
[`results/v19_confirmation_result.json`](results/v19_confirmation_result.json).
