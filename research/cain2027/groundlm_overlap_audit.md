# GroundLM publication-overlap audit

Status date: 2026-07-24  
GroundLM manuscript title: *Groundedness Is Not Truth: Evidence-Chain Forensics
for Retrieval-Augmented Generation*

## Status determination

The GroundLM 2026 call permits both archival and non-archival direct
submissions:

- archival long papers: up to eight content pages and included in ACL Anthology
  proceedings;
- archival short papers: up to four content pages and included in proceedings;
- non-archival papers: normally four to eight pages and not included in
  proceedings.

The official call also states that non-archival submissions may overlap with
previously published or concurrently submitted work, while archival submissions
must be original and cannot be under review elsewhere during the GroundLM review
period.

Source: [GroundLM 2026 call for papers](https://groundlm.github.io/grouplm_emnlp2026/).

On 2026-07-24, the user confirmed that the GroundLM submission is **archival**
and its decision is pending. The user also supplied the exact submitted PDF for
inspection. A submission receipt, OpenReview identifier, supplementary-material
record, and final decision are not yet stored in the repository.

**Finding: archival status is confirmed; decision is pending. This is not a
blocker to preregistration or new research, but it is a binding prior-work and
concurrent-review constraint for any CAIN manuscript.**

## Material inspected

- `paper/main.tex` and all included sections/tables.
- User-supplied submitted PDF, `main 2.pdf`: anonymous nine-page manuscript,
  SHA-256
  `ab8f211dc0102a12fbc6691135aecb11a8fe38dc638a4973cac1f3fbab6957ca`.
- `paper/main.pdf`: byte-identical to the supplied submission PDF, with the same
  SHA-256; anonymous nine-page build created 2026-07-05.
- `paper/contexttrace_preprint.pdf`: author-identified nine-page preprint created
  2026-07-07.
- `docs/publication_strategy.md`.
- `docs/workshop_submission_plan.md`.
- `docs/workshop_readiness.md`.
- Focused benchmark, Naturalistic Eval v2, RAGTruth, stress, baseline, and
  annotation-audit artifacts referenced by the manuscript.

The manuscript and most of its focused evidence are modified, untracked, or
ignored relative to public `origin/main`. The submitted bytes are now identified
by the hash above, but they cannot be reconstructed from public repository
history alone.

## GroundLM claims and contributions

The workshop manuscript presents the following as its contribution:

1. **Evidence-chain forensics formalism.** A typed chain separates claim support,
   citation state, source condition, abstention need, primary root cause, repair,
   and regression prevention.
2. **ContextTrace system.** A deterministic, local-first SDK/CLI that turns RAG
   or agent traces into inspectable claim-to-evidence-to-repair records.
3. **Groundedness-Truth-Gap.** An author-curated, template-varied 180-case
   conformance suite.
4. **Naturalistic transfer evaluation.** Audit v1, development, and 84-case Eval
   v2 public-document scenarios.
5. **External and safety controls.** RAGTruth, ARES, CRAG, a locked RAGTruth
   subset, and a constructed adversarial stress suite.
6. **Same-ID baselines.** RAGAS, DeepEval, lexical coverage, MiniLM cosine,
   RAGChecker, and a frozen GPT judge where configurations are available.
7. **Reproducibility and review infrastructure.** Frozen profiles, hashes,
   blinded annotation packet, scorer, and fail-closed claims.
8. **Bounded empirical conclusion.** Binary failure blocking transfers better
   than fine-grained root/source/unverifiable attribution; no broad superiority,
   truth-verification, independent-validation, or human-actionability claim is
   made.

## Overlap with the proposed CAIN paper

| Candidate CAIN contribution | GroundLM overlap | Risk | Required boundary |
| --- | --- | --- | --- |
| Evidence-chain representation | Directly claimed | Critical | Cite as prior ContextTrace/GroundLM contribution; do not claim novelty |
| Local deterministic SDK/CLI | Directly claimed | Critical | Treat as evaluated subject/system, not new contribution |
| Source-condition taxonomy | Directly claimed and evaluated | High | New contribution must be transfer evidence, not the taxonomy itself |
| Abstention and root-cause outputs | Directly claimed | High | Novelty may lie in selective calibration/generalization, not output existence |
| Groundedness-Truth-Gap | Directly introduced | Critical | Calibration-only prior benchmark |
| Naturalistic Eval v2 | Headline GroundLM evidence | Critical | Calibration-only; exclude from CAIN independent test |
| RAGTruth/ARES/CRAG results | Reported as controls/calibration | High | Context only; no reuse as CAIN test evidence |
| Adversarial stress suite | Reported before/after | High | Engineering regression only |
| Same-ID baselines | Reported | Medium | New sealed IDs and preregistered mappings are required |
| Blinded packet/scorer | Reported | Medium | Reuse infrastructure only; new independent annotations are required |
| Untouched real-RAG generalization | Explicitly missing | Low if genuinely new | Primary CAIN empirical contribution |
| Selective deterministic→NLI→abstain cascade | Not implemented in GroundLM | Low if developed only on separate dev data | Candidate CAIN method contribution |
| Field-level independent agreement | Missing | Low if newly collected | Candidate CAIN validity contribution |
| Operational feasibility under load | Not a GroundLM headline study | Low to medium | Candidate CAIN software-engineering contribution |
| Human developer actionability | Explicitly missing | Low if independently approved and run | Optional CAIN contribution |

## Material distinction required for CAIN

The CAIN paper should state that GroundLM introduced the system/formalism and
reported calibration results. Its new question should be:

> Does selective evidence-chain diagnosis generalize to genuinely unseen,
> naturally produced RAG traces across source families, domains, publication
> windows, and source-condition shifts, and is that diagnosis operationally
> feasible?

Minimum distinct evidence:

- 300–500 real RAG natural-OOD traces from three new domains;
- approximately 100 versioned/authority-contrasting traces;
- source/domain/time-disjointness and content-deduplication against all prior
  ContextTrace/GroundLM sources;
- public unlabeled freeze before verifier execution or label exposure;
- two independent annotators for headline cases and field-level agreement;
- a successor verifier with a new identifier and pinned selective NLI route;
- one-time sealed evaluation;
- new same-ID baselines and prespecified statistics;
- operational measurements, and optionally an approved human actionability
  study.

The CAIN paper must not reuse GroundLM prose, figures, tables, or contribution
wording without citation and a clear extension statement. Shared background,
system descriptions, and calibration results should be minimized and labeled as
prior work.

## Concurrent-submission risk

The official CAIN CFP requires unpublished original work and prohibits a paper
from being under review or submitted elsewhere while CAIN is considering it:
[CAIN 2027 Research Track](https://conf.researchr.org/track/cain-2027/cain-2027-call-for-papers).

GroundLM 2026 takes place on 2026-10-29, one day before the CAIN deadline.
Therefore:

Because GroundLM is archival, the CAIN manuscript must be a substantial,
explicitly disclosed extension whose novel claims and evidence are not the
GroundLM contribution. Its decision and final publication record must be
checked before CAIN submission. If GroundLM remains under review near the CAIN
deadline, the venues' concurrent-review restrictions must be resolved before
submission.

## Additional REALM overlap risk

The governing specification mentions a REALM submission on typed,
staleness-aware context assembly. No local artifact supports an audit of its
claims or archival status. CAIN source-condition, precedence, authority,
versioning, or typed-context claims cannot be finalized until that manuscript
is reviewed alongside GroundLM.

## Remaining publication records

GroundLM no longer blocks Phase 1. Before a CAIN submission, retain:

1. the GroundLM OpenReview paper number or receipt;
2. any submitted supplementary material;
3. the final decision and publication record;
4. any declaration made about dual submission or prior work;
5. the REALM manuscript/receipt and archival status.

The unresolved REALM boundary and any concurrent-review state remain submission
gates, not blockers to untouched-corpus research.
