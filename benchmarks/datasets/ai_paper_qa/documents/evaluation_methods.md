# RAG Evaluation Methods

RAG systems can be evaluated with answer correctness, citation support, retrieval recall, and abstention behavior. Citation support checks whether each answer claim is grounded in the cited passage.

Failure analysis should distinguish retrieval misses from answer generation errors. A system can cite a retrieved document and still make an unsupported claim when the cited text does not contain the required evidence.

