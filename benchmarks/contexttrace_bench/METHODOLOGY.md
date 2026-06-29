# ContextTrace-Bench Methodology

ContextTrace-Bench measures ContextTrace as a verifier, not as a retriever or
answer generator. A case is a portable RAG trace with a query, answer, retrieved
contexts, optional citations, and expected diagnostic labels.

The benchmark is designed to answer:

- Did the verifier classify claim support correctly?
- Did it identify the right failure labels?
- Did it attribute the primary root cause correctly?
- Did it detect citation errors?
- Did it localize the evidence span used for the verdict?
- Did it avoid dangerous false greens?

It is not a general RAG system leaderboard and should not be presented as proof
that a retrieval or generation stack is state of the art.

## Case Sets

`contexttrace`
: Curated cases from ContextTrace docs, examples, and release artifacts.

`external`
: Curated cases from public OSS documentation and public issue-style examples
  included in the package verifier benchmark.

`all`
: The union of `contexttrace` and `external`.

`public_holdout`
: A separate curated public-doc holdout from OpenTelemetry, Weaviate,
  LlamaIndex, Milvus, LangChain, Haystack, Qdrant, Pinecone, Chroma, RAGAS,
  DeepEval, LangSmith, Phoenix, TruLens, DSPy, LanceDB, Elasticsearch, Redis,
  pgvector, OpenSearch, MongoDB Vector Search, Azure AI Search, Vespa, OpenAI
  Evals, and Guardrails docs. This case set is intentionally not included in
  `all` so the default 500-case leaderboard remains stable while holdout
  regressions stay visible. It has reached the 150-case ContextTrace-Diag-150
  target and requires the [human audit checklist](AUDIT.md) before being called
  frozen.

The default repo-level run adds deterministic generated variants until the target
case count is reached. Generated variants are useful for regression pressure:
they preserve the same trace schema while varying labels, citations, evidence,
and failure shapes. They are not a substitute for independent human-labeled
external datasets.

Run the public holdout without generated variants:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set public_holdout \
  --no-generated-cases \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout
```

## Labels

Labels come from two sources:

- Bundled verifier benchmark cases define expected failure labels, claim-verdict
  counts, citation statuses, primary root causes, and evidence spans when the
  fixture supports those fields.
- `labels.json` adds expected primary root causes and evidence spans for older
  verifier fixtures that predate the richer benchmark metadata.

The harness intentionally keeps `candidate_inputs.jsonl` label-free. External
evaluators receive only the case ID, trace payload, source metadata, and variant
metadata.

## Metrics

Failure label macro-F1
: Macro-F1 over expected failure labels such as `unsupported_answer`,
  `citation_mismatch`, `should_have_abstained`, and `no_failure_detected`.

Claim verdict macro-F1
: Macro-F1 over claim verdict counts: `supported`, `partially_supported`,
  `unsupported`, `contradicted`, and `unverifiable`. External case-pack rows can
  mark `expected_verdict_scope: answer_label` when the source dataset labels
  answer-level outcomes but does not provide claim-level verdict counts; those
  rows are excluded from claim-verdict metrics.

Root-cause accuracy
: Exact match for the expected primary root-cause label on cases with root-cause
  labels.

Citation error precision, recall, and F1
: Detection quality for bad citation statuses:
  `cited_source_missing`, `cited_source_does_not_support_claim`, and
  `claim_supported_by_different_source`.

Evidence span overlap
: Token-F1 overlap between expected and predicted evidence snippets.

Dangerous false green rate
: Share of failing cases incorrectly predicted as only `no_failure_detected`.

Confidence intervals
: The harness reports deterministic 95% case-bootstrap confidence intervals for
  the headline quality metrics. These intervals resample benchmark cases with
  replacement using a fixed seed so CI artifacts remain reproducible. They are
  uncertainty estimates for the current case distribution; they do not remove
  the need for independent datasets or human audit.

Latency and cost
: Latency is measured locally per case. ContextTrace's default verifier has no
  remote evaluator cost; candidate rows may report estimated or measured cost.

## Quality Gates

The default gates are readiness checks for this repository:

- `failure_label_macro_f1 >= 0.95`
- `claim_verdict_macro_f1 >= 0.95`
- `root_cause_accuracy >= 0.90`
- `citation_error_f1 >= 0.90`
- `evidence_span_overlap >= 0.75`
- `dangerous_false_green_rate <= 0.01`

Passing these gates means the current verifier did not regress on the current
labeled benchmark. It does not, by itself, justify a broad public
state-of-the-art claim.

## Candidate Baselines

Candidate prediction files are scored by the same harness against the same case
IDs. Missing diagnostics are reported as `N/A`, not zero. This matters because
faithfulness-only evaluators usually do not report root causes, citation status,
or evidence spans.

A publishable baseline row should include:

- The exact command used.
- The package versions and model names.
- Whether the run covered all benchmark cases.
- The candidate JSON file generated by the runner or adapter.
- The scored `leaderboard.md` and `baseline_results.json` artifacts.
- The confidence interval table from `results.md` or `report.html`.

## External Dataset Adapters

`ragtruth_adapter.py` converts the official RAGTruth `response.jsonl` and
`source_info.jsonl` files into a ContextTrace-style case pack. RAGTruth is a
word-level hallucination corpus with response-level source joins, while
ContextTrace-Bench scores source-side evidence localization. For that reason the
adapter preserves answer-side hallucination spans in metadata and leaves
`expected_evidence_spans` empty until human review maps them back to supporting
or contradicting source spans.
It also uses `expected_verdict_scope: answer_label` by default, so claim-verdict
count metrics are not inferred from RAGTruth answer-level labels. Reviewers can
opt individual rows into strict claim-count scoring with
`taxonomy_override.expected_verdict_counts`.

For a broader RAGTruth review packet, prefer deterministic stratified sampling
over taking the first rows from the export:

```bash
python benchmarks/contexttrace_bench/ragtruth_adapter.py \
  --response benchmarks/contexttrace_bench/out/ragtruth_official/response.jsonl \
  --source-info benchmarks/contexttrace_bench/out/ragtruth_official/source_info.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_case_pack_test200_stratified.json \
  --split test \
  --quality good \
  --sample-size 200 \
  --sample-seed 13 \
  --stratify-by task_type,source,expected_label,model
```

Record `sample_size`, `sample_seed`, and `stratify_by` from the case-pack
`stats.sampling` block with any reviewed result so the split is reproducible.

The recommended path is to generate the case pack, review queue, reviewer
packet, and workflow manifest together:

```bash
python benchmarks/contexttrace_bench/ragtruth_workflow.py \
  --response benchmarks/contexttrace_bench/out/ragtruth_official/response.jsonl \
  --source-info benchmarks/contexttrace_bench/out/ragtruth_official/source_info.jsonl \
  --output-dir benchmarks/contexttrace_bench/out/ragtruth_test200_review \
  --split test \
  --quality good \
  --sample-size 200 \
  --sample-seed 13 \
  --stratify-by task_type,source,expected_label,model
```

After independent review fills `source_evidence_spans`, rerun with `--review`.
The workflow will validate the reviewed JSONL, apply mappings, score the
reviewed case pack, and record artifact paths plus scoring summary in
`ragtruth_workflow_manifest.json`:

```bash
python benchmarks/contexttrace_bench/ragtruth_workflow.py \
  --response benchmarks/contexttrace_bench/out/ragtruth_official/response.jsonl \
  --source-info benchmarks/contexttrace_bench/out/ragtruth_official/source_info.jsonl \
  --output-dir benchmarks/contexttrace_bench/out/ragtruth_test200_review \
  --split test \
  --quality good \
  --sample-size 200 \
  --sample-seed 13 \
  --stratify-by task_type,source,expected_label,model \
  --review benchmarks/contexttrace_bench/out/ragtruth_test200_review/ragtruth_reviewed.jsonl \
  --allow-missing-source-spans
```

Use `--allow-missing-source-spans` only when the reviewed JSONL explicitly
marks rows where no fair source-side span exists; those rows remain reviewed
but do not contribute to evidence-span-overlap labels. Keep strict source-span
validation for review rounds where every hallucination row has a copied source
evidence span.

External case packs are scored with the same harness and report format:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --output-dir benchmarks/contexttrace_bench/out/ragtruth
```

The generated `candidate_inputs.jsonl` contains only trace payloads and safe
source metadata. It does not include expected labels, notes, or RAGTruth
hallucination annotations.

Human evidence-span review uses a separate JSONL queue:

```bash
python benchmarks/contexttrace_bench/ragtruth_review.py build-queue \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --output benchmarks/contexttrace_bench/out/ragtruth_review_queue.jsonl \
  --suggest-source-spans \
  --max-suggestions 3
```

`--suggest-source-spans` pre-populates scored context snippets for reviewer
convenience. These suggestions are not accepted evidence until a reviewer copies
the correct text into `source_evidence_spans`. Build a reviewer-facing Markdown
packet from the queue when the mapping needs independent sign-off:

```bash
python benchmarks/contexttrace_bench/ragtruth_review.py build-packet \
  --review-queue benchmarks/contexttrace_bench/out/ragtruth_review_queue.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_review_packet.md \
  --context-char-limit 6000
```

The packet contains reviewer instructions, a checklist, answer-side
hallucination spans, suggested source snippets, and source-context excerpts.
It is a human review aid; the JSONL queue remains the machine-readable artifact.
After review, set `review_status` to `reviewed`, `accepted`, or `approved`,
then validate the reviewed JSONL before applying it:

```bash
python benchmarks/contexttrace_bench/ragtruth_review.py validate \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --review benchmarks/contexttrace_bench/out/ragtruth_reviewed.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_review_validation.json \
  --require-reviewed \
  --require-source-spans
```

The strict validation command fails if reviewed rows are missing reviewer
metadata, review dates, source evidence spans, or source spans that do not occur
in the provided source contexts. After validation passes, apply the file:

```bash
python benchmarks/contexttrace_bench/ragtruth_review.py apply \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --review benchmarks/contexttrace_bench/out/ragtruth_reviewed.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_reviewed_case_pack.json \
  --require-reviewed
```

Do not treat an adapted RAGTruth case pack as a frozen benchmark split until:

- The source files, commit or dataset version, and adapter command are recorded.
- Answer-side hallucination spans are manually audited against source passages.
- The resulting case pack is reviewed for ContextTrace taxonomy fit.
- The scored run includes confidence intervals and a limitations paragraph.

## Public Claim Policy

Acceptable current claim:

> ContextTrace-Bench is a reproducible local benchmark for claim-level RAG
> failure attribution, citation-error detection, root-cause diagnosis, and
> evidence-span localization.

Acceptable after competitor rows:

> On ContextTrace-Bench vN, ContextTrace outperforms the listed baseline
> evaluators on the reported diagnostic metrics while remaining local-first.

Do not claim general RAG-evaluation state of the art until the benchmark includes
independent public datasets, an audited frozen holdout split, confidence
interval review, and fully reproducible competitor runs.

## Known Limitations

- Generated variants increase regression coverage but are correlated with the
  curated source cases.
- Root-cause labels are deterministic product labels, not universal taxonomy
  ground truth.
- Evidence-span scoring uses token overlap rather than human judgment.
- Candidate adapters infer labels from evaluator-specific scores when the
  external evaluator does not natively expose ContextTrace labels.
- The public holdout has reached the 150-case ContextTrace-Diag-150 target, but
  it still needs human audit sign-off before being described as frozen.
- Current benchmark artifacts are generated in `benchmarks/contexttrace_bench/out/`.
  CI publishes run artifacts, while stable releases attach selected checksummed
  external evidence bundles as a versioned archive.

## Release Evidence Checklist

Before publishing dataset-specific benchmark results, produce:

- `contexttrace_bench_results.json`
- `results.md`
- `leaderboard.md`
- `report.html`
- `error_analysis.json`
- `error_analysis.md`
- `candidate_inputs.jsonl`
- At least one competitor smoke candidate, or a documented reason it is pending
  such as missing evaluator credentials.
- The ContextTrace-Diag-150 human audit status from [AUDIT.md](AUDIT.md).
- A clear limitations paragraph wherever results are shown publicly.
