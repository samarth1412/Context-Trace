# ContextTrace-Unseen-v1 privacy and license policy

Policy version: 1.0  
Status: active for Phase 2 collection  
Date: 2026-07-24

## Scope

This policy covers source acquisition, local snapshots, RAG inputs and outputs,
provider records, manifests, and eventual artifact publication. It does not
authorize collection; each source family and external model still requires
approval.

## Source eligibility

The production untouched corpus accepts only sources that are:

- publicly accessible without bypassing technical or contractual controls;
- explicitly permitted for the proposed collection use;
- reviewed before acquisition;
- attributable and redistributable at least at the metadata level;
- free of known secrets or private organizational content;
- compatible with publication of the required provenance metadata.

Authentication-gated, private, paywalled, confidential, or
`authorized_restricted` sources fail the production freeze. Public pages that
contain personal information require documented PII review before a case can be
eligible.

## License record

Every source records:

- license/terms identifier and URL when available;
- review status, reviewer, and review time;
- attribution requirement;
- redistribution class;
- access restrictions.

Redistribution classes:

- `permitted`: approved raw snapshot and derived trace content may be bundled,
  subject to attribution and other terms;
- `metadata_only`: public artifacts may contain identifiers, hashes, and
  allowed metadata, but not the raw source text;
- `prohibited`: the source cannot enter a publicly redistributable untouched
  corpus and is rejected by the production policy.

A multi-source case inherits the most restrictive class. A case manifest may
not claim broader rights than any source it uses.

Generated outputs may carry provider-specific restrictions independent of
source licenses. Provider/model selection must record whether prompts, outputs,
and model identifiers can be redistributed.

## Privacy classification

Source classifications:

- `public`: reviewed public material with no identified personal-data concern;
- `public_pii_review_required`: public material requiring documented review;
- `authorized_restricted`: ineligible for the production untouched freeze.

Case classifications:

- `public`;
- `public_pii_reviewed`.

The freeze fails if a case using a review-required source is not marked
`public_pii_reviewed`.

PII review records the category and disposition without copying unnecessary
personal data into the manifest. Incidental names or contact details not needed
for the research question should be removed from derived trace content under a
versioned transformation, with the raw source hash retained only where lawful.
Material transformations must be disclosed and cannot alter the evidence
relationship being evaluated.

## Secrets and credentials

Never place in a source, trace, manifest, log, or committed artifact:

- API tokens, passwords, cookies, or authorization headers;
- private endpoint URLs or account identifiers;
- local credential paths;
- unredacted provider request headers;
- annotator or participant contact information;
- private repository or organization data.

Credentials are supplied through the approved runtime secret mechanism and are
never included in configuration hashes. Logs must be scanned before retention.

## Local storage and access

- Keep raw snapshots and raw provider responses outside Git unless their terms
  explicitly permit publication.
- Use least-privilege filesystem permissions.
- Separate candidate inputs from future gold labels.
- Maintain an access log for restricted working artifacts.
- Backups inherit the same restrictions and retention schedule.
- Delete temporary provider payloads after verified transfer when retention is
  not permitted.

The public frozen manifest contains metadata and hashes, not secrets or gold
labels.

## External providers

Before using a hosted generator or baseline, record:

- provider and immutable model identity;
- data-retention and training-use settings;
- region or jurisdiction where relevant;
- prompt/output redistribution terms;
- cost ceiling;
- retry policy;
- whether source content can legally be sent to that provider.

Do not send `metadata_only`, restricted, or personal-data-containing source text
to a provider unless the terms and approved protocol explicitly allow it.

Paid API use requires explicit user authorization.

## Incident handling

If restricted content, PII, a secret, or a license conflict is discovered:

1. stop collection and prevent further synchronization;
2. preserve a minimal incident record without reproducing the sensitive value;
3. rotate exposed credentials immediately where applicable;
4. quarantine affected artifacts;
5. determine whether provider deletion or source-owner action is required;
6. invalidate any affected candidate or frozen corpus version;
7. document the correction without silently rewriting the original seal.

Privacy, access, or licensing uncertainty resolves to exclusion, not assumed
permission.

## Publication review

Before publishing a manifest or artifact:

- rerun secret and PII scans;
- verify every redistribution class;
- generate required attribution;
- confirm hashes do not expose restricted content by themselves;
- verify raw files are omitted for `metadata_only` sources;
- confirm provider output terms;
- obtain explicit user authorization for external publication.

No publication has occurred under this policy.
