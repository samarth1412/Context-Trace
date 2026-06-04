# Validation Reports

Keep generated HTML reports out of git by default.

If a report is intentionally checked in for a published validation case, include:

- the source trace or saved response that produced it
- exact command used to generate it
- short explanation of what the report demonstrates

Scratch reports should stay under `.contexttrace/reports/` or another ignored output directory.
