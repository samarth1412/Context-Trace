# Anonymous artifact checklist

- [x] Build uses tracked source files and deterministic ZIP timestamps.
- [x] Author repository URLs and package-index links are replaced.
- [x] Known author names, handles, email domains, and local usernames are scanned.
- [x] Generic email addresses and Windows/POSIX user paths are scanned.
- [x] Common API-token and private-key forms are scanned.
- [x] Private annotation and condition keys are excluded by path.
- [x] Paper sources, generated tables, protocols, tests, and licensed inputs are included.
- [x] Frozen full-run manifest and compact result outputs are included in complete builds.
- [x] Regenerate from paper/source payload commit `a5f73ad`.
- [x] Confirm validation status is `passed` with zero errors.
- [x] Run clean-room tests and the full reproduction command from an extracted archive.
- [x] Record the final ZIP SHA-256 and file count.

Verified archive: `out/anonymous-contexttrace-arr-final.zip`

- SHA-256: `082486c94e4f2055ebe6c9957f877255a71131bb867df10c0982474efa03c84a`
- Files: 226
- Exact final archive clean-room tests: 395 passed
- Clean-room full reproduction: completed; case-ID hashes and all reported
  main, baseline, and ablation metrics matched the source run
