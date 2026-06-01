# Examples

Examples live in `examples/`.

- `custom_rag.py`: basic SDK tracing around a custom retriever and generator.
- `local_report.py`: export a local HTML report.
- `batch_eval.py`: run local eval workflows.
- `fastapi_rag_endpoint.py`: sample endpoint for BYO RAG API eval.
- `langchain_rag.py`: LangChain callback example.
- `llamaindex_rag.py`: LlamaIndex callback example.
- `agent_trace.py`: agent event timeline example.

Try the local endpoint eval example:

```bash
uvicorn examples.fastapi_rag_endpoint:app --reload
contexttrace eval \
  --dataset datasets/demo/refund_policy/questions.json \
  --endpoint http://localhost:8000/query \
  --answer-path $.answer \
  --contexts-path $.contexts \
  --citations-path $.citations
```
