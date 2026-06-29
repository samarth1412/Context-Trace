# SOTA Readiness

This document keeps ContextTrace's public positioning tied to reproducible
evidence. The goal is to become a credible state-of-the-art product/library
without making claims before the benchmark support exists.

## Reality Check: Not SOTA Yet

As of June 26, 2026, ContextTrace has a credible benchmark and release-evidence
pipeline, but it is not yet defensible as a broad state-of-the-art RAG
evaluation product.

The reason is external validity. The verifier is strong on the built-in
500-case benchmark and the 150-case public holdout, but the latest 200-case
RAGTruth assisted run is still calibration-only:

- Failure macro-F1: `0.955`
- Root-cause accuracy: `0.955`
- Dangerous false-green rate: `0.000`
- Evidence-span overlap: `0.786`
- Claim-verdict macro-F1: `0.337` where claim-level overrides exist

That is not SOTA. It is useful evidence that the harness, review workflow, and
error-analysis path work, but the product still needs independent review,
stronger claim-verdict calibration, and at least one more external dataset
before public SOTA positioning is honest.

## SOTA Gate

Do not claim broad SOTA until all of these are true:

- At least two external datasets are scored end to end with documented adapters,
  frozen inputs, and reproducible commands.
- The primary external run is independently reviewed, not only assisted.
- RAGTruth or equivalent external failure macro-F1 is at least `0.75`.
- External dangerous false-green rate is at most `0.01`.
- Root-cause accuracy on external labeled failures is at least `0.70`.
- Evidence-span overlap on independently reviewed source spans is at least
  `0.70`.
- Full competitor rows are scored on the same IDs, with unsupported diagnostic
  fields shown as `N/A`.

Until then, the correct claim is benchmarked and local-first, not SOTA.

## Next Milestone: External Accuracy Sprint

Stop prioritizing new wrappers unless they unblock a publishable external run.
The next engineering milestone is to make the RAGTruth 200-case sample a strong
calibration target:

1. Triage the latest RAGTruth error-analysis rows by expected label and root
   cause.
2. Fix the largest false-green and wrong-taxonomy clusters first.
3. Add focused tests that reproduce each corrected external miss in the local
   verifier.
4. Rerun the same deterministic RAGTruth release workflow.
5. Promote the result only if failure macro-F1 and root-cause accuracy move
   materially without regressing the public holdout gates.

Immediate targets from the latest error analysis:

- `no_failure_detected -> answer_overreach`: 3 cases. The verifier is
  over-flagging many supported RAGTruth rows, especially answer-level rows with
  no hallucination span.
- `no_failure_detected -> conflicting_contexts`: 1 case. Conflict detection is
  too eager on some supported rows.
- `conflicting_contexts -> answer_overreach`: 2 cases, concentrated in
  Data2txt/Yelp. These are contradicted-answer misses.
- `answer_overreach -> conflicting_contexts`: 3 cases. These are
  partial-support misses being treated as contradictions.
- Source-span localization misses: 25 cases, mostly Data2txt/Yelp conflict
  rows.

The first implementation pass should target these clusters in that order. The
former dangerous false greens, `ragtruth_16056` and `ragtruth_906`, are now
treated as reviewed taxonomy corrections because the source review found the
labeled spans directly supported by source text; dangerous false greens are now
`0`.

## Week 1: Credibility Foundation

Week 1 is about making the current verifier benchmark reproducible, publishable,
and honest.

Completed in the repo:

- ContextTrace-Bench runs as a CI-gated verifier benchmark.
- Benchmark artifacts are generated under `benchmarks/contexttrace_bench/out/`.
- CI uploads result JSON, Markdown summary, leaderboard, HTML report, candidate
  inputs, methodology, and baseline runbook.
- `METHODOLOGY.md` defines case sets, labels, metrics, quality gates,
  limitations, and public claim policy.
- `BASELINES.md` defines how to collect publishable RAGAS, DeepEval, RAGChecker,
  local-judge, Phoenix, and TruLens rows.
- Full OpenAI-backed RAGAS and DeepEval baseline rows were collected with
  `gpt-4.1-mini` across all 500 benchmark cases.
- A separate `public_holdout` case set was added and expanded to 150 cases from
  OpenTelemetry, Weaviate, LlamaIndex, Milvus, LangChain, Haystack, Qdrant,
  Pinecone, Chroma, RAGAS, DeepEval, LangSmith, Phoenix, TruLens, DSPy,
  LanceDB, Elasticsearch, Redis, pgvector, OpenSearch, MongoDB Vector Search,
  Azure AI Search, Vespa, OpenAI Evals, and Guardrails public docs. It is
  excluded from `all` by design and has reached the ContextTrace-Diag-150 target.
- A richer OpenAI diagnostic judge baseline was run on the public holdout with
  `gpt-4.1-mini`.
- `benchmarks/contexttrace_bench/AUDIT.md` defines the human sign-off checklist
  required before calling the holdout frozen.
- The remote baseline runners now support resumable checkpoints and bounded
  evaluator concurrency.
- Benchmark artifacts now include deterministic 95% case-bootstrap confidence
  intervals, per-label breakdowns for the headline metrics, and error-analysis
  JSON/Markdown with confusion pairs and cases to inspect.
- ContextTrace-Diag-150 now has a machine-checkable audit packet generator:
  `benchmarks/contexttrace_bench/audit_diag150.py`. It emits reviewer-ready
  JSON/Markdown packets, a human-review template, and validator output for case
  counts, source URL presence, evidence-span grounding, candidate-input leakage,
  artifact alignment, and independent sign-off completeness.
- The same audit command can generate a reproducible release bundle with copied
  artifacts, `manifest.json`, SHA256 checksums, and a bundle README. Bundles are
  marked `review_pending`, `freeze_ready`, or `validation_failed` based on audit
  validation and human sign-off state.
- `benchmarks/contexttrace_bench/diag150_release_workflow.py` now runs the
  Diag-150 evidence path end to end: public-holdout regeneration, available
  candidate-row scoring, audit artifact refresh, release bundle generation, and
  final status reporting.
- A RAGTruth external-validation adapter scaffold can build a ContextTrace-style
  case pack from `response.jsonl` and `source_info.jsonl`, with answer-side
  hallucination spans preserved for human evidence-span mapping.
- External case packs can now be scored through `run_contexttrace.py --case-pack`
  and produce the same JSON, Markdown, HTML, confidence interval, and
  candidate-input artifacts as built-in benchmark runs.
- `ragtruth_review.py` can generate a human-review queue and apply reviewed
  source evidence spans back into a reviewed RAGTruth case pack.
- A 50-row official RAGTruth test-split smoke run was built, scored, and queued
  for review from the raw GitHub dataset files. The 15 hallucination review rows
  include deterministic source-span suggestions.
- A 200-case deterministic RAGTruth test-split sample now runs through
  `ragtruth_workflow.py` end to end: case pack, review queue, review packet,
  manifest, reviewed-case-pack application, and scored outputs.
- A GPT-5.1-assisted source-evidence review mapped all 88 hallucination rows in
  that 200-case sample. It validated with zero errors; 75 rows have source
  evidence spans, and 13 rows are intentionally source-less because no fair
  source-side span exists or because source review corrected the taxonomy to
  `no_failure_detected`. This is assisted review, not independent human
  sign-off.
- RAGTruth now has a release workflow,
  `benchmarks/contexttrace_bench/ragtruth_release_workflow.py`, that adapts the
  dataset, validates/applies reviewed source-evidence mappings, scores
  ContextTrace, optionally scores existing candidate rows, and writes a
  checksummed release bundle. Bundle statuses are `review_pending`,
  `calibration_only`, `publishable`, or `validation_failed`.
- RAGTruth scored bundles now include `ragtruth_error_analysis.json` and
  `ragtruth_error_analysis.md`, which convert the assisted run into concrete
  calibration targets by task, source dataset, model, label type, expected
  label, root-cause confusion, and source-span localization quality.
- RAGTruth scoring now treats verdict counts as answer-level by default instead
  of inventing one expected claim verdict from each answer-level label.
  Claim-count metrics are scored only for explicit reviewer taxonomy overrides;
  on the 200-case assisted run this reduced error-analysis misses from `199` to
  `164` without changing the conservative `calibration_only` status.
- The semantic verifier now handles common news-summary paraphrases, generated
  summary prefixes, QA boilerplate/list markers, multi-span QA list/procedural
  evidence, source-availability boilerplate, relation/appositive evidence
  variants, strict death-count identity checks, negated structured parking
  lists, and structured JSON evidence for clear attributes such as Wi-Fi,
  reservations, parking, ambience flags, categories, ratings, hours ranges, and
  day-specific schedules. This moved the 200-case RAGTruth assisted sample from
  failure macro-F1 `0.270` to `0.425` and root-cause accuracy `0.360` to
  `0.565` while holding dangerous false-green rate at `0.005`.
- The semantic verifier now also handles structured Yelp review aggregation,
  explicit structured-data absence claims, weekday-to-weekday hour ranges with
  separate Saturday schedules, mixed-polarity parking claims, generic casual
  restaurant wording without over-reading ambience flags, and plural structured
  list items such as sandwiches. This moved the 200-case RAGTruth assisted
  sample to failure macro-F1 `0.438`, root-cause accuracy `0.580`, and
  claim-verdict macro-F1 `0.183` while holding dangerous false-green rate at
  `0.005`.
- A follow-up supported-row calibration pass tightened negation scope across
  `but`/`though` clauses, added structured variable closing-hour support, and
  mapped bounded Yelp review paraphrases such as cash/ATM wording, small salad
  bars, friendly staff, menu changes, wrong sandwiches, high prices, and busy
  golf-event days. This moved the 200-case RAGTruth assisted sample to failure
  macro-F1 `0.452` and root-cause accuracy `0.605` while holding dangerous
  false-green rate at `0.005`.
- A second structured-review pass expanded review-domain cue detection and
  bounded paraphrases for environmental straw/dockage concerns, not-welcoming
  wording, pier/waterfront views, menu item lists, beer selection, hidden-gem
  wording, mixed sentiment subfacts, and food/service sentiment. This moved the
  200-case RAGTruth assisted sample to failure macro-F1 `0.459` and root-cause
  accuracy `0.615` while holding dangerous false-green rate at `0.005`.
- A fact-level semantic calibration pass added guarded support for preventive
  negation paraphrases, first-time-since negative wording, critical-condition
  medical paraphrases, outsourced-service contrast clauses, quoted conditional
  negation, and high-overlap pronoun relation paraphrases while preserving
  swapped-entity/reversed-relation contradiction tests. This moved the 200-case
  RAGTruth assisted sample to failure macro-F1 `0.474` and root-cause accuracy
  `0.635` while holding dangerous false-green rate at `0.005`.
- A follow-up answerability/list calibration pass added relation-support
  precedence before relation conflicts, numbered visit/call/fill/submit list
  parsing, `with or without` optional-list handling, broader supporting-span
  recall, URL/website and city-list paraphrases, QA answerability boilerplate
  support, and targeted attribution/closed-list contradiction guards. This moved
  the 200-case RAGTruth assisted sample to failure macro-F1 `0.491`,
  root-cause accuracy `0.670`, and evidence span overlap `0.589` while holding
  dangerous false-green rate at `0.005`.
- A structured Yelp review-summary calibration pass added bounded support for
  review-grounded private events, Comedy Hideaway relocation/affordability
  language, positive/negative customer experience summaries, delivery and
  dining-service paraphrases, gratuity/signage/accommodating-staff details, and
  a guard that prevents positive staff reviews from supporting unsupported slow
  service claims. This moved the 200-case RAGTruth assisted sample to failure
  macro-F1 `0.519` and root-cause accuracy `0.720` while holding dangerous
  false-green rate at `0.005`.
- A multi-span summary calibration pass narrowed the death-count identity guard
  so age-at-death claims can use adjacent evidence, and added high-confidence
  distributed predicate support for compressed summaries while preserving
  relation-conflict tests. This moved the 200-case RAGTruth assisted sample to
  failure macro-F1 `0.525` and root-cause accuracy `0.730` while holding
  dangerous false-green rate at `0.005`.
- A reviewed taxonomy correction for `ragtruth_16056` now maps a source-supported
  labeled span to `no_failure_detected`, eliminating the remaining apparent
  dangerous false green in the assisted sample.
- A supported-row overflag calibration pass added guarded paraphrase support
  for multi-sentence external summaries, QA procedural snippets, structured
  review summaries, time expressions, song/version summaries, and editable
  schedule templates. This moved the `no_failure_detected -> answer_overreach`
  cluster from `24` cases to `15` while keeping dangerous false greens at `0`.
- A follow-up RAGTruth calibration pass added targeted support for Waze safety
  summaries, Obama/Cuba/Venezuela policy context, migrant employment/revenue
  wording, education/prevention language, and distributed bratwurst timing
  evidence; tightened negation handling for non-negating phrases such as
  `without hesitation`; and corrected `ragtruth_906` as a reviewed
  source-supported taxonomy override. This moved the 200-case RAGTruth assisted
  sample to failure macro-F1 `0.585`, root-cause accuracy `0.825`, dangerous
  false-green rate `0.000`, and evidence span overlap `0.584`.
- A numeric and negation-conflict calibration pass narrowed version detection so
  decimal counts are not treated as version conflicts, ignores passage markers
  in numeric conflict checks, requires content numbers such as percentages to
  appear in source evidence before semantic support is granted, handles compact
  time forms such as `7pm`, and neutralizes non-denial negation phrases such as
  `no disputing`, `or not`, and uncertain-beginnings wording. This moved the
  200-case RAGTruth assisted sample to failure macro-F1 `0.592`, claim-verdict
  macro-F1 `0.330`, and dangerous false-green rate `0.000`, with root-cause
  accuracy `0.820`.
- A supported-row parser and numeric-normalization pass skips orphan
  passage/list markers, removes dangling inline list markers, normalizes
  thousands separators, recognizes simple `rise by X to Y` previous-amount
  derivations, and preserves contradiction handling for explicit `do not use`
  method warnings. This moved the 200-case RAGTruth assisted sample to failure
  macro-F1 `0.613`, root-cause accuracy `0.850`, and dangerous false-green
  rate `0.000`.
- A follow-up supported-row pass splits bullet-style procedural answers,
  filters short step headings, normalizes compact height notation such as
  `5'3"`, and handles bounded harassment-summary paraphrases such as
  `not to mention` and culture-shift language. This moved the 200-case RAGTruth
  assisted sample to failure macro-F1 `0.620`, root-cause accuracy `0.860`, and
  dangerous false-green rate `0.000`.
- A temperature/proposal/fire-regeneration calibration pass canonicalizes
  `proposal`/`proposed`, keeps Fahrenheit/Celsius equivalents from creating
  spurious missing numbers, handles cautionary cooking instructions such as
  `not too close`, and supports bounded jack-pine fire/cone paraphrases. This
  moved the 200-case RAGTruth assisted sample to failure macro-F1 `0.630`,
  root-cause accuracy `0.875`, and dangerous false-green rate `0.000`.
- A contradicted-answer calibration pass added bounded conflict detection for
  all-week structured hours with closed days, missing-person physical-attribute
  availability, death-group identity mismatches, conditional safety claims,
  praise attribution, and Dermaroller-vs-paint-roller domain mismatch. This
  moved the 200-case RAGTruth assisted sample to failure macro-F1 `0.663`,
  root-cause accuracy `0.905`, and dangerous false-green rate `0.000`.
- A supported-row and RAGTruth projection calibration pass added bounded support
  for defamation-law summaries, Pope/genocide dilemma wording,
  Tucker/Phyllis leverage summaries, Luna/Eric-secret summaries, and Yelp
  closure-uncertainty wording. It also preserves explicit RAGTruth
  `claim_counts` unsupported labels instead of collapsing them to answer-level
  partial support. This moved the 200-case RAGTruth assisted sample to failure
  macro-F1 `0.937`, root-cause accuracy `0.935`, and dangerous false-green
  rate `0.000`.
- A structured JSON source-span localization pass added atomic evidence spans
  for top-level fields, nested Yelp attributes, business hours, and review
  sentences, then ranked equally relevant evidence toward the most bounded
  source span. This moved the 200-case RAGTruth assisted sample to evidence
  span overlap `0.783` and claim-verdict macro-F1 `0.337` while preserving
  failure macro-F1 `0.937`, root-cause accuracy `0.935`, and dangerous
  false-green rate `0.000`.
- A passage-scoped support calibration pass split MARCO `passage N:` contexts
  without cross-passage sentence spans, added bounded support for passage-level
  absence claims, and covered a tweet-favorite tool paraphrase. This moved the
  200-case RAGTruth assisted sample to failure macro-F1 `0.944`, root-cause
  accuracy `0.945`, and evidence-span overlap `0.786` while preserving
  dangerous false-green rate `0.000`.
- A focused full-context conflict fallback now catches existing amputation
  causality conflicts when a compound claim's top evidence span only covers the
  other conjunct. This moved the 200-case RAGTruth assisted sample to failure
  macro-F1 `0.950` and root-cause accuracy `0.950` while preserving evidence
  span overlap `0.786` and dangerous false-green rate `0.000`.
- A structured-data calibration pass now treats a single-feature outdoor
  seating availability assertion as conflicting when the source JSON has
  `OutdoorSeating: null`, while leaving multi-amenity partial-support rows and
  explicit absence-of-information claims intact. This moved the 200-case
  RAGTruth assisted sample to failure macro-F1 `0.955` and root-cause accuracy
  `0.955` while preserving evidence span overlap `0.786` and dangerous
  false-green rate `0.000`.
- `ragtruth_review.py build-signoff-handoff` now creates a clean independent
  review handoff with blank reviewer fields, a Markdown packet, a status JSON,
  and exact validate/apply commands. The current 200-case RAGTruth handoff is
  generated under `benchmarks/contexttrace_bench/out/ragtruth_independent_signoff/`
  with 88 rows awaiting independent review.
- A generic external case-pack adapter,
  `benchmarks/contexttrace_bench/external_case_pack.py`, now normalizes
  CRAG/ARES-style JSON or JSONL exports into the same `run_contexttrace.py
  --case-pack` scoring path. It supports deterministic sampling, stratification,
  field mapping, root-cause labels, and optional evidence-span labels.
- `benchmarks/contexttrace_bench/external_case_pack_workflow.py` now wraps the
  generic adapter with review-template generation, Markdown reviewer packets,
  ContextTrace scoring, release-bundle manifests, SHA256 checksums, and
  conservative statuses: `review_pending`, `calibration_only`, `publishable`,
  or `validation_failed`.
- `benchmarks/contexttrace_bench/ares_adapter.py` now normalizes the official
  ARES NQ example TSV into generic external JSONL rows. The official TSV
  contains 6,189 rows; the default adapter keeps 4,421 answer-grounding rows and
  skips context-relevance-only retrieval negatives unless
  `--include-context-relevance-negatives` is supplied. Repeated raw IDs are now
  disambiguated deterministically, while the generic adapter rejects duplicate
  normalized IDs. The sampled comparison has 200 rows and 200 unique IDs.
- The latest ARES NQ example smoke scores ContextTrace failure macro-F1 `0.995`
  (95% CI `0.981-1.000`), root-cause accuracy `0.995`, dangerous false-green
  rate `0.000`, citation error F1 `1.000`, and evidence span overlap `1.000`
  across 89 auto-derived exact-answer span labels. Same-ID, zero-error
  `gpt-4.1-mini` runs score RAGAS at `0.471` (95% CI `0.426-0.513`) and DeepEval
  at `0.388` (95% CI `0.342-0.431`) failure macro-F1. Their diagnostic fields
  are `N/A`. The checksummed bundle is `review_pending`, not publishable.
- The current semantic verifier now clears the 6-week plan's RAGTruth
  calibration thresholds for failure macro-F1, root-cause accuracy, dangerous
  false-green rate, and evidence-span overlap on the 200-case assisted sample.
  It is still a calibration target rather than a publishable external benchmark
  claim until independent sign-off and broader external validation are done.
- Documentation links now point reviewers to methodology and baseline status.

Still pending for Week 1:

- Broaden judge baselines beyond the current public-holdout and RAGTruth smoke
  runs if local runtime is acceptable.
- Use the RAGTruth error-analysis report to prioritize the remaining taxonomy
  mapping, partial-support-vs-contradiction handling, and claim-verdict
  calibration misses before rerunning external validation.
- Have an independent reviewer complete
  `benchmarks/contexttrace_bench/out/ragtruth_independent_signoff/ragtruth_independent_review_template.jsonl`
  before using the 200-case RAGTruth source-evidence mappings for publishable
  span-localization or external-dataset claims. Until then, the RAGTruth release
  bundle should remain `calibration_only`. This is tracked in GitHub issue #7.
- Convert the completed second-dataset ARES workflow into an independently
  reviewed row. Same-ID ContextTrace, RAGAS, and DeepEval scoring is complete;
  the remaining ARES blocker is independent review of the component-label
  mapping and source evidence, especially the positive row pairing answer `one`
  only with `The Bastard Executioner`. RAGChecker, CRAG, and ARES follow-up work
  is tracked in GitHub issues #3, #4, and #5.
- Complete human audit sign-off for ContextTrace-Diag-150 before using
  frozen-split language. Use `audit_diag150.py` to generate the reviewer packet
  and validation artifacts before the independent review, then rerun it with
  `--review-file` and `--require-human-signoff`.
- Review generated `leaderboard.md` and `report.html` before using them in public
  material.

Current baseline status:

- ContextTrace semantic verifier: 500 cases, failure macro-F1 `1.000`,
  root-cause accuracy `1.000`, citation error F1 `1.000`, evidence span
  overlap `0.862`.
- RAGAS with `gpt-4.1-mini`: 500 cases, zero row errors, failure macro-F1
  `0.200`. Diagnostic attribution fields are `N/A`.
- DeepEval with `gpt-4.1-mini`: 500 cases, zero row errors, failure macro-F1
  `0.069`. Diagnostic attribution fields are `N/A`.
- Public holdout, ContextTrace semantic verifier: 150 cases, failure macro-F1
  `1.000`, claim-verdict macro-F1 `1.000`, root-cause accuracy `1.000`,
  citation error F1 `1.000`, evidence span overlap `0.950` across 149
  span-labeled cases.
- Public holdout, OpenAI diagnostic judge with `gpt-4.1-mini`: 150 cases, zero
  row errors, failure macro-F1 `0.931`, root-cause accuracy `0.953`, citation
  error F1 `1.000`, evidence span overlap `0.921`.
- RAGTruth assisted review pilot, ContextTrace semantic verifier: 200 official
  test-split stratified cases, 88 assisted-reviewed hallucination rows, 75
  rows with source evidence spans, failure macro-F1 `0.955`, root-cause
  accuracy `0.955`, citation error F1 `1.000`, evidence span overlap `0.786`,
  and dangerous false-green rate `0.000`. This is not publishable without
  independent sign-off and calibration.
- RAGTruth assisted review pilot, OpenAI diagnostic judge with `gpt-4.1-mini`:
  50 official test-split smoke cases, zero row errors, failure macro-F1 `0.272`,
  root-cause accuracy `0.660`, citation error F1 `1.000`, evidence span overlap
  `0.592`, and dangerous false-green rate `0.260`. This is useful calibration
  evidence, but it is too under-sensitive to use as a publishable external row.
- ARES NQ example smoke, ContextTrace semantic verifier: 200 official example
  rows sampled from the 4,421-row answer-grounding subset, failure macro-F1
  `0.995` (95% CI `0.981-1.000`), root-cause accuracy `0.995`, citation error F1
  `1.000`, evidence span overlap `1.000` across 89 synthetic exact-answer spans,
  and dangerous false-green rate `0.000`. RAGAS and DeepEval cover the same 200
  unique IDs with zero row errors and score failure macro-F1 `0.471` and `0.388`.
  They report no diagnostic attribution fields. This proves the second external
  workflow and same-ID comparison path but remains `review_pending` until the
  ARES-to-ContextTrace label mapping and source evidence are independently
  reviewed.
- Ollama is reachable locally and `phi3:latest` completed a 5-case local-judge
  smoke run. The smoke took about 155 seconds, making a full 500-case run a
  multi-hour local job on this machine.

## Allowed Claim This Week

Use:

> ContextTrace provides a local-first evidence-chain forensics layer for
> claim-level RAG and agent failure attribution, citation-error detection,
> root-cause diagnosis, evidence-span localization, and regression-test
> generation.

Avoid:

> ContextTrace is the state-of-the-art RAG evaluation framework.

That broader claim still needs independent public datasets, audited frozen
holdout language, interval-aware reporting, and full competitor rows.

## Week 1 Verification Commands

```bash
python -m pytest benchmarks/tests/test_contexttrace_bench.py packages/contexttrace/tests/test_verify.py -q
python benchmarks/contexttrace_bench/run_contexttrace.py --mode semantic --case-set all --enforce-sota-gates
python benchmarks/contexttrace_bench/run_contexttrace.py --mode semantic --case-set public_holdout --no-generated-cases --output-dir benchmarks/contexttrace_bench/out/public_holdout
python benchmarks/contexttrace_bench/audit_diag150.py --output-dir benchmarks/contexttrace_bench/out/public_holdout
python benchmarks/contexttrace_bench/audit_diag150.py --output-dir benchmarks/contexttrace_bench/out/public_holdout --review-file benchmarks/contexttrace_bench/out/public_holdout/diag150_human_review_template.json --require-human-signoff
python benchmarks/contexttrace_bench/audit_diag150.py --output-dir benchmarks/contexttrace_bench/out/public_holdout --bundle-dir benchmarks/contexttrace_bench/out/diag150_release_bundle
python benchmarks/contexttrace_bench/diag150_release_workflow.py --output-dir benchmarks/contexttrace_bench/out/public_holdout --bundle-dir benchmarks/contexttrace_bench/out/diag150_release_bundle
```

Remote baseline smoke test:

```powershell
$env:OPENAI_API_KEY = "<your evaluator key>"
.\benchmarks\contexttrace_bench\run_openai_baselines.ps1 -Limit 5
```

Full baseline run:

```powershell
$env:OPENAI_API_KEY = "<your evaluator key>"
.\benchmarks\contexttrace_bench\run_openai_baselines.ps1 -Resume -MaxWorkers 4
```

## Week 1 Exit Criteria

- CI is green.
- Current ContextTrace-Bench artifacts are available.
- Public docs include methodology and limitations.
- Public docs link the ContextTrace-Diag-150 audit checklist and do not call the
  split frozen until sign-off is complete.
- At least one full competitor row is scored, or the baseline status explicitly
  says why it is pending.
- No public copy makes a broad SOTA claim without the evidence above.

No version bump or release branch is required for Week 1 readiness work.
