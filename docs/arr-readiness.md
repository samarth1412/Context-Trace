# ARR readiness

Status date: 2026-06-30. Target: ARR August 2026 submission on August 3, with
October 12 as the lower-risk fallback. Confirm dates on the official
[ARR dates page](https://aclrollingreview.org/dates) before submission.

## Readiness summary

| Area | Completion | Status | Blocking evidence |
| --- | ---: | --- | --- |
| Product and SDK | 98% | release-capable | none for a product release |
| Reproducible experiment pipeline | 98% | original and post-simulated-review full runs complete | independent rerun remains desirable |
| Benchmark and ablation implementation | 95% | 9 executable and 2 explicitly unavailable variants | pin models before enabling NLI-only or judge-only |
| Paper and artifact structure | 95% | complete official-style 8-page build and anonymous artifact | final post-human-review refresh |
| Empirical validity | 70% | frozen evidence plus simulated stress test | independent RAGTruth and Diag-150 review |
| RQ4 actionability evidence | 55% | protocol and 360-judgment simulated pilot complete | three non-author human reviewers have not responded |
| Broad SOTA claim | 0% | prohibited | fail-closed gate is 8/11, so the binary claim is not allowed |

The implementation plan is about 96% complete. ARR submission readiness is
about 90%, with the remaining work concentrated in human evidence rather than
software. Those
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
- Three controlled simulated-review agents completed 1,410/1,410 judgments with
  zero parse failures for an estimated $0.296. They suggested 214 unapplied
  corrections and exposed substantial RAGTruth disagreement.
- The simulated RQ4 evidence-chain setting improved root-cause accuracy but
  reduced mean actionability, so the registered positive proxy claim is not supported.
- The official ACL-style manuscript compiles to eight pages; the conservative
  content count is seven of eight pages and the release-surface anonymity audit passes.

## Critical path

1. Send the Diag-150 and RAGTruth reviewer bundles to independent reviewers now.
2. Run the preregistered 40-case RQ4 study with at least three non-author
   reviewers; preserve every response and disagreement.
3. Apply accepted human review corrections through the versioned review workflow,
   rerun the full experiment, and regenerate all tables.
4. Replace simulated-pilot caveats and N/A human cells only where completed
   human evidence supports doing so.
5. Regenerate the official PDF and anonymous artifact from the exact final commit.

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
