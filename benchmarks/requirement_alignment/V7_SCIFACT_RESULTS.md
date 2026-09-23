# V7 SciFact cross-domain transfer results

## Decision

The frozen V6 cascade improves substantially over both local verifier artifacts
on scientific claim verification, but it does not meet the predeclared transfer
gates and must remain experimental. The result supports continued development
of an optional Jev route; it does not justify enabling a remote provider by
default.

On 180 balanced SciFact evaluation cases, the optional cascade reaches **76.67%
accuracy**, **0.6842 macro F1**, **38.33% supported recall**, and a **4.17%
false-support rate**. This improves over v3 at 65.56% accuracy, 0.5104 macro F1,
16.67% recall, and 10.00% false support. It also improves over v5 at 73.89%
accuracy, 0.6381 macro F1, 31.67% recall, and 5.00% false support.

The transfer gate still fails because supported recall remains below 50%, two
contradictions are marked supported, and the local-only automatic subset has a
12.20% false-support rate.

## Dataset and isolation

V7 uses the official SciFact release archive with SHA-256
`11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be`.
SciFact train supplies 270 development-only cases; SciFact dev supplies 180
evaluation cases. Each split is balanced across 60 or 90 support,
contradiction, and no-evidence cases. Claim IDs are disjoint across the splits.

Support and contradiction inputs contain one upstream gold rationale group.
No-evidence cases come from claims with no annotated evidence and use up to
three deterministic high-overlap sentences from a cited abstract. Labels are
upstream expert annotations; no evaluation label is synthetic.

The V6 policy, v3 artifact, and v5 artifact were frozen before SciFact scoring.
SciFact was not used for their training, threshold selection, prompt selection,
or route selection. The public dev split is evaluation rather than the hidden
test set because SciFact test labels are not public.

## Results

| System | Accuracy | Macro F1 | Supported recall | False-support rate | Remote calls |
|---|---:|---:|---:|---:|---:|
| V3, threshold 0.90 | 0.6556 | 0.5104 | 0.1667 | 0.1000 | 0/180 |
| V5, threshold 0.90 | 0.7389 | 0.6381 | 0.3167 | 0.0500 | 0/180 |
| Frozen V6 + optional Jev | **0.7667** | **0.6842** | **0.3833** | **0.0417** | 124/180 |

The optional route predicts support for 23 of 60 entailments. It incorrectly
predicts support for two of 60 contradictions and three of 60 no-evidence
cases. All five false supports originate from the local-agreement branch. Jev
accepts 12 routed cases as supported, all 12 are true entailments, and it adds
no routed false support.

This separation is actionable: Jev is helping safe recall, while the frozen
local support rule is the source of the remaining unsafe decisions. A next
candidate should add a contradiction-aware local guard before automatic support
and develop the decomposed Jev support check on SciFact train only. This
evaluation split is now consumed and must not be used for tuning.

## Local-first and operational behavior

Under `local_only`, uncertain cases abstain with zero network calls. The frozen
policy automatically decides 56/180 cases (31.11% coverage), reaches 83.93%
accuracy on those decisions, and has five false supports. It abstains on 124
cases.

With explicit remote opt-in, 124 cases are routed to Jev (68.89%). The run uses
87,329 total tokens, with 287.236 ms mean and 485.382 ms p95 request latency.
Every call resolves to `jev-1.13.0`. All supported decisions and low-confidence
remote decisions require review; the resulting no-review subset has 51.11%
coverage, 84.78% accuracy, and zero false supports.

Jev receives only the claim and selected evidence IDs/text. Query, title,
document metadata, split, relation, and evaluation labels are absent. Results
contain full probabilities, confidence, resolved model, latency, and token
usage. Explanation and matched/missing/conflicting fact fields remain empty.

## Scope

SciFact directly covers supported, contradicted, and no-evidence cases. It does
not supply partial-support or ambiguity labels, so V7 makes no transfer claim
for those categories. Gold rationales also isolate verification from retrieval;
this experiment does not measure end-to-end evidence retrieval quality.
