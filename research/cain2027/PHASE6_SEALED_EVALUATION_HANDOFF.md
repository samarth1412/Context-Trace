# ContextTrace CAIN 2027 Phase 6 sealed-evaluation handoff

Status: tooling implemented and tested on synthetic fixtures only
Untouched candidate execution: not authorized and not run
Sealed scoring: not run

## Separation of duties

The implementation team may run the candidate verifier only after a dedicated
Phase 6 authorization record is created. The candidate runner has no gold-label
argument and emits unscored predictions.

The label custodian runs the scorer inside the private label zone. The scorer
joins immutable candidate and predecessor outputs to sealed gold. The
implementation team must never receive `private-scoring-detail.json`, the gold
file, annotation files, adjudication records, case-level errors, or the label
zone path.

The custodian may return only:

- `aggregate-metrics.json`;
- its SHA-256;
- a signed execution receipt containing commands, input hashes, environment,
  timestamps, exit codes, and deviations, without labels or case examples.

## Gate 1: implementation-team candidate run

Required immutable inputs:

| Input | Frozen identity |
| --- | --- |
| Dataset | `ContextTrace-Unseen-v1` |
| Cases | 493 |
| Manifest payload | `8bf65cd7e2c95ccfcc12e78b580fc47e4157b0f808ba3fcace0a24bfcdc2e5f6` |
| Manifest file | `6b1b48ed4ed8bc9b4966b9218b77406b2d925ae1b6d8991f630726415c5c01e4` |
| Source-manifest file | `794603f6287445cefad2893d091f325b2c2da6acf24028fe702a75fe91712ccc` |
| Candidate implementation | `0abd8c25ad417ee0ac84e04ae0989dd9066fdbe3390d323875bf483e14cb4d70` |
| NLI artifact manifest | `330f0fd77aad129877e1a1a90d4a77e6f093ee238b97d535202816a116b9c9f3` |
| Evaluation config payload | `ed6be19ec12570f189c9c5999ac2e777d4b68b0f6fa9cf237281dd74ed726441` |
| Ablation config payload | `15ddb5b471af8385b75edfa282e39c8a080dd6af6df461b43613f0c5a1e89880` |

The authorization JSON must contain:

```json
{
  "schema_version": "1.0",
  "record_kind": "contexttrace_cain2027_phase6_execution_authorization",
  "authorized": true,
  "one_time_sealed_run": true,
  "dataset_id": "ContextTrace-Unseen-v1",
  "manifest_payload_sha256": "8bf65cd7e2c95ccfcc12e78b580fc47e4157b0f808ba3fcace0a24bfcdc2e5f6",
  "source_manifest_file_sha256": "794603f6287445cefad2893d091f325b2c2da6acf24028fe702a75fe91712ccc",
  "case_count": 493,
  "implementation_source_manifest_sha256": "0abd8c25ad417ee0ac84e04ae0989dd9066fdbe3390d323875bf483e14cb4d70",
  "candidate_profile_sha256": "036b8d1c02c101aceb00ee3fee67dda60d58c9dfece09ab524832ae164057511",
  "ablation_config_payload_sha256": "15ddb5b471af8385b75edfa282e39c8a080dd6af6df461b43613f0c5a1e89880",
  "authorized_by": "USER-SUPPLIED-IDENTIFIER",
  "authorized_at": "USER-SUPPLIED-UTC-TIMESTAMP",
  "authorization_statement": "USER-SUPPLIED-EXACT-STATEMENT",
  "payload_sha256": "CANONICAL-SHA256-OF-ALL-PRECEDING-FIELDS"
}
```

Do not treat this example as authorization. A fresh user statement and a
hash-valid record are required.

After authorization, execute from the repository root with the frozen
environment:

```bash
.venv/bin/python -m benchmarks.contexttrace_unseen_v1.evaluation.candidate_runner \
  --repository-root . \
  --manifest .tmp-contexttrace-unseen-v1-two-track-freeze/contexttrace_unseen_v1_frozen_unlabeled.json \
  --artifact-root .tmp-contexttrace-unseen-v1-two-track-freeze \
  --source-manifest .tmp-contexttrace-unseen-v1-two-track-freeze/combined_source_manifest.json \
  --model-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --authorization PRIVATE-PHASE6-AUTHORIZATION.json \
  --output .tmp-contexttrace-unseen-v1-phase6-candidate/raw-output.json
```

Preserve the command, stdout, stderr, exit status, start/end times, output file
hash, and output file bytes before copying the raw output to the custodian.
Never open or summarize the per-case predictions before sealed scoring.

## Gate 2: custodian scoring

SAR verifies the candidate-output hash received through an authenticated
channel, verifies the already frozen predecessor hash, and independently
records the sealed-gold hash. Inside the private label zone, SAR runs:

```bash
python -m benchmarks.contexttrace_unseen_v1.evaluation.sealed_scorer \
  --repository-root /PATH/TO/HASH-VERIFIED-CONTEXTTRACE \
  --manifest /PRIVATE/UNLABELED/contexttrace_unseen_v1_frozen_unlabeled.json \
  --artifact-root /PRIVATE/UNLABELED \
  --candidate-run /PRIVATE/INPUTS/semantic-core-v2-raw-output.json \
  --candidate-run-sha256 CANDIDATE-RUN-FILE-SHA256 \
  --v1-run /PRIVATE/INPUTS/semantic-v1-calibrated-raw-output.json \
  --v1-run-sha256 c80b2f3bcd9e0806b627b480398d8d536fb6f94ed86de6c3c87eaf0abb752064 \
  --gold /PRIVATE/LABELS/sealed-gold.json \
  --gold-sha256 SAR-RECORDED-SEALED-GOLD-FILE-SHA256 \
  --output-directory /PRIVATE/RESULTS/contexttrace-unseen-v1-phase6 \
  --confirm-sealed-zone I_AM_THE_LABEL_CUSTODIAN_IN_THE_PRIVATE_LABEL_ZONE
```

The production scorer refuses any bootstrap count other than 10,000 and any
paired-randomization count other than 100,000. It refuses an existing output
directory to prevent overwrite.

## Defect and deviation rule

If any hash, schema, case set, environment, or runtime check fails, stop. Keep
the failed attempt, logs, and outputs immutable. Do not repair predictions,
change labels, substitute a source, rerun selected cases, tune a threshold, or
inspect results to decide what to change.

A mechanical tooling defect requires a dated deviation record, preservation of
the invalid run, a source-only correction whose scope is documented, a new
tooling lock, and an explicit decision on whether confirmatory status remains
valid before any rerun.
