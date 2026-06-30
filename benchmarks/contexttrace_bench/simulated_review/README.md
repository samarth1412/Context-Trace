# LLM-simulated review pilot

This directory implements a controlled multi-agent stress test for the blinded
annotation and actionability protocols. It is **not human review**, is never
reported as independent validation, and cannot satisfy paper-result or broad
SOTA gates.

The default cloud configuration pins `gpt-4.1-nano-2025-04-14`. Requests use a
strict JSON schema, three role prompts, bounded concurrency, up to three malformed
response retries, and resumable response caches. The API key is read from
`OPENAI_API_KEY` and is never written to an artifact. Ollama is supported as a
no-cost fallback.

```bash
python benchmarks/contexttrace_bench/simulated_review/run_simulated_review.py annotation \
  --dataset ragtruth \
  --packet benchmarks/contexttrace_bench/out/arr_annotation_ragtruth/annotation_packet.json \
  --output-dir benchmarks/contexttrace_bench/out/simulated_review/ragtruth

python benchmarks/contexttrace_bench/simulated_review/run_simulated_review.py annotation \
  --dataset diag150 \
  --packet benchmarks/contexttrace_bench/out/arr_annotation_diag150/annotation_packet.json \
  --output-dir benchmarks/contexttrace_bench/out/simulated_review/diag150

python benchmarks/contexttrace_bench/simulated_review/run_simulated_review.py rq4 \
  --packet benchmarks/contexttrace_bench/out/arr_actionability/actionability_packet.json \
  --key benchmarks/contexttrace_bench/out/arr_actionability/condition_key.private.json \
  --output-dir benchmarks/contexttrace_bench/out/rq4/simulated
```

Score annotation pilots only after inference is complete:

```bash
python benchmarks/contexttrace_bench/simulated_review/score_simulated_review.py annotation \
  --dataset ragtruth \
  --review-dir benchmarks/contexttrace_bench/out/simulated_review/ragtruth \
  --key benchmarks/contexttrace_bench/out/arr_annotation_ragtruth/annotation_key.private.json
```

Private keys are coordinator-only inputs to scoring and condition selection.
They are excluded from prompts, public review files, and anonymous artifacts.
