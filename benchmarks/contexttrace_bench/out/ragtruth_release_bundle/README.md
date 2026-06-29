# RAGTruth Release Bundle

Status: `calibration_only`
Workflow status: `scored`
Cases: `200`
Review kind: `assisted`
Generated: `2026-06-29T14:58:25+00:00`

## Claim Policy

This RAGTruth bundle is useful for calibration, but it is not publishable external validation. Reasons can include assisted review or intentionally missing source-side spans.

## Score Summary

| Metric | Value |
| --- | ---: |
| Failure macro-F1 | 0.955 |
| Root-cause accuracy | 0.955 |
| Citation error F1 | 1.000 |
| Evidence span overlap | 0.786 |
| Dangerous false-green rate | 0.000 |

## Artifacts

| File | Bytes | SHA256 | Required |
| --- | ---: | --- | --- |
| `ragtruth_workflow_manifest.json` | 4299 | `9da1bd915c532aa4cb2fcd8ed7525045efe9585c91b6fa9a1ba5cbb97e243c64` | `True` |
| `ragtruth_case_pack.json` | 1321687 | `85fc631840a830919e940efca9369cdf4375b35a18c6413a324ea13bce1c5a96` | `True` |
| `ragtruth_review_queue.jsonl` | 732371 | `b5feb96a32d2a2e821d3bd397c409a372ed9ec72fa8f41415012e6d8e9d73a09` | `True` |
| `ragtruth_review_packet.md` | 708289 | `f50acc09d980a15cea943f2c4a6fc1995302e145c052228f7048c9d69008538e` | `True` |
| `ragtruth_review_signoff.jsonl` | 794674 | `3a9ef16f1b65d1a2bde8bd271720c45c9cb51f65491d9c164dc97081ac661297` | `True` |
| `ragtruth_review_validation.json` | 20846 | `58a25bd33f985366a6ccdfa6c36f8c975b9b2d44a898a3296519f8c585f9b901` | `True` |
| `ragtruth_reviewed_case_pack.json` | 1398575 | `19294b50661931ae2f0d4e3c95d18c3220e52a021f5f0289fe459c760986ceaa` | `True` |
| `scored/contexttrace_bench_results.json` | 22442678 | `17792f2091e88238e051ada8bb7b0bbf3c00c8a390a5f2e1fd51c404a9975e80` | `True` |
| `scored/results.md` | 4673 | `1dd74caa4a66b7498cae76b21616b41e46fc69323bec86a3d8185cf5db276a7d` | `True` |
| `scored/leaderboard.md` | 1007 | `e2d9133f128db28512c50044ad5a3e49b5150c2b0dba5c9eeb5c474365fe1f62` | `True` |
| `scored/report.html` | 142789 | `bfc1de4a3e5974708b838818e924f8374d8e5590b74fd1c81c7a2db6c42fe62b` | `True` |
| `scored/error_analysis.json` | 15771 | `b04be38e3ae3b3f9e0b77262e43de4f07762a5e219242911b23fa65db4188fbe` | `True` |
| `scored/error_analysis.md` | 4915 | `96f3dafabfb20f29e6adc9b5214bfc8df9fc8893624da8ef65a6b18f06582e6f` | `True` |
| `scored/ragtruth_error_analysis.json` | 41104 | `d01400dd350b51c9a4bd4dcf0f213466a5c0bbb72717ab3c65546bc1af5dbf2d` | `True` |
| `scored/ragtruth_error_analysis.md` | 6938 | `16c7a373f28b75d241e532cce336c27e7b392177059c6eb6aab5bd94e96bbdec` | `True` |
| `scored/candidate_inputs.jsonl` | 1164092 | `f682aae7b20962d776738dc7a03391c208fcf91130dc55c85b054041a7736d12` | `True` |
| `scored/baseline_results.json` | 269588 | `5626cffed3f91de1a7a0ced1eb03a3cd8cca4849c18bb2d54258e11a576940fa` | `True` |
| `candidates/ragas_predictions.json` | 65764 | `85c39ffaed7d8be59a19af8e446692706963e37832a4e30021286029356404de` | `False` |
