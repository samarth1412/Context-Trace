# Author audit fallback

An author audit is a debugging fallback, not independent validation. It may
identify packet defects and label disagreements while external review is being
scheduled, but it cannot change `paper_result_eligible` or satisfy the broad
SOTA gate.

Required records:

- `audit_packet.jsonl`: blinded case rows with no expected labels or predictions.
- `responses.jsonl`: the author's completed judgments, preserved unchanged.
- `disagreements.jsonl`: judgments that differ from the private key after scoring.
- `corrections.jsonl`: separately approved corrections with rationale.
- `summary.json`: reviewer role, counts, hashes, validation status, and explicit
  `independent=false` and `paper_result_eligible=false` fields.

No author responses currently exist. Generated packet scaffolding must therefore
report `pending_author_completion` and must not contain guessed labels.
