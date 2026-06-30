# ARR submission checklist

Unchecked items are blockers or final-submission tasks. Do not mark them complete
without the corresponding artifact.

## Evidence

- [x] Full non-quick experiment run is recorded with hashes and environment data.
- [x] Same-ID baseline comparison reports unsupported diagnostics as N/A.
- [x] Eleven requested ablation rows are present, including explicit unavailable variants.
- [x] Error-analysis categories distinguish measured, unmeasured, and unrun cases.
- [ ] Independent RAGTruth review is complete and validation passes.
- [ ] Independent Diag-150 sign-off is complete and validation passes.
- [ ] RQ4 has at least three eligible non-author reviewers on all frozen cases.
- [ ] Review disagreements and corrections are versioned and rescored.
- [ ] Final SOTA gate returns `claim_ready`; otherwise remove every broad SOTA claim.

## Paper

- [x] Anonymous paper skeleton exists.
- [x] Dedicated Limitations section exists.
- [x] Ethics statement exists.
- [x] Six generated tables include review status.
- [x] Four figure specifications exist.
- [ ] Related work uses verified primary sources and complete BibTeX records.
- [ ] All claims are supported by the final reviewed snapshot.
- [ ] Official ARR/ACL style compiles without warnings that affect submission.
- [ ] Main content fits the current long-paper page limit.
- [ ] Abstract, title, checklist fields, and supplementary references are final.

## Anonymity and artifact

- [ ] Exact final artifact directory and archive are regenerated.
- [ ] Identity scan reports zero author names, handles, emails, local paths, and personal URLs.
- [ ] Git history and release links are absent from anonymous supplementary files.
- [ ] Private condition keys and reviewer identities are excluded.
- [ ] Clean-room install, full artifact tests, and reproduction command pass.
- [ ] Final archive SHA-256 and file count are recorded.

## Submission

- [ ] Official ARR dates and call-for-papers requirements are rechecked.
- [ ] Human-subjects or institutional review requirements are resolved for RQ4.
- [ ] Submission PDF is visually inspected page by page.
- [ ] Supplementary archive opens and contains only intended files.
- [ ] OpenReview author, conflict, subject-area, and reproducibility fields are complete.
