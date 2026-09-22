# Experimental local-quality verifier

`contexttrace.verify.local_quality` is an opt-in, local-only verification path.
It addresses compound-claim, number, negation, explicit-absence, qualifier, and
conflicting-evidence failures found during the Jev pilot audit. The stable
verifier and provider defaults remain unchanged.

The path combines three bounded stages:

1. Select exact spans from the supplied contexts and preserve their context ID,
   offsets, text, and hash.
2. Decompose conservative coordinated predicates or required objects and apply
   deterministic relation rules.
3. When explicitly supplied, use the repository's pinned local NLI backend as
   an auxiliary entailment, contradiction, or neutral signal.

Deterministic code owns numeric conflicts, semantic negation, explicit absence,
universal-versus-qualified language, approximate evidence for exact claims, and
conflicting sources. NLI does not override those policy decisions. Absence of
support becomes `unsupported` only when the selected evidence explicitly says
the asserted detail is unspecified; it is not treated as contradiction.

The optional NLI artifact is never downloaded by verification. Provisioning is
an explicit command documented in
`benchmarks/local_verification_quality/README.md`. Construction fails with an
actionable error when `require_nli=True` and no local backend is supplied. No
weaker backend is silently substituted.

Use the experimental path directly:

```python
from contexttrace.verify.local_quality import (
    LocalQualityProfile,
    verify_trace_local_quality,
)
from contexttrace.verify.semantic_core_v2.nli import build_pinned_nli

nli = build_pinned_nli("/absolute/path/to/the/pinned/model")
result = verify_trace_local_quality(
    trace,
    nli=nli,
    profile=LocalQualityProfile(require_nli=True),
)
```

`truth_status` remains `not_assessed`; a grounded claim is not thereby certified
as true or current. Source condition remains a separate field. Evidence and
atomic diagnostics are copied from actual local inputs and backend outputs; the
pipeline does not generate explanations, evidence spans, or matched facts.

The current evidence supports continued opt-in testing. The untouched synthetic
held-out set contains only 15 author-labeled cases, and the repository has no
qualified independently labeled set for this exact five-way verdict task. Do
not use these results for SOTA or general-superiority claims.
