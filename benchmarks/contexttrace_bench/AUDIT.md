# ContextTrace-Diag-150 Human Audit Checklist

Use this checklist before calling `public_holdout` a frozen public diagnostic
split. The goal is to verify label quality, source grounding, and reproducible
reporting, not to tune the verifier. The automated audit report is tracked in
[AUDIT_REPORT.md](AUDIT_REPORT.md).

## Case Source Audit

- Every case ID is unique and stable.
- Every `source_url` opens to the referenced public documentation or project page.
- Every context excerpt is copied from, or tightly paraphrases, the cited source.
- Source families are balanced enough that no single vendor or framework
  dominates the split.
- Each case has no expected labels or answers leaked into `candidate_inputs.jsonl`.

## Label Audit

- `no_failure_detected` cases have all material answer claims directly supported.
- `partial_support` cases contain at least one supported material claim and at
  least one unsupported, unverifiable, or overreaching material claim.
- `contradicted_answer` cases contain an explicit conflict with retrieved context,
  such as negation, incompatible numbers, incompatible dates, or reversed support.
- `citation_mismatch` cases have a supported answer claim but cite a source that
  does not support that specific claim.
- `should_have_abstained` is used only when the answer should not be accepted
  from the retrieved context.
- Expected claim-verdict counts match the actual atomic claims emitted by the
  benchmark claim splitter.

## Diagnostic Audit

- Expected primary root causes match the product taxonomy:
  `no_failure_detected`, `answer_overreach`, `conflicting_contexts`,
  `wrong_source_cited`, `missing_cited_source`, or `should_have_abstained`.
- Expected citation statuses distinguish `citation_ok`,
  `cited_source_does_not_support_claim`, `claim_supported_by_different_source`,
  and `cited_source_missing`.
- Expected evidence spans point to the minimum source text needed to justify the
  label.
- One canonical expected evidence span is used for multi-context cases unless
  multiple spans are required by claim splitting.

## Reproducibility Audit

- Regenerate the holdout artifacts with:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set public_holdout \
  --no-generated-cases \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout
```

- Generate the machine-checkable audit packet and validator output:

```bash
python benchmarks/contexttrace_bench/audit_diag150.py \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout
```

This writes:

- `diag150_audit_packet.json`
- `diag150_audit_packet.md`
- `diag150_audit_validation.json`
- `AUDIT_REPORT.md`

Use `diag150_audit_packet.md` for case-by-case human review and keep
`diag150_audit_validation.json` with the benchmark artifacts.

- Rerun the OpenAI diagnostic judge or clearly mark the row stale.
- Confirm `leaderboard.md`, `results.md`, `report.html`,
  `contexttrace_bench_results.json`, `error_analysis.md`,
  `error_analysis.json`, and `baseline_results.json` agree on case counts,
  headline metrics, and miss/confusion counts.
- Confirm diagnostic coverage tables show missing fields as coverage counts or
  `N/A`, not as attempted failures.
- Record reviewer, date, command SHA, and any changed labels.

## Audit Log

| Date | Reviewer | Scope | Result | Notes |
| --- | --- | --- | --- | --- |
| 2026-06-11 | Codex automated audit | Structure, source URL reachability, candidate-input leakage, metric consistency | Passed | See [AUDIT_REPORT.md](AUDIT_REPORT.md). Human source/label/span review still required. |
| 2026-06-11 | Codex assisted source review | Source excerpt exact/fuzzy matching and review of weak matches | Passed with limitations | No machine-actionable source, label, or span blockers found. Not independent human sign-off. |
| Pending | Pending | 150-case source, label, diagnostic, and artifact audit | Pending | Required before frozen-split claim. |
