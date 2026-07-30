# ContextTrace 60-case assisted-annotation pivot

Frozen before model access to the 60 production cases: 2026-07-30

This pilot has two distinct arms:

1. **Model-first, Pul-reviewed:** Codex drafts every field using only the
   supplied trace and source evidence. Pul reviews every field, changes any
   value they disagree with, and signs the review attestation.
2. **Sid independent:** Sid completes the original packet without seeing the
   model draft, Pul's review, system predictions, or Phase 6 results.

The model draft is never described as an independent annotation or gold label.
Before Pul completes review, its status is `model_draft`. After complete review,
its status is `model_first_pul_reviewed`. It may be summarized as
“LLM + Pul reviewed,” with the model-first procedure disclosed.

The Sid submission remains an independent comparison arm. Agreement between
the two arms must be reported as cross-arm agreement, not inter-annotator
reliability. Neither arm alone is a sealed gold standard.

ContextTrace predictions and case-level Phase 6 results remain unavailable to
both arms during labeling. The original annotation packets remain unchanged.
