# Second confirmation execution log

The initial frozen execution under manifest
`confirmation_v2_freeze_manifest_preflight_failed.json` stopped after the first
API response. The runner indexed the development-only field
`development_partition`, which is absent from held-out cases, and raised a
`KeyError` before appending or writing a result row. No prediction was printed,
persisted, scored, or inspected. The request used the same frozen claim,
selected evidence, model, and typed questions as the subsequent run.

The only code change made after that failure allows the field to be absent and
records it as `null`. Tests were rerun and a new manifest was frozen before the
held-out execution restarted. No policy, coefficient, threshold, case, label,
or model input changed.
