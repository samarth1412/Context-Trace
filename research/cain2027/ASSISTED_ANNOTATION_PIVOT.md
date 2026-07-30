# ContextTrace 60-case assisted-annotation pivot

Frozen before model access to the 60 production cases: 2026-07-30

This pilot has two distinct arms:

1. **Model-first, Pul-reviewed:** a pinned local Gemma 3 4B model drafts every
   field using only the supplied trace and source evidence. Codex performs
   mechanical validation of offsets, evidence quotations, and schema
   completeness. Pul reviews every field, changes any value they disagree with,
   and signs the review attestation.
2. **Sid independent:** Sid completes the original packet without seeing the
   model draft, Pul's review, system predictions, or Phase 6 results.

The model draft is never described as an independent annotation or gold label.
Before Pul completes review, its status is `model_draft`. After complete review,
its status is `model_first_pul_reviewed`. It may be summarized as
“LLM + Pul reviewed,” with the model-first procedure disclosed.

The Sid submission remains an independent comparison arm. Agreement between
the two arms must be reported as cross-arm agreement, not inter-annotator
reliability. Neither arm alone is a sealed gold standard.

The model artifact is `gemma3:4b`, weight digest
`aeda25e63ebd698fab8638ffb778e68bed908b960d39d0becc650fa981609d25`,
run locally through Ollama with temperature 0 and seed 20260730.

ContextTrace predictions and case-level Phase 6 results remain unavailable to
both arms during labeling. The original annotation packets remain unchanged.
