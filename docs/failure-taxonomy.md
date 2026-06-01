# Failure Taxonomy

ContextTrace reports practical failure labels for RAG debugging.

- `no_failure_detected`: available checks did not find a reliability issue.
- `retrieval_miss`: expected evidence was not retrieved.
- `low_relevance_context`: retrieved context is weakly related to the query.
- `citation_mismatch`: a claim cites a chunk that does not support it.
- `unsupported_answer`: the answer contains claims not supported by retrieved context.
- `contradicted_answer`: retrieved evidence contradicts the answer.
- `conflicting_sources`: retrieved sources disagree or mix current and archived policies.
- `bad_chunking`: relevant evidence is split or incomplete because of chunk boundaries.
- `over_compression`: compression removed needed qualifiers or evidence.
- `should_have_abstained`: the answer should have said the evidence was insufficient.
- `query_needs_decomposition`: the query likely needs multiple retrieval steps.
- `unknown`: the evaluator could not classify the issue.

Reports include severity, root cause, and a suggested fix. Treat the label as a debugging aid, not a scientific benchmark.
