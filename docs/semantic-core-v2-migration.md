# Migrating to `semantic_core_v2`

`semantic_core_v2` is an opt-in research verifier. The default ContextTrace
verifier remains `semantic_v1_calibrated`; existing v1 traces, schemas, CLI
behavior, and provenance fields are unchanged.

## Use the deterministic selective profile

```python
from contexttrace.verify.schema import load_trace_file
from contexttrace.verify.semantic_core_v2 import (
    DETERMINISTIC_ONLY_V2_PROFILE,
    verify_trace_v2,
)

trace = load_trace_file("trace.json")
prediction = verify_trace_v2(
    trace,
    profile=DETERMINISTIC_ONLY_V2_PROFILE,
)
```

Low-confidence deterministic cases become schema-valid diagnostic abstentions.
They are not forced into a supported verdict.

## Enable the frozen local NLI cascade

The research profile pins:

- model: `cross-encoder/nli-deberta-v3-small`;
- revision: `fa2804872c3b4bd748f38c0185cc85775361e735`;
- artifact-manifest SHA-256:
  `330f0fd77aad129877e1a1a90d4a77e6f093ee238b97d535202816a116b9c9f3`;
- backend: local Transformers;
- precision: float32;
- maximum input length: 512.

ContextTrace never downloads this model automatically. Download the exact
revision into a private local directory, then verify and load it:

```python
from contexttrace.verify.schema import load_trace_file
from contexttrace.verify.semantic_core_v2 import (
    build_pinned_nli,
    verify_trace_v2,
)

nli = build_pinned_nli("/private/models/nli-deberta-v3-small")
prediction = verify_trace_v2(load_trace_file("trace.json"), nli=nli)
```

Any missing or changed model/tokenizer artifact fails closed. When NLI is
required but absent or fails, the default selective profile emits
`unverifiable` with diagnostic abstention.

## V2 output fields

V2 uses `claim-verification-v2.schema.json` and keeps these concepts separate:

- `claim_verdict` and `support_status`;
- `truth_status`, which remains `not_assessed`;
- `source_condition`;
- `citation_state`;
- `failure_label`;
- `primary_root_cause`;
- `abstention_requirement` and `diagnostic_abstention`;
- `diagnostic_confidence` and `route`;
- exact-offset claim text and evidence spans.

Do not coerce a v2 artifact into the v1 schema. Store both artifacts when a
paired comparison is required.

## Source-condition metadata

Fine-grained source-condition transfer requires observable metadata on
`TraceContext.metadata`. Supported signals include:

- `canonical` or `is_canonical`;
- `current` or `is_current`;
- `stale`, `superseded`, or their `is_*` forms;
- `source_condition` or `source_status`;
- `authority_score`;
- `supersedes`, `conflicts_with`, or `authority_conflict`;
- source version and publication/effective timestamp.

If those observables are absent, v2 reports `unknown`; it does not infer hidden
authority or freshness.

## Observable pipeline causes

Retrieval, reranking, chunking, and corpus-gap diagnoses require corresponding
trace metadata such as:

- `eligible_evidence_in_retrieved_candidates`;
- `eligible_evidence_in_corpus`;
- `reranking_enabled`;
- `chunking_destroyed_relation`.

Without stage evidence, v2 uses `not_observable`. This prevents fluent
explanations from becoming unsupported causal claims.

## Bounded execution and privacy

V2 bounds query, answer, context, total-context, claim, NLI-span, and worker
counts. Every truncation is recorded and suppresses green output. Candidate
predictions contain hashes and allowlisted identifiers, not full trace metadata
or full contexts. Local NLI exceptions are reduced to stable error codes.
