# Synthetic Retrieval Paper

## Method
The paper evaluates hybrid retrieval by combining sparse BM25 scores with dense embedding similarity before reranking the top candidates.

## Findings
Hybrid reranking improved answer citation support from 0.71 to 0.84 on the policy QA set, with a 120 ms median latency increase.
