# Evidence integrity examples

These two fictional offline cases exercise the ContextTrace 1.3 evidence-integrity
contract with framework-shaped metadata:

- LangChain: a sentence selector keeps a question and drops its linked answer.
- LlamaIndex: selected source text drops a declared return condition.

Run both without API keys, model downloads, or network access:

```bash
PYTHONPATH=packages/contexttrace python examples/evidence_integrity/run.py
contexttrace inspect examples/evidence_integrity/langchain_linked_answer_loss.json
contexttrace inspect examples/evidence_integrity/llamaindex_qualifier_loss.json
```

The integration labels describe the source shape; these committed files do not
claim a live framework version was exercised. See
[`docs/evidence-integrity-v1.3.md`](../../docs/evidence-integrity-v1.3.md) for the
capture contract and its limits.
