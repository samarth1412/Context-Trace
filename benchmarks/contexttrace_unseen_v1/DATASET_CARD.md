# Dataset card for ContextTrace-Unseen-v1

## Dataset summary

ContextTrace-Unseen-v1 is a planned claim-level evaluation corpus for diagnosing
RAG grounding, citation, retrieval-stage, abstention, and source-condition
failures. Its distinguishing design goal is independence from all evidence used
to develop or calibrate ContextTrace.

Current status: **Natural OOD sources acquired and generation schedule
locked**. There are zero generated traces, no frozen unlabeled manifest, and no
annotations. The temporal/source-condition sources have not been acquired.

## Motivation

Existing ContextTrace results establish calibration behavior but do not show
generalization to genuinely unused source families, domains, or time periods.
This dataset is intended to support a one-time test of:

- claim verdict and failure-label generalization;
- observable root-cause attribution;
- minimal evidence localization;
- citation correctness;
- selective abstention and dangerous false greens;
- transfer to stale, superseded, noncanonical, or low-authority evidence.

The dataset does not establish real-world truth or hidden causal internals that
are absent from a recorded trace.

## Planned composition

### Natural OOD track

Target 400 traces, with 300–500 eligible:

- three top-level source groups;
- at least 12 source families per group and 36 overall;
- no family above 10% of the track;
- BM25, dense-vector, and hybrid retrieval in every group;
- multiple chunk sizes and overlaps;
- reranking enabled and disabled;
- at least two pinned generator model families;
- clean answers and naturally failing answers;
- varied context sizes, answer lengths, and citation formats.

The three broad groups are sampling strata. The disjoint `domain_id` is finer,
such as a product ecosystem, regulatory jurisdiction/topic, or operational
service family, and must not occur in the calibration registry.

### Temporal/source-condition track

Target approximately 100 traces using independently established pairs:

- archived policy to current policy;
- old API documentation to replacement API;
- noncanonical copy to canonical source;
- low-authority summary to authoritative source.

Each pair requires source snapshots, dates where available, canonical
identifiers, and a written authority basis created without inspecting system
predictions.

## Data instance

An eligible instance consists of:

- query and unedited generated answer;
- complete retrieved chunk set and selected context identifiers;
- citations;
- source snapshot references and cryptographic hashes;
- retriever, chunker, reranker, generator, prompt, and generation settings;
- collection timestamps and immutable model/configuration revisions;
- license/access and privacy classifications;
- no claim verdict, root cause, evidence span, reviewer note, prediction, or
  other label-derived field.

Raw source and trace bytes are retained separately from the public metadata
manifest. Redistribution follows the most restrictive applicable source term.

## Collection process

Sources are approved before acquisition. A balanced configuration schedule is
fixed before generation. Actual RAG pipelines produce candidate answers without
calling either evaluated ContextTrace verifier. Cases are retained or excluded
only by predeclared metadata, privacy, license, pipeline-validity, and
chain-of-custody rules—not because an answer appears easy, difficult, correct,
or favorable.

See `COLLECTION_PROTOCOL.md`.

## Splits

There is one untouched test role. Random row-level train/test splitting is
prohibited.

Development and annotation-pilot data must use separate documents, source
families, domain IDs, publication windows, and case IDs. They are recorded in
the calibration registry and cannot later enter the untouched corpus.

## Labels

No labels exist. Annotation is a later phase and will be stored outside the
implementation workspace under a label custodian. Candidate and frozen
unlabeled files may never contain gold fields or label-derived metadata.

## Intended uses

- one-time locked evaluation of frozen ContextTrace versions;
- same-ID baseline comparison on capabilities each baseline actually exposes;
- domain, source-condition, and selective-risk reporting;
- reproducible methodological research with disclosed limitations.

## Prohibited uses

- verifier training or tuning before the one-time test;
- threshold, taxonomy, prompt, or output-schema adjustment using test results;
- presenting manually authored or synthetic failures as natural;
- repeated test-set scoring during development;
- truth verification beyond the recorded evidence;
- production-safety certification;
- redistribution that violates source terms;
- deanonymization or extraction of personal information.

## Biases and limitations

The corpus will be bounded by public source availability, licensing,
English-language coverage unless amended, chosen RAG configurations, generator
access, and annotator judgments. Public documentation is not representative of
private enterprise knowledge bases. Source authority rules can be
jurisdiction- and task-dependent. Natural failures may be rare in some strata,
which can make individual class estimates inconclusive.

The fixed manifest records these limitations rather than modifying the sample
after labels or predictions are visible.

## Licensing and privacy

Dataset metadata and project-authored code can be distributed under repository
terms. Third-party source text and generated outputs retain their applicable
terms. A source with `metadata_only` redistribution may appear in the public
manifest but its raw bytes may not be bundled. Prohibited or restricted sources
cannot enter the public untouched freeze.

See `PRIVACY_AND_LICENSE.md`.

## Versioning and retirement

The initial frozen corpus will be `ContextTrace-Unseen-v1`. Its unlabeled
manifest and hash are immutable. Once any evaluated predictions or errors are
inspected, the dataset becomes evaluation evidence and must be treated as
calibration for future verifier development. Corrections are additive,
versioned, and preserve the original artifact and seal.

## Maintenance

No maintainer or release record is assigned because collection has not begun.
External publication, dataset release, and label release require explicit user
authorization.
