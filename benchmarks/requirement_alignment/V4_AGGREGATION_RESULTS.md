# Hierarchical evidence aggregation results

## Decision

Per-span evidence aggregation does not improve the frozen v3 verifier. The
existing concatenated-evidence policy remains the selected policy with 47.5%
ContractNLI entailment recall. No v4 candidate meets the 50% promotion gate,
so product behavior remains unchanged and the next experiment should use a
stronger local backbone.

## Fixed protocol

The experiment used the hash-verified v3 model without changing its weights.
It compared three policies fixed before scoring:

1. concatenate the selected evidence, matching v3;
2. take the maximum entailment probability across independently scored spans;
3. take maximum entailment unless any span has contradiction probability at or
   above 0.50.

Every policy used one shared threshold selected on the same fixed 0.05 grid and
the existing dual gates: ContractNLI recall at least 50%, false-positive rate at
most 5% on both sets, and WiCE recall at least 22.54%. ContractNLI test was not
accessed. Jev and other remote inference were not used.

## Results

| Policy | Threshold | Contract recall | Contract FPR | Contract AUC | WiCE recall | WiCE FPR | Gates met |
|---|---:|---:|---:|---:|---:|---:|---|
| **Concatenated** | **0.90** | **0.4750** | **0.0063** | **0.8200** | **0.2319** | **0.0421** | No |
| Maximum entailment | 1.00 | 0.0000 | 0.0000 | 0.7094 | 0.0000 | 0.0000 | No |
| Contradiction veto | 1.00 | 0.0000 | 0.0000 | 0.6958 | 0.0000 | 0.0000 | No |

Maximum per-span entailment raises false-support scores enough that no
non-abstaining threshold on the fixed grid satisfies both safety caps. Its ROC
AUC also falls from 0.8200 to 0.7094. The contradiction veto suppresses 161 of
240 ContractNLI cases but does not restore useful safe recall. It also adds the
cost of scoring 527 ContractNLI spans and 345 WiCE spans instead of 240 and 164
concatenated inputs.

The concatenated policy takes 7.517 seconds on ContractNLI and 5.136 seconds on
WiCE in this CPU run. Per-span inference takes 16.754 and 10.984 seconds,
respectively. These timings are environment-specific, but the per-span method
is slower without a quality benefit.

## Conclusion

Evidence aggregation is not the missing improvement. V3 already handles the
selected evidence group better as a whole than as independent spans. The next
bounded experiment should retain the three-way relation objective and
concatenated evidence while replacing the small DeBERTa backbone with one
stronger local model. V3 remains the baseline and the ContractNLI test split
remains reserved for confirmation after a development candidate passes.
