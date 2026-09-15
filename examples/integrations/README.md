# Framework capture to regression gates

These two offline examples complete the loop from framework callbacks to a portable ContextTrace verification gate. They use small objects with the same fields as framework documents and responses, so the scripts remain runnable without installing LangChain or LlamaIndex. In an application, register the same callback classes with the real framework.

```bash
python examples/integrations/langchain_ci_gate.py --out-dir /tmp/contexttrace-langchain-demo
python examples/integrations/llamaindex_source_gate.py --out-dir /tmp/contexttrace-llamaindex-demo
```

`langchain_ci_gate.py` captures retrieval and generation, writes a portable trace, and asserts that a misleading citation is detected. `llamaindex_source_gate.py` captures a query and selected node, writes a portable trace, and asserts that an answer grounded in an explicitly stale source is flagged.

Both examples use fictional data, need no model or network access, and exit nonzero if the expected diagnostic disappears. Replace their mock document or node lists with the values delivered by your application while preserving the capture and verification calls.
