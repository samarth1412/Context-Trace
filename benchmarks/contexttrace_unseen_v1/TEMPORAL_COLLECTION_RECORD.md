# ContextTrace-Unseen-v1 temporal collection record

Record version: 1.0

Executed: 2026-07-26

Status: complete, structurally valid, private, and unlabeled

## Authorized lock

The run executed only temporal generation schedule SHA-256
`b6250401aadaaf913d7a8e9a5f095d2816cb798f9d512340d0702b8bb233340d`
under the exact authorization in `TEMPORAL_RUN_AUTHORIZATION.md` and
`temporal_run_authorization.json`.

Preflight revalidated all 37 retained source artifacts, all 20 source pairs,
the frozen questions and configurations, the schedule sidecar, pinned Python
and package versions, the pinned Ollama manifest and weight, hosted-key
presence, privacy boundaries, and the USD 3 hard guard before the first
answer call.

## Outcome

| Field | Recorded value |
| --- | --- |
| Frozen answer slots | 100 |
| Completed cases | 100 |
| Structural collection failures | 0 |
| Local answer attempts | 50 |
| Hosted answer attempts | 50 |
| Transport retries | 0 |
| Non-answer model attempts | 0 |
| Hosted charged cost | USD 0.03685225 |
| Hard ceiling | USD 3.00 |
| Query-authoring calls | 0 |
| Verifier or NLI calls | 0 |
| Annotation or label access | none |
| Evaluation | not performed |
| Publication or release | not performed |

Every answer and transport record was retained unedited. The collector made no
semantic eligibility decision and did not inspect system results for
correctness, failure type, or research metrics.

## Private artifact chain

The output root is
`.tmp-contexttrace-unseen-v1-temporal-collection`, is mode `0700`, is ignored
by Git, and contains the unedited responses, traces, state records, budget
ledger, structural validation, and private unlabeled freeze. It contained 374
files and occupied approximately 33 MiB when this record was created.

| Private artifact | SHA-256 |
| --- | --- |
| Candidate case manifest | `e7b106530417f111148e4bda57dc55623cecc046b676b74be5f8109358525e7a` |
| Preflight record | `67f041bc7115906baca3fc2c900d51a379768d8bf92f21abd838470ef69986d8` |
| Hosted budget ledger | `390cf15f34971e0811f1cd58bd0411bf1d720556da3df216af531ebc22f41013` |
| Collection validation | `fa31287d921d6ab2eb9111d24761324ffb4af9428580e032bc5c60f7c2280a11` |
| Frozen temporal unlabeled manifest | `2d6fefc158c584a04fb484e16ee283faaa44926f1d9cc5968e5bd83a269cba91` |

The private frozen manifest was created at
`2026-07-26T20:51:52.201196Z`. Its hash binds the schedule, candidate
manifest, preflight record, budget ledger, and structural validation summary.
It contains no labels, verifier outputs, NLI outputs, or evaluation results.

## Scope boundary after collection

This record does not authorize annotation, evaluation, publication, release,
source substitution, query editing, verifier calls, or NLI calls. The Natural
OOD and temporal private manifests must next be composed and independently
retained as the complete two-track unlabeled freeze before any label access.
