# Fix KaTeX Star Notation

## Objective

Fix KaTeX parse errors in the dynamic model identification report and document the notation rule in `AGENTS.md` so future reports avoid the same issue.

## Files Changed

- `reports/dynamic_model_identification_report.md`
- `AGENTS.md`
- `change-reports/20260522_014602_fix_katex_star_notation.md`

## Method Or Implementation Summary

- Replaced invalid KaTeX notation such as `b_0^\*`, `d^\*`, and `\tau^\*` with KaTeX-safe notation such as `b_0^{*}`, `d^{*}`, and `\tau^{*}`.
- Added a report-style instruction to `AGENTS.md`: use `x^{*}` instead of `x^\*` because KaTeX treats `\*` as an undefined command.

## Generated Artifacts

No new result folders, tables, or figures were generated. This was a report and workflow-instruction fix only.

## Verification Commands And Results

Checked for remaining invalid star patterns:

```powershell
Select-String -Path reports\dynamic_model_identification_report.md -Pattern '\\\*|\^\\\*|\^\*'
```

Result: no matches.

Checked that the report now contains KaTeX-safe starred optima:

```powershell
Select-String -Path reports\dynamic_model_identification_report.md -Pattern '\^\{\*\}'
```

Result: safe `^{*}` notation is present.

Checked that `AGENTS.md` contains the future-work instruction:

```powershell
Select-String -Path AGENTS.md -Pattern 'KaTeX'
```

Result: instruction is present.

## Known Limitations Or Next Steps

- This fixes the known undefined-control-sequence issue for starred optima.
- Future report edits should avoid escaped asterisks inside math mode and prefer explicit braces for superscripts.
