# ARR paper workspace

This directory is an anonymous ARR draft driven by the frozen benchmark
snapshot. Regenerate all quantitative tables with:

```bash
python paper/generate_tables.py
```

Compile `main.tex` with the official ARR/ACL style files placed in this
directory. The fallback geometry package is for local syntax checks only and is
not submission formatting.

Do not replace pending review or RQ4 cells with inferred values. Update the
tracked snapshot from reviewed artifacts first, regenerate the tables, and then
inspect the resulting diff.
