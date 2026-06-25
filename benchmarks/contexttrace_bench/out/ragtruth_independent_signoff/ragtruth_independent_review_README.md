# RAGTruth Independent Review Handoff

Status: `pending_independent_review`
Generated: `2026-06-25T00:50:58+00:00`
Review rows: `88`

## Files

- Signoff template: `benchmarks\contexttrace_bench\out\ragtruth_independent_signoff\ragtruth_independent_review_template.jsonl`
- Review packet: `benchmarks\contexttrace_bench\out\ragtruth_independent_signoff\ragtruth_independent_review_packet.md`
- Status JSON: `benchmarks\contexttrace_bench\out\ragtruth_independent_signoff\ragtruth_independent_review_status.json`

## Reviewer Rules

- Fill `review_status`, `reviewer`, and `reviewed_at` only after direct source inspection.
- Copy minimal source text into `source_evidence_spans` when source text supports, contradicts, or bounds the labeled answer span.
- Leave `source_evidence_spans` empty only when no fair source-side span exists, and explain why in `review_notes`.
- Use `taxonomy_override` only when the adapted expected label, root cause, or verdict counts need correction.

## Commands

Validate completed independent review:

```bash
python benchmarks/contexttrace_bench/ragtruth_review.py validate --case-pack benchmarks\contexttrace_bench\out\ragtruth_release_bundle\ragtruth_case_pack.json --review benchmarks\contexttrace_bench\out\ragtruth_independent_signoff\ragtruth_independent_review_template.jsonl --output benchmarks\contexttrace_bench\out\ragtruth_independent_signoff\ragtruth_independent_review_validation.json --require-reviewed
```

Strict validation when every hallucination row must have a source span:

```bash
python benchmarks/contexttrace_bench/ragtruth_review.py validate --case-pack benchmarks\contexttrace_bench\out\ragtruth_release_bundle\ragtruth_case_pack.json --review benchmarks\contexttrace_bench\out\ragtruth_independent_signoff\ragtruth_independent_review_template.jsonl --output benchmarks\contexttrace_bench\out\ragtruth_independent_signoff\ragtruth_independent_review_validation.json --require-reviewed --require-source-spans
```

Apply completed review to the case pack:

```bash
python benchmarks/contexttrace_bench/ragtruth_review.py apply --case-pack benchmarks\contexttrace_bench\out\ragtruth_release_bundle\ragtruth_case_pack.json --review benchmarks\contexttrace_bench\out\ragtruth_independent_signoff\ragtruth_independent_review_template.jsonl --output benchmarks\contexttrace_bench\out\ragtruth_independent_signoff\ragtruth_independent_reviewed_case_pack.json --require-reviewed
```
