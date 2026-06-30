# ARR readiness

Status date: 2026-06-29. Target: ARR August 2026 submission on August 3, with
October 12 as the lower-risk fallback. Confirm dates on the official
[ARR dates page](https://aclrollingreview.org/dates) before submission.

## Readiness summary

| Area | Completion | Status | Blocking evidence |
| --- | ---: | --- | --- |
| Product and SDK | 95% | release-capable | none for a product release |
| Reproducible experiment pipeline | 95% | full run complete | independent rerun is still desirable |
| Benchmark and ablation implementation | 90% | 9 executable and 2 unavailable registered variants | pin models before enabling NLI-only or judge-only |
| Paper and artifact structure | 85% | skeleton, tables, and figures generated | final ACL render and anonymous package audit |
| Empirical validity | 65% | frozen pre-review evidence | independent RAGTruth and Diag-150 review |
| RQ4 actionability evidence | 35% | protocol and packet complete | at least three non-author reviewers have not responded |
| Broad SOTA claim | 0% | prohibited | fail-closed gate is 8/11, so the binary claim is not allowed |

The implementation plan is about 85% complete once the anonymous artifact and
full test suite are regenerated. ARR evidence readiness is about 70%. Those
numbers must not be conflated: code completion cannot substitute for independent
review or a human study.

## Completed evidence

- `python benchmarks/contexttrace_bench/reproduce_arr_tables.py --full` completed
  from commit `15cf09f9f9d7bfdd6285dae2603edad12d8a3ff9`.
- The run contains 150 Diag cases, 200 RAGTruth cases, 200 same-ID baseline
  cases, and 500 cases per executable ablation profile.
- Six TeX tables and six Markdown mirrors are generated from the tracked frozen
  snapshot.
- Four figure sources and a 13-section anonymous paper skeleton are present.
- The broad-claim gate fails closed at 8/11 rather than treating scored but
  review-pending evidence as publishable.

## Critical path

1. Send the Diag-150 and RAGTruth reviewer bundles to independent reviewers now.
2. Run the preregistered 40-case RQ4 study with at least three non-author
   reviewers; preserve every response and disagreement.
3. Apply accepted review corrections through the versioned review workflow,
   rerun the full experiment, and regenerate all tables.
4. Complete argumentation, related-work citations, statistical analysis, and
   the official ACL-format render.
5. Run the anonymous artifact identity scan and submission checklist against the
   exact final commit.

August 3 is feasible only if reviewer recruitment starts immediately and the
reviews do not force material benchmark redesign. October 12 is the safer target
if independent evidence is not complete by mid-July.

## Commands

```bash
python benchmarks/contexttrace_bench/reproduce_arr_tables.py --full
python paper/generate_tables.py
python benchmarks/contexttrace_bench/sota_gate.py --allow-not-ready
python -m pytest
```

ARR long-paper limits, anonymization, mandatory limitations, and supplementary
material rules must be checked against the official
[ARR call for papers](https://aclrollingreview.org/cfp) at final submission.
