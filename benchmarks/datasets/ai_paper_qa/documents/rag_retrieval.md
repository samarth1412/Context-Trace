# Retrieval-Augmented Generation

Retrieval-augmented generation answers a query by retrieving external passages and conditioning a generator on that evidence. Retrieval quality affects factuality because the generator can only ground answers in the selected context.

Hybrid retrieval combines lexical ranking with dense vector search. Reranking can improve precision by scoring the retrieved candidates against the query before the generator receives the final context.

