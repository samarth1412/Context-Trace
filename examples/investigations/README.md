# Six reproducible RAG failure investigations

These public, fictional cases show the full ContextTrace workflow: preserve the broken trace, localize the evidence-chain failure, apply a targeted fix, and keep an executable regression artifact. They are product demonstrations and were not used as final research evaluation cases.

| Investigation | Signal | Runner ID |
| --- | --- | --- |
| [A grounded answer backed by an expired policy](stale-but-supported/README.md) | `grounded_but_stale` | `stale-but-supported` |
| [A correct sentence with the wrong citation](misleading-citation/README.md) | `citation_mismatch` | `misleading-citation` |
| [Two retrieved runbooks disagree](conflicting-sources/README.md) | `grounded_but_conflicted` | `conflicting-sources` |
| [The answer invents a detail absent from retrieval](evidence-gap/README.md) | `unsupported_claim` | `evidence-gap` |
| [A retriever upgrade removes the only supporting chunk](retrieval-regression/README.md) | `regression` | `retrieval-regression` |
| [From a failed CI gate to a repaired trace](ci-debugging-walkthrough/README.md) | `contradicted_claim` | `ci-debugging-walkthrough` |

```bash
python examples/investigations/run.py --all
```

Every case runs offline with the stable `semantic_v1_calibrated` verifier. `regression.json` records the exact broken and repaired assertions.
