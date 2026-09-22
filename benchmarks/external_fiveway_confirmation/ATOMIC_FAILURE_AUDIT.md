# Atomic coverage failure audit

## Finding

The fresh 60-case development validation audit shows that no single threshold
or selector adjustment will fix complete-support detection. The 28 supported
false negatives divide into three actionable groups:

| Primary failure mode | Cases | Share of supported false negatives |
| --- | ---: | ---: |
| Frozen NLI or requirement representation fails even on a gold evidence group | 15 | 53.6% |
| A gold group can pass, but the selector misses the complete group | 8 | 28.6% |
| The complete group is present globally but routed to the wrong requirement | 5 | 17.9% |

The normal candidate path recognized only 2/30 supported claims. Giving the
same atomic decision rule a complete WiCE gold evidence group raised that
diagnostic upper bound to 15/30. This establishes that retrieval and routing
cause a substantial part of the loss, while the generic NLI model or its
requirement representation still fails on half of fully supported claims.

## Retrieval evidence

At least one annotated WiCE sentence was retrieved for 28/30 supported claims,
but a complete annotated group was present for only 13/30. Retrieving one
relevant sentence is therefore a misleading success measure for complete
support. The training and evaluation target must require a complete evidence
group for every material requirement.

The five routing failures had a complete group somewhere in the selected set
and passed when that group was supplied together, but per-requirement selection
did not give each requirement the evidence it needed. The next selector should
score requirement–evidence pairs and preserve group coverage rather than
independently taking the top lexical spans.

## Decomposition correction

The audit found five cases where the first prototype reconstructed a sentence
instead of retaining an exact claim span. One example inserted the malformed
phrase `reputation has it is viewed`. The experimental decomposer was corrected
to return only exact claim substrings, and its version was advanced to
`atomic_coverage_v2_experimental`.

After the correction, all 60 validation cases have exact source provenance for
every requirement. The final accuracy and supported recall remained 50.0% and
6.67%, respectively. This removes a tracing defect but confirms it was not the
main quality bottleneck.

## False support

Two partially-supported cases, `wice_dev02670` and `wice_dev02905`, were still
marked supported. The 6.67% partial-to-supported rate exceeds the 5% safety
limit. These cases must be hard negatives in model development, but their
validation labels must not be used for fitting or threshold selection.

## Next training specification

The next model should be trained only from the official WiCE training split.
Each record should preserve the original case ID, exact requirement substring,
evidence context IDs, and construction provenance.

- Positive pairs: an exact claim requirement with a complete annotated
  supporting group.
- Missing-coverage negatives: remove one required annotated sentence from a
  multi-sentence group.
- Retrieval negatives: pair the requirement with high-overlap non-supporting
  sentences from the same case.
- Partial-support negatives: use upstream partial claims to represent cases
  where some evidence exists but the full claim is not established.
- Group objective: score whether one evidence group covers every requirement,
  in addition to scoring individual requirement–evidence pairs.

The existing 120-case calibration pack may be used for threshold selection,
and the disjoint 60-case extension must remain validation-only. A held-out pack
must remain unopened until the same gates are met: at least 50% supported
recall, at least 70% partial recall, at most 5% partial-to-supported errors, and
macro F1 above base Jev.

## Protocol integrity

Gold WiCE evidence was used only in this post-prediction diagnostic. It was
never supplied to the candidate run, and evaluation labels were never sent to
NLI. All 568 oracle-diagnostic NLI calls ran locally with the frozen model. Jev
was not called, product defaults were not changed, and no held-out data was
created or queried.
