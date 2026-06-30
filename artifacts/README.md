# ARR artifacts

`arr_anonymous/` is a generated, inspectable copy of the exact anonymous ZIP
payload and is intentionally ignored to avoid duplicating source files in git.
Regenerate both forms with:

```bash
python scripts/build_anonymous_artifact.py \
  --output out/anonymous-contexttrace-artifact.zip \
  --directory artifacts/arr_anonymous
```

The ZIP, checksum, validation report, and materialized directory must all be
regenerated from the exact final submission commit.
