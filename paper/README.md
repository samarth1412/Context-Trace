# ARR paper workspace

This directory is an anonymous ARR manuscript driven by the frozen benchmark
snapshot and controlled simulated-pilot status. Regenerate all quantitative
tables with:

```bash
python paper/generate_tables.py \
  --rq4-results benchmarks/contexttrace_bench/out/rq4/simulated/rq4_results.json
```

The official ACL style files are pinned in this directory; see
`ACL_STYLE_SOURCE.md`. Preferred compilation is:

```bash
cd paper
latexmk -pdf -outdir=build main.tex
```

If `latexmk` is unavailable, use the equivalent sequence recorded in
`compile_log.txt`: `pdflatex`, `bibtex`, then two further `pdflatex` passes.
The current official-style build is `build/main.pdf`.

Run the page-limit and cross-root anonymity audits with:

```bash
python paper/audit_submission.py
```

Do not replace pending review or RQ4 cells with inferred values. Update the
tracked snapshot from reviewed artifacts first, regenerate the tables, and then
inspect the resulting diff.
