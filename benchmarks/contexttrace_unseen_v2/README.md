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

## Planned composition

- 300 Natural OOD traces: 100 software/product documentation, 100
  support/operational knowledge-base, and 100 policy/regulatory traces;
- 100 temporal/source-condition traces from 20 five-question source pairs;
- BM25, dense-vector, and hybrid retrieval;
- 384- and 768-token chunking with and without deterministic reranking;
- two local generator families, with no paid API calls;
- complete source snapshots, retrieval rankings, selected evidence, prompts,
  generator identities, timings, and hashes;
- no gold labels or verifier outputs.

Raw snapshots and traces remain in a private, Git-ignored artifact root. The
checked-in public manifest contains source/configuration metadata, immutable
case IDs, artifact hashes, and no diagnostic labels.
