# Plot raw July 31 input logs without averaging

## Objective

Plot every selected-run flow record from the July 31 BioSMB CSV without
averaging, resampling, or reducing the approximately one-second log so the
available pump-flow behavior can be inspected.

## Files inspected

- `Data/July31 BioSMB RL Test.csv`
- `analysis/plot_july31_biosmb_schedule.py`
- `Biosmb-run-online/Biosmb-run-online/biosmb_interface/manager.py`
- `Biosmb-run-online/Biosmb-run-online/TD3_LAB_HANDOFF_REPORT.md`
- `change-reports/20260804_234831_correct_july31_water_and_combine_plots.md`
- `results/july31_biosmb_schedule_20260731_205921/`

## Method

The selected continuous run contains 7,499 CSV samples from
`2026-07-31T12:02:22.080Z` through `2026-07-31T14:24:10.535Z`. Every sample
was plotted at its actual timestamp using the corrected July 31 mapping:

- Arium water is `biosmb-flows[3]`.
- Acetic acid is `biosmb-flows[0]`.
- Sodium acetate is `biosmb-flows[1]`.

No values were averaged or resampled. If \(t_i\) is the recorded timestamp and
\(u_{j,i}\) is the logged value for stream \(j\), the figure plots the raw
pairs:

\[
\left(t_i, u_{j,i}\right), \qquad i = 1,\ldots,7499.
\]

## Sampling evidence

The selected-run sample intervals are:

- minimum: 0.104 s
- median: 1.143 s
- mean: 1.135 s
- 95th percentile: 1.216 s
- maximum: 2.116 s

The source is therefore approximately a one-second log, not an exact 1.000 s
grid. Preserving actual timestamps avoids inventing samples.

## Raw flow evidence

- Water is fixed at 5.00 mL/min with one unique logged value and no changes.
- Acid ranges from 1.04 to 9.48 mL/min with 122 sample-to-sample command
  changes.
- Sodium acetate ranges from 1.00 to 9.04 mL/min with 120 sample-to-sample
  command changes.
- Between changes larger than `1e-6 mL/min`, acid has no logged variation and
  sodium acetate has at most `5.96e-7 mL/min` numerical variation.

These records look perfectly held between controller changes.

## Important interpretation limitation

The BioSMB manager reads flow values from the OPC `FLOW` array and writes pump
commands back to that same `FLOW` array. The repository handoff report also
states that the team must confirm whether this value is a measured flow,
commanded flow, or another internal value.

Therefore this figure verifies that the logged `FLOW` register is stable. It
does not by itself prove that the physical pumps delivered those flows without
slip, occlusion, calibration error, or transient deviation.

## Files changed

- `analysis/plot_july31_biosmb_schedule.py`
  - Adds raw input-log sampling and change diagnostics.
  - Adds a three-subplot figure using all selected-run samples.
  - Records the no-averaging figure and diagnostics in future manifests.
- `change-reports/20260805_095255_plot_raw_july31_input_logs.md`
  - Records the method, evidence, limitation, and verification.

The raw CSV and existing figures were not modified.

## Generated artifact

Generated under:

`results/july31_biosmb_schedule_20260731_205921/figures/`

- `july31_raw_input_logs_no_averaging.png`

The PNG is 2704 by 1684 pixels. The `results/` folder remains ignored by Git.

## Verification

Commands:

```powershell
& '.venv\Scripts\python.exe' -m py_compile `
  'analysis/plot_july31_biosmb_schedule.py'

& '.venv\Scripts\python.exe' `
  'analysis/plot_july31_biosmb_schedule.py' `
  --output-dir `
  (Join-Path ([System.IO.Path]::GetTempPath()) `
    'codex_july31_raw_inputs_verify')
```

Results:

- Python compilation passed.
- The complete analysis ran successfully.
- The figure contains all 7,499 samples with no averaging or resampling.
- The corrected water channel is fixed at 5.00 mL/min.
- The figure was visually inspected for mapping, labels, time coverage, and
  readability.
- `git diff --check` passed apart from the Windows line-ending notice.

## Recommended next experiment

Record an independent delivered-flow measurement or perform a supervised
gravimetric pump test at several fixed commands. Compare measured flow with the
OPC `FLOW` register using mean bias, standard deviation, maximum deviation, and
settling time after each command change. That test can establish physical pump
performance, which the present command-log figure cannot.
