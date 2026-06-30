# Anonymous artifact checklist

- [x] Build uses tracked source files and deterministic ZIP timestamps.
- [x] Author repository URLs and package-index links are replaced.
- [x] Known author names, handles, email domains, and local usernames are scanned.
- [x] Generic email addresses and Windows/POSIX user paths are scanned.
- [x] Common API-token and private-key forms are scanned.
- [x] Private annotation and condition keys are excluded by path.
- [x] Paper sources, generated tables, protocols, tests, and licensed inputs are included.
- [x] Frozen full-run manifest and compact result outputs are included in complete builds.
- [x] Regenerate from paper/source payload commit `767d937`.
- [x] Confirm validation status is `passed` with zero errors.
- [x] Run clean-room tests and the full reproduction command from an extracted archive.
- [x] Record the final ZIP SHA-256 and file count.

Verified archive: `out/anonymous-contexttrace-arr-simulated-final.zip`

- SHA-256: `84b461570b78352fd8f0d907d422d2b5e2a50b06dfd4836badf4a124dac36812`
- Files: 274
- Exact final archive clean-room tests: 406 passed
- Clean-room full reproduction: completed; case-ID hashes and all reported
  main, baseline, and ablation metrics matched the source run
