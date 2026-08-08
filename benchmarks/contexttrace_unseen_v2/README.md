# ContextTrace-Unseen-v2

ContextTrace-Unseen-v2 is the successor confirmatory corpus created after the
original 493 ContextTrace-Unseen-v1 cases were reclassified as development data.
It is intentionally source-, domain-, and publication-window-disjoint from both
that corpus and every declared calibration source.

The sequence is fail closed:

1. finish development on the reclassified Unseen-v1 cases;
2. commit and hash-freeze the candidate, local NLI, thresholds, schema,
   taxonomy, metrics, and statistical tests;
3. acquire and generate the new unlabeled corpus without invoking any
   ContextTrace verifier;
4. publish the unlabeled manifest and SHA-256;
5. independently annotate and seal labels;
6. execute the candidate and baselines once, then score inside the sealed zone.

No annotation, candidate execution, scoring, publication claim, version tag, or
package release is authorized by the corpus freeze.

## Frozen composition

- 300 Natural OOD traces: 100 software/product documentation, 100
  support/operational knowledge-base, and 100 policy/regulatory traces;
- 100 temporal/source-condition traces from 20 five-question source pairs;
- 160 BM25, 130 dense-vector, and 110 hybrid retrieval traces;
- 240 384-token and 160 768-token traces, with deterministic reranking on 160;
- 210 Gemma 3 4B and 190 Qwen 3 1.7B local generations, with no paid API
  calls;
- complete source snapshots, retrieval rankings, selected evidence, prompts,
  generator identities, timings, and hashes;
- no gold labels or verifier outputs.

Raw snapshots and traces remain in a private, Git-ignored artifact root. The
checked-in public manifest contains source/configuration metadata, immutable
case IDs, artifact hashes, and no diagnostic labels.

## Freeze identity

- status: `frozen_unlabeled_unscored_unannotated`;
- public manifest: `contexttrace_unseen_v2_frozen_unlabeled.json`;
- manifest payload SHA-256:
  `e07d58d25c901694ba4870e01de44192ce51768a9593cc545bff7a3e6831a42e`;
- manifest file SHA-256:
  `739cd8a8e47ef9dbae2407242d164f460c06f9a67887f0952331b66b87b61282`;
- freeze-record payload SHA-256:
  `a4f38c0af6b3bee4650e5da02a590a237a9508218017c08225ba0ad754fd9e96`;
- candidate execution, annotation, labels, evaluation, release, and publication
  claims remain unauthorized.
