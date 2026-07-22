# Public artifact schemas

ContextTrace packages JSON Schema Draft 2020-12 contracts for `TraceV1`,
`ClaimVerificationV1`, `DiagnosisV1`, `RepairPlanV1`, and `RegressionCaseV1`.
Load them without relying on repository paths:

```python
from contexttrace import load_json_schema

schema = load_json_schema("ClaimVerificationV1")
```

Every emitted artifact includes `schema_version`, `taxonomy_version`,
`verifier_version`, and `profile_id`. Readers should reject unsupported major
schema versions and record all four fields with benchmark results. The current
compatibility verifier is `semantic_v1_calibrated`; its identifier explicitly
signals that repository and RAGTruth scores are calibration evidence.
