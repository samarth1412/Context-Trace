# Experimental `hybrid_v2` verifier

`hybrid_v2` is the opt-in successor-development path for ContextTrace. It keeps
the default `semantic_v1_calibrated` verifier stable while new source-validity
and evidence-gap behavior is developed on declared development data.

## Use

```python
from contexttrace.verify import verify_trace_hybrid_v2
from contexttrace.verify.schema import RAGTrace, TraceContext

trace = RAGTrace(
    query="Which API should integrations use?",
    answer="Integrations should use LegacyClient.",
    contexts=[
        TraceContext(
            id="v1",
            text="Guide version 1: integrations should use LegacyClient.",
        ),
        TraceContext(
            id="v2",
            text=(
                "Guide version 2: LegacyClient was retired; integrations "
                "should use ModernClient instead."
            ),
        ),
    ],
)

result = verify_trace_hybrid_v2(trace, mode="semantic")
```

The result identifies itself as:

- schema: `2.0` (`ClaimVerificationHybridV2`);
- taxonomy: `contexttrace-hybrid-v2.0`;
- verifier: `hybrid_v2`;
- profile: `hybrid_v2` for the full default profile;
- diagnostic reasoner: `evidence_chain_v2`;
- experimental: `true`.

## Phase 1 boundary

The hybrid path currently adds content-derived chronology and lifecycle
relations, unresolved-conflict handling, query temporal scope, and
query-conditioned evidence-gap diagnosis. Its experimental semantic path also
binds JSON fields and table/CSV rows, checks explicitly prohibited operation
order and conditional exceptions, handles exclusive feature scope, and respects
query-scoped source attribution and historical lifecycle context. It uses the established deterministic
evidence verifier in `semantic` mode. A local NLI provider is available only
when the caller explicitly selects `mode="nli"`; ContextTrace does not download
models automatically.

The earlier `semantic_core_v2` package remains a separate research prototype
for strict selective verification and a pinned NLI cascade. Its schema and
predictions must not be mixed with `hybrid_v2` artifacts.

## Research status

The v1.2.0 implementation was hash-frozen on 2026-09-13 before generation or
scoring of the controlled final corpus. The embedded development manifest is the
earlier development-boundary record retained byte-for-byte so the evaluated
implementation remains identifiable.

The one-shot controlled study found that the hybrid caught more faults but
produced substantially more false alarms and underperformed
`semantic_v1_calibrated` on the balanced release-gate measure. The result does
not support hybrid superiority. Exact study results are withheld from public
product materials during double-anonymous review. The implementation is released
for explicit evaluation and feedback, with its negative conclusion preserved.

## Limitations

The verifier reasons only from supplied text and metadata. It cannot establish
independent real-world truth, and it reports freshness as unknown when neither
source text nor metadata provides observable chronology or lifecycle evidence.
The API remains experimental and can change in a future version. Do not use it
as a blocking production gate without calibrating false alarms on the target
system. The v1.2.0 default stays on `semantic_v1_calibrated`.
