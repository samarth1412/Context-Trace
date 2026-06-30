# ARR Annotation Label Guide

This guide defines the labels available to independent reviewers. It contains
no case IDs, expected labels, system predictions, or dataset label counts.

## Decision Order

1. Identify every material factual claim in the answer.
2. Locate the smallest exact context span that supports or conflicts with each
   claim.
3. Assign the minimal observable failure label set.
4. Assign one primary root cause using only information visible in the packet.
5. Record uncertainty in `notes`; do not infer unavailable retrieval or model
   internals.

## Failure Labels

- `no_failure_detected`: Every material answer claim is supported by the
  provided contexts, citations are aligned where present, and the answer did
  not need to abstain. Do not combine this with another failure label.
- `partial_support`: At least one material answer claim or required fact is
  supported and at least one other material claim or fact lacks support. Use
  `contradicted_answer` instead when source evidence explicitly states an
  incompatible fact.
- `unsupported_answer`: Diag-150 label for an answer whose material factual
  content is not supported by the provided contexts.
- `unsupported`: RAGTruth label with the same observable meaning as
  `unsupported_answer`. Preserve the dataset-specific spelling in a RAGTruth
  packet.
- `contradicted_answer`: At least one material answer claim explicitly
  conflicts with provided source evidence. This may be combined with
  `should_have_abstained` when an unqualified answer was unsafe.
- `citation_mismatch`: The cited source is missing or does not support its
  associated claim, including cases where another provided source does.
- `should_have_abstained`: The available evidence is absent, insufficient, or
  conflicting, but the answer asserts an unqualified factual conclusion.

## Primary Root Causes

Choose exactly one root cause.

- `no_failure_detected`: No observable failure is present.
- `answer_overreach`: The answer adds a material claim or detail beyond what
  the provided evidence supports.
- `conflicting_contexts`: Provided evidence explicitly conflicts with a
  material answer claim.
- `wrong_source_cited`: The answer points to a missing or non-supporting source
  for a claim, including when another provided source supports it.
- `should_have_abstained`: No provided source supports a responsible factual
  answer, so the system should have declined or qualified its response.

Do not assign `retrieval_miss`, `reranking_failure`, `chunking_issue`, or
`corpus_gap` from these packets. Those diagnoses require retrieval or corpus
state that is intentionally hidden from annotators.

## Citation Statuses

Record one status per material cited claim, in answer order.

- `citation_ok`: The cited source exists and supports the associated claim.
- `cited_source_does_not_support_claim`: The cited source exists but does not
  support the claim, and no provided source clearly supplies the support.
- `claim_supported_by_different_source`: The cited source does not support the
  claim, but another provided source does.
- `cited_source_missing`: The citation references a source absent from the
  packet.

Leave `citation_statuses` empty when the answer contains no material citation.

## Evidence Spans

Each span must contain `context_id`, exact `text`, `start_char`, and `end_char`.
Offsets are zero-based with `end_char` exclusive. Copy the smallest span that
is sufficient to support or contradict the claim. Use multiple spans only when
the evidence is genuinely distributed. An empty list is valid when no provided
source supports the answer.

## Annotation Quality

- Complete every case assigned to you.
- Set packet-level `reviewer` to a stable pseudonymous ID.
- Set `review_kind` to `independent` only if you are not an author and did not
  inspect predictions, expected labels, or the private key.
- Use a consistent numeric confidence scale and state that scale in the first
  case's notes.
- Return the completed JSON unchanged except for reviewer fields and
  `annotation` objects.
