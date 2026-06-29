# CRAG Validation Track

Status: `calibration_only`, `review_pending`

This track uses Meta's official Comprehensive RAG Benchmark (CRAG) Task 1/2
v5 archive to test ContextTrace against dynamic, multi-domain retrieval inputs.
It is a review workflow, not a publishable verifier leaderboard row yet.

## Frozen Source

- Repository: `facebookresearch/CRAG`
- Commit: `ad1518887dd4d9ebcd7de95388c7a62751e7705c`
- Archive: `crag_task_1_and_2_dev_v5.jsonl.bz2`
- Bytes: `739310088`
- SHA256: `d4c14897d8ea2f450a24e098b595d8247c6575f996f9869d6f27a020fe020618`
- License: CC BY-NC 4.0

Downloaded CRAG data stays under `benchmarks/contexttrace_bench/out/` and is
not committed. The adapter pins and verifies the official archive, so another
machine can reconstruct the same input without storing the 739 MB file in this
repository.

## Label Boundary

CRAG gold answers establish answer correctness at the recorded query time. They
do not establish that the five supplied web pages support every claim in the
gold answer. Those are different labels:

| CRAG concept | ContextTrace concept | Directly comparable? |
| --- | --- | --- |
| Correct / incorrect answer | Failure label | Only after a judged response mapping and grounding review |
| Missing answer | Safe abstention | Related, but CRAG penalizes missing answers while ContextTrace may prefer abstention when evidence is insufficient |
| CRAG score / accuracy | Failure macro-F1 | No |
| Hallucination rate | Dangerous false-green rate | No; denominators and label protocols differ |
| Gold answer | Supported claim | No; correctness does not prove support by retrieved context |
| Web pages | Context evidence | Yes, after deterministic HTML-to-text extraction |

The initial adapter therefore marks every row with
`crag_label_scope=unreviewed_gold_answer_proxy` and
`crag_requires_grounding_review=true`. Point metrics from that proxy measure how
often ContextTrace accepts the assumption that the official gold answer is
grounded by the supplied pages. They must not be presented as failure-detection
accuracy.

## Current Calibration

The pinned archive contains 2,705 eligible Task 1/2 rows after one literal
`nan` answer is excluded. The deterministic sample contains 200 unique IDs:

- Selected-ID SHA256: `a782cf309506e2dff8f3b9c039fd2dc7bbab6f9cc3d98c9238693a1f64a9d80c`
- Domains: all 5 represented
- Question types: all 8 represented, including 25 false-premise rows
- Temporal classes: all 4 represented, including 15 real-time rows
- Splits: 99 validation and 101 public-test rows
- Contexts: 1,000 total, with 511 reaching the disclosed 12,000-character cap

ContextTrace accepts 95/200 gold answers under the proxy assumption and sends
105/200 to grounding review. Acceptance is 0/25 for false-premise answers and
4/15 for real-time answers. These results expose a substantial review and
retrieval-grounding problem; they do not prove 52.5% verifier error. In
particular, the generic harness's failure macro-F1 `0.107` is not a comparable
CRAG accuracy metric because the proxy labels assume every gold answer is fully
grounded.

RAGChecker `0.1.9` was also run on the same 200 IDs with
`openai/gpt-4.1-mini` as both extractor and checker, all 11 metrics enabled,
and the official CRAG answers supplied through a real reference sidecar. It
completed 200/200 rows with zero errors and complete metric coverage. Using the
default candidate thresholds (faithfulness `0.75`, claim recall `0.50`),
RAGChecker proxy-accepts 93 rows and flags 107. The systems agree on 150/200
rows (`75.0%`, Cohen's kappa `0.4982`); exact McNemar p-value is `0.887725`.
Mean RAGChecker faithfulness is `0.5073` and mean claim recall is `0.4903`.
This compares grounding evaluators on official gold-answer responses; it is not
a generated-RAG answer-quality comparison or verifier accuracy.

Tracked aggregate evidence:

- `out/crag_official/crag_task1_v5_adapter_manifest_200.json`
- `out/crag_official/review200/crag_calibration_report.json`
- `out/crag_official/review200/crag_calibration_report.md`
- `out/crag_official/ragchecker/crag_full200_comparison.json`
- `out/crag_official/ragchecker/crag_full200_comparison.md`
- `out/crag_official/review200_ragchecker_bundle/manifest.json`

The full archive, normalized rows, case pack, and reviewer packet remain ignored
under `out/` because they contain CC BY-NC CRAG data. They are reproducible from
the frozen source and commands below.

## Reproduce

Normalize a deterministic 200-row sample balanced by domain, question type,
temporal dynamics, and split:

```bash
python benchmarks/contexttrace_bench/crag_adapter.py \
  --download-official \
  --download-dir benchmarks/contexttrace_bench/out/crag_official \
  --output benchmarks/contexttrace_bench/out/crag_official/crag_task1_v5_rows_200.jsonl \
  --manifest-output benchmarks/contexttrace_bench/out/crag_official/crag_task1_v5_adapter_manifest_200.json \
  --ragchecker-reference-output benchmarks/contexttrace_bench/out/crag_official/crag_task1_v5_ragchecker_references_200.jsonl \
  --sample-size 200 \
  --sample-seed 13 \
  --stratify-by domain,question_type,static_or_dynamic,split \
  --max-pages 5 \
  --context-char-limit 12000
```

The adapter performs deterministic two-pass sampling directly over compressed
JSONL, removes script/style/template content, emits visible page text, rejects
duplicate IDs and missing-value answer sentinels, and records all extraction and
sampling parameters in its manifest.

Create the calibration report and independent-review packet:

```bash
python benchmarks/contexttrace_bench/external_case_pack_workflow.py \
  --input benchmarks/contexttrace_bench/out/crag_official/crag_task1_v5_rows_200.jsonl \
  --dataset CRAG-Task1-v5 \
  --source-name "CRAG Task 1 v5" \
  --output-dir benchmarks/contexttrace_bench/out/crag_official/review200 \
  --bundle-dir benchmarks/contexttrace_bench/out/crag_official/review200_bundle \
  --bootstrap-samples 100 \
  --no-auto-candidates
```

Render CRAG-specific proxy statistics without relabeling them as verifier
failure accuracy:

```bash
python benchmarks/contexttrace_bench/crag_calibration_report.py \
  --results benchmarks/contexttrace_bench/out/crag_official/review200/scored/contexttrace_bench_results.json \
  --output-json benchmarks/contexttrace_bench/out/crag_official/review200/crag_calibration_report.json \
  --output-markdown benchmarks/contexttrace_bench/out/crag_official/review200/crag_calibration_report.md
```

Run RAGChecker against the same IDs and real CRAG reference sidecar from an
isolated Python 3.11 environment:

```powershell
$ragcheckerVenv = Join-Path $env:TEMP "contexttrace-ragchecker-crag"
py -3.11 -m venv $ragcheckerVenv
& "$ragcheckerVenv\Scripts\python.exe" -m pip install -r benchmarks/contexttrace_bench/requirements-ragchecker.txt
& "$ragcheckerVenv\Scripts\python.exe" -m spacy download en_core_web_sm
& "$ragcheckerVenv\Scripts\python.exe" benchmarks/contexttrace_bench/run_ragchecker.py `
  --input benchmarks/contexttrace_bench/out/crag_official/review200/scored/candidate_inputs.jsonl `
  --reference-file benchmarks/contexttrace_bench/out/crag_official/crag_task1_v5_ragchecker_references_200.jsonl `
  --reference-id-field id `
  --reference-answer-field gt_answer `
  --ragchecker-input-output benchmarks/contexttrace_bench/out/crag_official/ragchecker/crag_full200_input.json `
  --raw-output benchmarks/contexttrace_bench/out/crag_official/ragchecker/crag_full200_raw_results.json `
  --candidate-output benchmarks/contexttrace_bench/out/crag_official/ragchecker/crag_full200_predictions.json `
  --extractor-name openai/gpt-4.1-mini `
  --checker-name openai/gpt-4.1-mini `
  --metrics all_metrics `
  --chunk-size 10 `
  --resume
```

Render the fail-closed same-ID comparison:

```bash
python benchmarks/contexttrace_bench/crag_ragchecker_report.py \
  --contexttrace-results benchmarks/contexttrace_bench/out/crag_official/review200/scored/contexttrace_bench_results.json \
  --ragchecker-candidate benchmarks/contexttrace_bench/out/crag_official/ragchecker/crag_full200_predictions.json \
  --ragchecker-raw benchmarks/contexttrace_bench/out/crag_official/ragchecker/crag_full200_raw_results.json \
  --output-json benchmarks/contexttrace_bench/out/crag_official/ragchecker/crag_full200_comparison.json \
  --output-markdown benchmarks/contexttrace_bench/out/crag_official/ragchecker/crag_full200_comparison.md
```

After an independent reviewer validates answer grounding and corrects labels or
source spans, rerun with:

```bash
python benchmarks/contexttrace_bench/external_case_pack_workflow.py \
  --input benchmarks/contexttrace_bench/out/crag_official/crag_task1_v5_rows_200.jsonl \
  --dataset CRAG-Task1-v5 \
  --source-name "CRAG Task 1 v5" \
  --output-dir benchmarks/contexttrace_bench/out/crag_official/review200 \
  --bundle-dir benchmarks/contexttrace_bench/out/crag_official/review200_bundle \
  --review benchmarks/contexttrace_bench/out/crag_official/review200/external_review_completed.jsonl \
  --review-kind independent \
  --bootstrap-samples 100 \
  --no-auto-candidates
```

## Limitations

- The unreviewed proxy starts from official gold answers, not generated RAG
  responses with official CRAG correctness judgments.
- Visible page text is capped at 12,000 characters per page. The manifest makes
  this explicit; evidence beyond the cap can create legitimate ContextTrace
  abstentions.
- CRAG's query-time and dynamic-fact labels are preserved as metadata but do not
  automatically alter ContextTrace's verification policy.
- Evidence-span metrics remain `N/A` until source spans are independently
  reviewed.
- Competitor rows must use the same sampled IDs and the same extracted contexts.
- The CC BY-NC 4.0 dataset license applies to downloaded and derived CRAG data.
