# Baseline Capability Matrix

“N/A” means the system does not output that construct; it does not mean a score of
zero.

| Baseline | Execution | Evidence support | Failure label | Root cause | Unverifiable | Evidence span | Primary status |
|---|---|---:|---:|---:|---:|---:|---|
| `semantic_v1_calibrated` | local deterministic | yes | yes | yes | limited | yes | required predecessor comparator |
| `lexical_evidence_overlap_v1` | local deterministic | continuous overlap only | N/A | N/A | N/A | claim offsets only | executable sanity baseline |
| `minilm_cosine_support_v1` | pinned local model | continuous similarity only | N/A | N/A | N/A | N/A | adapter ready; run pending |
| RAGAS 0.4.3 | judge/model dependent | selected metrics | N/A | N/A | metric dependent | N/A | adapter only; model/budget not authorized |
| DeepEval 4.1.4 | judge/model dependent | selected metrics | N/A | N/A | metric dependent | N/A | adapter only; model/budget not authorized |
| RAGChecker 0.1.9 | extractor/checker models | claim-level metrics | generator/retriever classes only | limited, incompatible taxonomy | N/A | claim units | sealed scoring-zone conditional |
| RAGXplain paper | unavailable artifact | paper-defined | paper-defined | explanatory recommendations | paper-defined | paper-defined | not reproducibly runnable in this lock |
| TRAIL paper | agent-trace method | agent-trace evidence | issue types | agent-step localization | N/A | trace-step localization | deferred secondary transfer |
| Generic LLM judge | remote or local judge | yes | support verdict only | N/A by prompt | yes | N/A | prompt frozen; model/budget not authorized |
| Aggregate score | derived, deterministic | aggregate only | N/A | N/A | N/A | N/A | developer-study summary only |

No cross-system table may relabel an unavailable output as an error. Metrics sharing
a name are compared only when their unit, reference inputs, and semantics match.
