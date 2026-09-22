# MiniCheck baseline status

## Implementation

The binary MiniCheck baseline is runnable and isolated under `benchmarks/`.
It uses the exact Jev-v2 shared selector and evaluates the task MiniCheck
documents: sentence support versus non-support. It does not manufacture
five-way verdicts, explanations, matched facts, or evidence spans.

Pinned identities for the executed baseline:

- Official source commit: `b58b9fa69acbd1015ec970fa65dd752413a053d2`
- Model: `lytang/MiniCheck-RoBERTa-Large`
- Model revision: `74c8919647e61ed0f71bc177d94f10930f090068`
- Weight bytes: `1421577710`
- Weight SHA-256: `67af45a2d5a2706283821049232c7d7c81cea22e81dfdbb7097487a98bc61b53`
- Published decision threshold: `0.5`
- NLTK data commit: `550b6625bcef1f2abff2ff770a5a0d272c9c6b2a`
- `punkt.zip` SHA-256: `51c3078994aeaf650bfc8e028be4fb42b4a0d177d41c012b6a983979653660ec`
- `punkt_tab.zip` SHA-256: `e57f64187974277726a3417ca6f181ec5403676c717672eef6a748a7b20e0106`

The runner rejects a missing, partial, or mismatched weight before importing
the model. Inference forces Hugging Face Hub and Transformers offline. It also
checks that comparison artifacts have identical case IDs and selected-input
hashes before reporting disagreements.

## Results

The published threshold was used for development and then unchanged for one
held-out run. These are binary grounding results and are not comparable to the
five-way Jev macro F1.

| Split | Accuracy | Balanced accuracy | Macro F1 | False support | Supported rejected |
|---|---:|---:|---:|---:|---:|
| Development (15) | 0.8000 | 0.8000 | 0.7847 | 2/10 | 1/5 |
| Held-out (15) | 0.7333 | 0.6000 | 0.5833 | 0/10 | 4/5 |

On development, MiniCheck alone was correct on three cases where the stable
verifier was wrong, while the stable verifier alone was correct on two. Against
Jev's binary projection, MiniCheck alone was correct on one and Jev alone on
two. On held-out, MiniCheck, Jev, and the stable verifier made the same 15
binary decisions: all ten non-supported claims were rejected, but four of five
supported claims were also rejected.

This is positive evidence that the experiment is working and that a
grounding-specific model can recover supported claims missed by the stable
verifier on development. It is not evidence for a runtime `MiniCheckJudge` or
`JevJudge`: the development false-support rate is 20%, the held-out supported
recall is 20%, and the held-out binary decisions add no coverage beyond the
existing systems. Keep MiniCheck as a research baseline while expanding the
independently annotated evaluation set and testing the stronger Flan checkpoint.

The later non-overlapping extension contains 39 development and 72 held-out
cases. On extension held-out, MiniCheck reaches 0.7361 binary accuracy and
0.7241 binary macro F1, with 14 false-support decisions among 48 negative
claims. Jev's binary projection reaches 0.8889 accuracy with four false-support
decisions on the same exact inputs. See `EXTENSION_RESULTS.md`; the extension
strengthens MiniCheck's value as a baseline but not as a runtime judge.

## Reproduce

```bash
PYTHONPATH=packages/contexttrace:. TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m benchmarks.jev_v2_verification.minicheck_baseline \
  --cases benchmarks/jev_v2_verification/ragtruth_sentence_development.json \
  --split development \
  --model roberta-large \
  --cache-dir .tmp-contexttrace-models/minicheck-roberta-cache \
  --nltk-data .tmp-contexttrace-models/nltk_data \
  --threshold 0.5 \
  --baseline-results benchmarks/jev_v2_verification/results/ragtruth_sentence_development_jev.json \
  --output benchmarks/jev_v2_verification/results/ragtruth_sentence_development_minicheck_roberta.json
```

Use the frozen held-out case pack and corresponding held-out Jev result for the
held-out reproduction. Do not tune the model, evidence formatting, or threshold
against that split.

The stronger Flan checkpoint remains supported but unexecuted because its 3.1
GB transfer did not complete. Its pinned identity and integrity checks remain
in the runner and README.
