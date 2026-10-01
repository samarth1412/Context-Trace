# ContextTrace 1.3 evidence integrity

Status: first product slice implemented behind existing `inspect` and `repair`
workflows. The stable verifier and its defaults are unchanged.

## Product promise

ContextTrace reports when an instrumented RAG transformation drops or detaches
captured evidence, then carries that observed failure into a repair plan and a
repeatable CLI gate.

This slice distinguishes observations from unknowns:

- `linked_part_dropped`: one required part of a captured unit remains selected
  while another required part is absent, such as a retained question with its
  linked answer removed.
- `material_span_dropped`: a developer-declared qualifier, condition, or value
  is present in the captured source unit and absent from the selected fragment.
- `selected_text_not_in_source`: the selected text is not a normalized verbatim
  span of its claimed source unit. ContextTrace does not guess whether this came
  from mutation, bad lineage, or misattachment.
- `not_captured` / `invalid_lineage`: the transformation remains unknown because
  the required source state was not captured correctly.

All checks are deterministic, local, and offline. They make zero model or network
calls. Jev remains an optional research comparator; it is not needed to establish
verbatim lineage or declared-span loss.

## Capture contract

Attach namespaced lineage to each selected context with
`build_evidence_lineage()`:

```python
from contexttrace import build_evidence_lineage, capture_rag_trace

source = "Question: When are refunds issued? Answer: After approval."
metadata = build_evidence_lineage(
    source_unit_id="refund_qa",
    source_text=source,
    linked_parts=[
        {"id": "question", "role": "question", "text": "Question: When are refunds issued?"},
        {"id": "answer", "role": "answer", "text": "Answer: After approval."},
    ],
    transformation="sentence_selector",
)

trace = capture_rag_trace(
    query="When are refunds issued?",
    answer="After approval.",
    contexts=[{"id": "selected", "text": "Question: When are refunds issued?", "metadata": metadata}],
)
```

`linked_parts` and `material_spans` must name text that actually exists in the
captured `source_text`. ContextTrace never constructs a missing span or explanation.

## Inspect, repair, and gate

```bash
contexttrace inspect trace.json
contexttrace inspect trace.json --fail-on evidence_integrity
contexttrace inspect trace.json --fail-on unknown_integrity
contexttrace repair trace.json --mode lexical --out repair.md
```

`inspect` reports issue counts, assessed contexts, and unknown contexts. `repair`
places observed transformation loss before inferred RAG causes and recommends
preserving the captured linked unit or material span. After repair, recapture the
trace and add the passing result to the existing suite workflow.

## Frozen acceptance checklist

- A complete linked unit produces `complete` with no issues.
- A selected question that drops its captured linked answer produces exactly one
  `linked_part_dropped` issue.
- A selected prefix that drops a declared condition produces
  `material_span_dropped`.
- Text that is not present in its claimed source produces
  `selected_text_not_in_source` without assigning a cause.
- Missing or malformed lineage remains unknown and never becomes a loss finding.
- Every finding references captured context, source-unit, and part/span IDs.
- Existing verification labels and stable defaults do not change.
- The implementation performs zero network and model calls.
- LangChain-shaped and LlamaIndex-shaped fictional cases reproduce offline.

## Current boundary

This slice audits transformations only when both sides were instrumented. It does
not reconstruct uncaptured source state, decide which undeclared text was
important, or establish the semantic effect on an answer. Those are separate
evaluation questions for the next bounded research pilot.
