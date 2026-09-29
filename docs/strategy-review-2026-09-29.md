# ContextTrace: purpose, shipped product, and next direction

Reviewed on 2026-09-29. Recommendation: retain ContextTrace, pause the broad
verifier race, and focus the next product increment on evidence lost during
retrieval/context transformations. Keep a separate, bounded research question.
This is a strategy recommendation, not a changed release gate or authorization
to promote an experimental verifier.

## Original purpose and constraints

The repository's written thesis is that grounding in a supplied source does not
establish truth, freshness, or authority. ContextTrace preserves the path from
query to retrieval, selected evidence, claims, citations, diagnosis, repair, and
regression prevention. Its public package describes the same purpose.
[Public package description](https://pypi.org/project/contexttrace/).

The durable constraints are local-first operation, an installation usable
without paid APIs, offline verification after explicit optional provisioning,
inspectable evidence provenance, and user-owned development. Jev can remain
an optional research comparator; it is not a required default. Preserve the
existing separation of support, source condition, and independently assessed
truth. Do not infer a causal root cause from a score alone.

## What is actually shipped

Live registry JSON confirms **1.2.0**, uploaded on September 15, 2026. GitHub
also lists a published v1.2.0 release. The initially indexed PyPI HTML was stale;
the direct registry request resolved that discrepancy. Some local release notes
still call 1.2.0 unpublished and need reconciliation.
[PyPI metadata](https://pypi.org/pypi/contexttrace/json),
[GitHub release](https://github.com/samarth1412/Context-Trace/releases/tag/v1.2.0).

The public wheel was downloaded without installation/execution, checked against
the registry SHA-256, and compared with the clean research worktree at `cf07754`.
All **116 files under its `contexttrace/` package are byte-identical** to their
worktree counterparts. The only additional package files are
`verify/local_quality.py` and `verify/atomic_coverage.py`, both experimental.
This comparison excludes distribution metadata, repository examples, and docs.
Details and member hashes are in
[`audits/strategy-review-2026-09-29.json`](audits/strategy-review-2026-09-29.json).

| Area | What exists | Meaning for the next release |
|---|---|---|
| Capture and storage | SDK/CLI, portable traces, local SQLite, endpoint capture | Existing product foundation |
| Evidence inspection | Claims, selected spans, citations, source status and corpus audit | Existing diagnostics; limits remain |
| Repair and regression | Repair plans, baseline/current comparison, saved suites and CI examples | Already a user workflow; do not announce it as a new 1.3 invention |
| Integrations and privacy | LangChain, LlamaIndex, LangGraph, FastAPI, OTel exporter; redaction and local-only controls | Reuse and validate compatibility |
| Experimental verification | v2.1/hybrid paths already packaged; two extra local experimental modules in the worktree | Explicit opt-in does not establish a quality improvement |
| Research infrastructure | Pinned baselines, input/label hashes, offline scorers, failed screens, annotation proposals | Useful research assets, not a shipping justification |

The original workspace is on a different branch with **323 Git status entries**.
Twenty published package files differ there, and three additional modules are
present, including an untracked Jev provider. Those are byte differences, not
20 confirmed new features. Their ownership, semantic deltas, and readiness need
reconciliation before a release. This review changed none of that workspace.
Do not merge the dirty workspace wholesale or assume its release state matches
the isolated research worktree.

Checks rerun for this review: six fictional offline investigations, 12 traces,
24 assertions, all passing; the LangChain and LlamaIndex capture-to-gate examples
also passed. The latter use compatible mock objects, not newly exercised live
framework versions. These checks demonstrate working workflows, not natural
traffic accuracy or a new full release validation.

## What the experiments tell us

The recent work followed real failures, but successive verifier experiments
became the main milestone while evaluation validity remained unresolved.
The candidate's 11% safe support recall and 78% pooled review recall describe
a research benchmark; they do not summarize every capability in the installed
library. The stable default was preserved throughout.

V25 found a concrete evidence-selection defect: 32/400 AVeriTeC cases retained
questions without answers. Restoring already-selected QA records improved
direct macro-F1 from 0.5213 to 0.5840. That is an input ablation on development
data. It provides a more concrete engineering lead than another confidence
threshold sweep.

V26's small recall gain increased false supports and was unstable across fold
selection. V27's appended pretrained NLI signals changed no verdicts. The first
100 label proposals include 50 disagreements but are not adjudicated gold.
The remaining 400 reviews should not become an automatic release blocker for
an unrelated product feature; first decide whether that exact dataset serves
the narrowed research question. Preserve all snapshots and their provenance.
[Detailed diagnosis](../benchmarks/requirement_alignment/V26_V27_RECALL_DIAGNOSIS.md).

## Current landscape and implications

This is a targeted primary-source screen, not an exhaustive systematic review
or a same-input performance comparison. Product documentation establishes
advertised capability; research results remain specific to their own tasks.

| Area | Verified evidence as of this review | Implication for ContextTrace |
|---|---|---|
| Tracing and evaluation platforms | Langfuse combines tracing, datasets, experiments and evaluators; Phoenix provides a similar workflow and supports local SQLite deployment. [Langfuse](https://langfuse.com/docs), [Phoenix workflow](https://arize.com/docs/phoenix/get-started), [Phoenix local storage](https://arize.com/docs/phoenix/self-hosting/architecture) | Local hosting, tracing, and evaluation alone are insufficient differentiation. Favor a focused workflow and interoperability. |
| Fine-grained RAG evaluation | RAGChecker already diagnoses retrieval/generation using fine-grained metrics. Q-CARE's 2026 paper combines query coverage and claim verifiability; its authors report COLM 2026 acceptance. [RAGChecker](https://proceedings.neurips.cc/paper_files/paper/2024/hash/27245589131d17368cccdfa990cbf16e-Abstract.html), [Q-CARE](https://arxiv.org/abs/2608.11238) | Claim decomposition and fine-grained evaluation are established baselines, not sufficient new-paper contributions. |
| Local span verification | LettuceDetect's June 2026 release added code/tool-output models and typed spans; its repository includes local encoder models. [Official repository](https://github.com/KRLabsOrg/LettuceDetect) | Local/offline checking and evidence spans do not by themselves distinguish our verifier. Evaluate suitable existing components before training a replacement. |
| Selective verification | SURE-RAG's July 2026 revision evaluates sufficiency, coverage, uncertainty and conflict. It also reports a performance reversal on a different natural hallucination task. It is a preprint reporting submission, not verified acceptance. [Paper](https://arxiv.org/abs/2605.03534) | Narrow the task and test transfer. Strong controlled results do not imply general verification quality. |
| Agent diagnosis and repair | AgentRx's August revision reports 170 annotated trajectories and EMNLP Findings acceptance. REFLECT tests diagnosis-specific replay interventions. AgentDebugX packages diagnosis and recovery. [AgentRx](https://arxiv.org/abs/2602.02475), [REFLECT preprint](https://arxiv.org/abs/2606.09071), [AgentDebugX preprint](https://arxiv.org/abs/2607.18754) | A generic agent-debugger pivot or replay-based attribution alone is already crowded. These are related work, not unclaimed opportunities. |
| Retrieval test adequacy | The July 2026 Chunk Coverage paper studies retrieval-space coverage and test selection; its record identifies ISSTA 2026. [Paper](https://arxiv.org/abs/2607.18155) | A RAG testing paper needs more than a regression-test generator or coverage count. |
| Trace interchange | OpenTelemetry has a dedicated GenAI conventions repository covering GenAI and MCP signals. [Official repository](https://github.com/open-telemetry/semantic-conventions-genai) | Extend the existing exporter/import boundary when useful; avoid rebuilding an observability platform. Pin schema mappings rather than assuming lasting compatibility. |

These capabilities were not all introduced this month. The recent 2026 work
matters because the comparison set has expanded beyond the older scalar-metric
baselines. No cross-paper metric in this table proves a competitor is better
than ContextTrace on an identical task.

## Recommended focus

Proposed product promise: **show where a pipeline change lost, altered, or
misattached the evidence behind an answer, then preserve a regression check.**

For example, a retrieved QA record contains the answer, but sentence selection
keeps only its question. The useful diagnostic identifies the original record,
selected fragment, lost linked answer, affected claim, and reproducible check.
It should distinguish an observed transformation defect from a hypothesized
semantic consequence. Only instrumented stages can establish where the loss
occurred; missing capture data must remain unknown.

This builds on existing `compare`, `audit`, `repair`, and `suite` commands. The
new work should be limited to a missing capability discovered through a real
workflow comparison, such as an evidence-transformation manifest and linked-unit
integrity audit. Do not create another overlapping command family or dashboard.
The proposed focus is a positioning hypothesis; this review does not establish
market demand or research novelty.

Keep lightweight defaults, no forced hosted service, and explicit provider
provenance. Support existing tracing systems where that reduces user work.
Provider extensibility does not require shared ownership of the project.

## Ordered game plan

1. **Reconcile release state and workspaces.** Use the published 1.2.0 wheel
   as the product baseline, classify pending changes as fixes, experiments,
   documentation, or unrelated work, and correct stale release descriptions.
   Preserve the dirty workspace. The registry/package inventory is completed;
   semantic reconciliation of its pending changes is still open.
2. **Choose one demonstrable product improvement.** Trace a linked-evidence
   loss through a small documentation/support RAG example and a second pipeline.
   Specify observable inputs, unknown states, expected diagnostic, and a stable
   regression assertion. Freeze a short acceptance checklist before coding.
   Reuse the existing offline examples as regression coverage, not proof of
   generalization.
3. **Release when that improvement is ready.** Bug fixes and corrected docs
   can justify 1.2.1. A useful backwards-compatible new workflow can justify
   1.3.0. Run release checks on the exact candidate, including privacy, supported
   platforms, artifact/install checks, and migration compatibility. The current
   experimental verifier remains unpromoted; its gates are not relaxed.
4. **Use the release to earn recurring use.** Put one complete failure-to-fix
   example first in the quickstart, publish a concise reproducible walkthrough,
   and make two integrations easy to run. Measure voluntarily reported successful
   setup and repeat CI use alongside download trends. Do not add telemetry or
   contact users without authorization. Downloads alone do not establish active
   users or verifier quality.
5. **Run one separate research pilot with a stop rule.** Spend a bounded work
   block on the question below. Freeze the dataset contract and method before
   scoring; do not resume unlimited model/threshold sweeps. Stop if the observed
   issue is specific to one adapter, the method adds no benefit over complete
   selected records, or related work already answers the proposed contribution.

The first new engineering task is workspace/release reconciliation followed by
an acceptance specification for evidence integrity. It is not another five-way
model run or a version bump. Do not finish 400 annotations merely because the
packet already exists; retain them as pending research work until scoped.

## Research direction consistent with actual LLM/RAG work

Candidate question: **How much does the construction of selected evidence
change claim-verification decisions, and can preserving evidence structure
improve verification across domains and verifier backends?**

Study both information-preserving representations and information-losing
transformations. A harmless representation change should not be confused with
removing a material answer or qualifier: losing evidence can legitimately
change the correct verdict. Bind labels to the exact displayed inputs, keep
upstream assessments out of model inputs, and retain source/offset provenance.
Compare the same fixed inputs across backends within each condition; describe
restored records as an input change rather than a same-input model improvement.

The bounded pilot should compare the original fragment selector, complete
already-selected units, and one proposed structure-preserving method. Measure
incorrect support, supported recall, per-class review recall, localization,
token cost and latency, and robustness across source-disjoint data. Include
clean controls and negative cases, not only known failures. Freeze one local
NLI baseline and one suitable current verifier; Jev can be optional if a later
task explicitly authorizes hosted evaluation. No extra hosted calls were made
for this review.

Start with a small owner-adjudicated development pilot and acknowledge that
annotation provenance. The research question must survive related-work and
label-validity checks before building a new untouched confirmation set. Compare
against SURE-RAG, Q-CARE, fine-grained attribution, and evidence reconstruction
work at the method level; this literature screen alone cannot establish novelty.
The accepted GroundLM paper and used development sets remain distinct from
any new contribution. Choose a venue after the contribution and evidence exist,
not as the reason to keep expanding the product.

## Decision boundaries

- Continue the product because a working workflow exists; validate its next
  user benefit rather than treating download counts as proof of product fit.
- Pause general verifier training and the remaining bulk label-review pass
  until they serve the narrower research design.
- Keep the 1.3 verifier-upgrade checklist as historical/current quality evidence;
  a proposed product-only release needs a separate frozen scope.
- This review made documentation/audit artifacts only. It did not merge, publish,
  bump a version, retrain a model, contact anyone, or change runtime defaults.

For future turns, use this review and the machine-readable wheel inventory to
re-establish the shipped baseline; do not assume the latest research experiment
is the latest product release.
