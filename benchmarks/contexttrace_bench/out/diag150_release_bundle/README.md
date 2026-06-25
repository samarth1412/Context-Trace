# ContextTrace-Diag-150 Release Bundle

Status: `review_pending`
Commit: `a2f44be`
Case set: `public_holdout`
Cases: `150`
Generated: `2026-06-23T21:17:47+00:00`

## Claim Policy

This bundle passed automated validation, but independent human signoff is pending. Use it for reviewer handoff and reproducibility, not frozen-split or broad SOTA claims.

## Headline Metrics

| Metric | Value |
| --- | ---: |
| Failure macro-F1 | 1.000 |
| Claim-verdict macro-F1 | 1.000 |
| Root-cause accuracy | 1.000 |
| Citation error F1 | 1.000 |
| Evidence span overlap | 0.950 |
| Dangerous false-green rate | 0.000 |

## Validation

- Validation status: `passed`
- Human signoff complete: `False`
- Required human signoff: `False`
- Missing required artifacts: `0`

## Artifacts

| File | Bytes | SHA256 | Required |
| --- | ---: | --- | --- |
| `contexttrace_bench_results.json` | 1633673 | `41e46e57ca85f94f3e0e24b1c1ff511aff7747d5915256f39ea256ce92a3d92e` | `True` |
| `results.md` | 2285 | `5f68ecd2d367378ff6b634b6eae6fad0b79fddbcb4e9713d1d9eae7f1658f008` | `True` |
| `leaderboard.md` | 1021 | `21805c5b2305f79b39ad2d7a43fd733a8d295d7ce38ff7253fe588dbd5bbe377` | `True` |
| `report.html` | 72868 | `17d3b95888f40750ab9704de0ef72a51993654974ecd1d580cd5672961ac29d0` | `True` |
| `error_analysis.json` | 1757 | `e49d986f8587cdf1b9eb6a241a6ab82d054c4b070344aa8ada087bd5e79261e5` | `True` |
| `error_analysis.md` | 1156 | `d3c2d1216a0ac2aba75d71eb8cecf2fb90b0429e32fda73c96664ed8977a83a8` | `True` |
| `candidate_inputs.jsonl` | 161612 | `473e0b3bbd31ca434ce81a737bd2b6f5371437b5e1576196d54c7b34a32af46f` | `True` |
| `diag150_audit_packet.json` | 354779 | `cb8e9be08fe45c3d3362888f95055e70e342d10a0cffce489270c3a6cad183a8` | `True` |
| `diag150_audit_packet.md` | 125240 | `c647bc35686dd94b9111699dbc6ad49fa074aac6ba84c1e8b948b0d57e481b12` | `True` |
| `diag150_human_review_template.json` | 45120 | `9bbf16dd8e9cb0170972f5b1179646666da6450e51b0d13fa271cec4268057ca` | `True` |
| `diag150_audit_validation.json` | 2923 | `2bd043fa751f2db4e9754ee0cf228bce5d18a006fd466231e628048d014cd23a` | `True` |
| `AUDIT_REPORT.md` | 3804 | `ac94aead89f1dcacbfdf09d1af89c327d4a8a01ed6c114339d0f9d4e2ca76958` | `True` |
| `baseline_results.json` | 258215 | `c71d4fe895bdc5b19bebda6f61bf32be058009161b898fa8dd089cd110aed4ad` | `False` |
| `openai_diagnostic_judge_predictions.json` | 95141 | `abe10f539da1e412ad2baf2fddde51c798104392bb32649239b079d88d7c9300` | `False` |
| `openai_diagnostic_judge_raw_results.json` | 102839 | `577019f8e04ed901486e0f79aeeac191d27de94c83c08457acb113d7ad6e1577` | `False` |

## Reproduce

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set public_holdout \
  --no-generated-cases \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout
python benchmarks/contexttrace_bench/audit_diag150.py \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout \
  --bundle-dir benchmarks/contexttrace_bench/out/diag150_release_bundle
```
