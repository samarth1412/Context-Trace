# Anonymous artifact checklist

- [x] Build uses tracked source files and deterministic ZIP timestamps.
- [x] Author repository URLs and package-index links are replaced.
- [x] Known author names, handles, email domains, and local usernames are scanned.
- [x] Generic email addresses and Windows/POSIX user paths are scanned.
- [x] Common API-token and private-key forms are scanned.
- [x] Private annotation and condition keys are excluded by path.
- [x] Paper sources, generated tables, protocols, tests, and licensed inputs are included.
- [x] Frozen full-run manifest and compact result outputs are included in complete builds.
- [ ] Regenerate from the final paper commit.
- [ ] Confirm validation status is `passed` with zero errors.
- [ ] Run clean-room install, tests, and the reproduction command from the extracted archive.
- [ ] Record the final ZIP SHA-256 and file count in the submission notes.
