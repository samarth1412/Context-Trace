# Real-World RAG Validation

This is a smoke test against public GitHub RAG projects. It does not vendor their source code.
The runner clones/uses local scratch copies under `.contexttrace/real_world_repos`, retrieves from real project docs/code, creates portable RAG traces, and verifies them with ContextTrace.

Important limitation: this does not execute each original application end-to-end. The cloned projects often require Poetry, local model downloads, GPU-specific dependencies, or app-specific setup. This validation tests ContextTrace against real project corpora and realistic RAG artifacts derived from those corpora.

This is not a leaderboard. It answers one practical question: when a developer points ContextTrace at real RAG-style artifacts, does the output explain useful grounding failures?

## Run

```bash
python benchmarks/real_world_rag/run_real_world_validation.py
```

Environment used in the latest run:

- Generation model: `mistral`
- Embedding model: `all-MiniLM-L6-v2`
- Answer mode: `extractive_from_retrieved_context`
- Date: `2026-06-04`

## Results

### HeskethGD/local-rag-chat

- Repository: https://github.com/HeskethGD/local-rag-chat
- Status: `completed`
- Notes: Offline FastAPI/Streamlit RAG app using Ollama and LanceDB.
- Corpus files: `11`
- Corpus chunks: `50`

| Case | Type | Support Rate | Primary Audit Label | Failure Type | Reports |
| --- | --- | ---: | --- | --- | --- |
| local_rag_chat_1 | `grounded_smoke` | 1.000 | `no_failure_detected` | `no_failure_detected` | [verify](reports/local_rag_chat_1_verify.html) / [audit](reports/local_rag_chat_1_audit.html) / [trace](traces/local_rag_chat_1.json) |
| local_rag_chat_2 | `grounded_smoke` | 1.000 | `no_failure_detected` | `no_failure_detected` | [verify](reports/local_rag_chat_2_verify.html) / [audit](reports/local_rag_chat_2_audit.html) / [trace](traces/local_rag_chat_2.json) |
| local_rag_chat_stress_1 | `retrieval_stress_control` | 0.000 | `retrieval_miss` | `should_have_abstained` | [verify](reports/local_rag_chat_stress_1_verify.html) / [audit](reports/local_rag_chat_stress_1_audit.html) / [trace](traces/local_rag_chat_stress_1.json) |

Representative findings:
- `local_rag_chat_1`: What local models does this RAG chatbot use for chat and embeddings?. Claims: `supported`/no_failure_detected, `supported`/no_failure_detected, `supported`/no_failure_detected
- `local_rag_chat_2`: How does the RAG agent use retrieved sources when drafting an answer?. Claims: `supported`/no_failure_detected, `supported`/no_failure_detected, `supported`/no_failure_detected
- `local_rag_chat_stress_1`: What local models does this RAG chatbot use for chat and embeddings?. Claims: `unsupported`/should_have_abstained, `unsupported`/should_have_abstained, `unsupported`/should_have_abstained

### taha-parsayan/Ollama-and-HuggingFace-RAG-Engine

- Repository: https://github.com/taha-parsayan/Ollama-and-HuggingFace-RAG-Engine
- Status: `completed`
- Notes: LangChain/Ollama/FAISS RAG script with a real text corpus in data/.
- Corpus files: `3`
- Corpus chunks: `53`

| Case | Type | Support Rate | Primary Audit Label | Failure Type | Reports |
| --- | --- | ---: | --- | --- | --- |
| ollama_hf_rag_engine_1 | `grounded_smoke` | 1.000 | `no_failure_detected` | `no_failure_detected` | [verify](reports/ollama_hf_rag_engine_1_verify.html) / [audit](reports/ollama_hf_rag_engine_1_audit.html) / [trace](traces/ollama_hf_rag_engine_1.json) |
| ollama_hf_rag_engine_2 | `grounded_smoke` | 1.000 | `no_failure_detected` | `no_failure_detected` | [verify](reports/ollama_hf_rag_engine_2_verify.html) / [audit](reports/ollama_hf_rag_engine_2_audit.html) / [trace](traces/ollama_hf_rag_engine_2.json) |
| ollama_hf_rag_engine_stress_1 | `retrieval_stress_control` | 0.000 | `retrieval_miss` | `should_have_abstained` | [verify](reports/ollama_hf_rag_engine_stress_1_verify.html) / [audit](reports/ollama_hf_rag_engine_stress_1_audit.html) / [trace](traces/ollama_hf_rag_engine_stress_1.json) |

Representative findings:
- `ollama_hf_rag_engine_1`: What vector store does this RAG engine use?. Claims: `supported`/no_failure_detected, `supported`/no_failure_detected
- `ollama_hf_rag_engine_2`: What should the assistant do if it does not know the answer?. Claims: `supported`/no_failure_detected, `supported`/no_failure_detected, `supported`/no_failure_detected
- `ollama_hf_rag_engine_stress_1`: What vector store does this RAG engine use?. Claims: `unsupported`/should_have_abstained, `unsupported`/should_have_abstained

### umbertogriffo/rag-chatbot

- Repository: https://github.com/umbertogriffo/rag-chatbot
- Status: `completed`
- Notes: Local llama.cpp plus Chroma RAG chatbot with Markdown chunking and incremental indexing.
- Corpus files: `73`
- Corpus chunks: `548`

| Case | Type | Support Rate | Primary Audit Label | Failure Type | Reports |
| --- | --- | ---: | --- | --- | --- |
| rag_chatbot_1 | `grounded_smoke` | 1.000 | `no_failure_detected` | `no_failure_detected` | [verify](reports/rag_chatbot_1_verify.html) / [audit](reports/rag_chatbot_1_audit.html) / [trace](traces/rag_chatbot_1.json) |
| rag_chatbot_2 | `grounded_smoke` | 1.000 | `no_failure_detected` | `no_failure_detected` | [verify](reports/rag_chatbot_2_verify.html) / [audit](reports/rag_chatbot_2_audit.html) / [trace](traces/rag_chatbot_2.json) |
| rag_chatbot_stress_1 | `retrieval_stress_control` | 0.000 | `retrieval_miss` | `should_have_abstained` | [verify](reports/rag_chatbot_stress_1_verify.html) / [audit](reports/rag_chatbot_stress_1_audit.html) / [trace](traces/rag_chatbot_stress_1.json) |

Representative findings:
- `rag_chatbot_1`: How does this chatbot update its vector database when documents change?. Claims: `supported`/no_failure_detected, `supported`/no_failure_detected, `supported`/no_failure_detected
- `rag_chatbot_2`: What response synthesis strategies does the chatbot support?. Claims: `supported`/no_failure_detected, `supported`/no_failure_detected
- `rag_chatbot_stress_1`: How does this chatbot update its vector database when documents change?. Claims: `unsupported`/should_have_abstained, `unsupported`/should_have_abstained, `unsupported`/should_have_abstained

## Honest Takeaways

- ContextTrace is already useful as a local post-hoc verifier for RAG artifacts built from real project corpora.
- The clean smoke cases produced `no_failure_detected` with support rate `1.0`, which is the expected pass behavior.
- The retrieval stress controls produced `unsupported_answer`, `should_have_abstained`, and audit-level `retrieval_miss`, which is the expected failure behavior.
- The biggest gap is ingestion ergonomics: real projects do not expose a universal trace format, so adapters are still manual.
- The next product feature should be adapter helpers that turn common LangChain, Haystack, LlamaIndex, Ollama, and HTTP endpoint traces into ContextTrace JSON with minimal glue code.
