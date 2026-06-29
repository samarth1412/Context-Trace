# ARR Annotation Protocol

This protocol covers blinded ground-truth review for RAGTruth and
ContextTrace-Diag-150. It is separate from the later diagnosis-actionability
study, where reviewers will compare system outputs.

## Review Targets

- Independently review all 150 ContextTrace-Diag-150 cases.
- Independently review all 200 cases in the frozen RAGTruth primary pack.
- Double-annotate a fixed stratified overlap of at least 20%, with minimums of
  30 Diag-150 cases and 40 RAGTruth cases.
- Adjudicate every disagreement before producing a corrected release pack.

An author may run a `blinded_author` pass for calibration. That pass does not
count as independent validation. At least one non-author must use
`review_kind=independent` for any independently reviewed claim.

## Packet Handling

Generate the packet and private key together, then send only
`annotation_packet.json` to reviewers. Keep `annotation_key.private.json` with
the experiment owner. Reviewers must not inspect ContextTrace predictions,
expected labels, benchmark notes, or original case IDs.

```bash
python benchmarks/contexttrace_bench/arr_annotation.py build \
  --case-set public_holdout \
  --output-dir benchmarks/contexttrace_bench/out/arr_annotation_diag150
```

Set the packet-level `reviewer` and `review_kind`, fill the `annotation` object
for each assigned case, and preserve blind IDs. Do not modify query, answer,
context, or citation fields.

## Labels

`failure_labels` is the minimal set of observable failure categories. Use
`no_failure_detected` only when every material answer claim is supported.

`primary_root_cause` is the single most direct upstream cause supported by the
trace. Do not infer unavailable system internals. Use the repository label
inventory in `labels.json`; record ambiguity in `notes`.

`citation_statuses` records one status per material cited claim where applicable.
`should_abstain` is true only when the available evidence is insufficient for a
responsible answer. `evidence_spans` contains minimal exact source spans with
context ID, text, start character, and end character. Empty spans are valid when
no source text supports the claim.

`confidence` is a reviewer-supplied numeric confidence on a consistent scale.
The scale and any reviewer training examples must be fixed before annotation.

## Agreement And Adjudication

Score completed packets with:

```bash
python benchmarks/contexttrace_bench/arr_annotation.py score \
  --key benchmarks/contexttrace_bench/out/arr_annotation_diag150/annotation_key.private.json \
  --annotations reviewer_a.json reviewer_b.json \
  --output-dir benchmarks/contexttrace_bench/out/arr_annotation_diag150/scored
```

Report completion, failure-label exact agreement and set F1, primary-root-cause
agreement and Cohen's kappa, abstention agreement, and evidence-span token F1.
Do not hide low agreement. Use `audit_disagreements.jsonl` for adjudication and
record each resolution in `audit_corrections.jsonl` with adjudicator identity and
rationale. Re-score the corrected release pack separately from raw agreement.

## Quality Gate

Independent-review claims require complete assigned packets, no leakage errors,
reported raw agreement, documented adjudication, and a versioned corrected case
pack. Agreement thresholds are descriptive rather than reasons to discard data;
material ambiguity belongs in the paper's error analysis and limitations.
