# HH Residual Shift Diagnostic

## Objective

Diagnose why the Henderson-Hasselbalch residual changes inside the slower-sampling phase before the main sampling-rate phase change.

## Files changed

- `helpers/hh_residual_shift_diagnostic.py`
- `helpers/hh_residual_shift_plotting.py`
- `run_hh_residual_shift_diagnostic.py`
- `reports/hh_residual_shift_diagnostic.md`
- `helpers/data_preparation_plotting.py`

## Method or implementation summary

- Added a residual changepoint scan on `pH - pH_HH`.
- Compared three segments:
  - pre-jump samples `0-182`
  - post-jump same-sampling samples `183-308`
  - Phase 2 samples `309-961`
- Compared HH predictions using the treated last-column flows versus raw `observation.biosmb-flows[0:2]`.
- Computed effective `pK_a` and the equivalent stock-ratio factor needed to explain the residual offset.
- Ranked raw numeric columns by local mean shift around the residual jump.
- Saved long-gap event evidence showing reservoir mass resets and pH sensor changes.
- Added figures for the residual overview and local transition context.
- Extended phase-background plotting with an optional `label_phases` flag so zoomed plots can use shading without overcrowding labels.

## Generated artifacts

Generated under:

```text
results/hh_residual_shift_diagnostic_20260624_130716/
```

Tables:

- `tables/changepoint.csv`
- `tables/segment_metrics.csv`
- `tables/flow_source_metrics.csv`
- `tables/local_context.csv`
- `tables/column_shift_ranking.csv`
- `tables/selected_column_medians.csv`
- `tables/long_gap_events.csv`
- `tables/hh_model_comparison_with_shift_context.csv`

Figures:

- `figures/hh_residual_shift_overview.png`
- `figures/hh_residual_shift_local_context.png`

Report:

- `reports/hh_residual_shift_diagnostic.md`

## Verification commands and results

```powershell
.\.venv\Scripts\python.exe -m py_compile run_hh_residual_shift_diagnostic.py helpers\hh_residual_shift_diagnostic.py helpers\hh_residual_shift_plotting.py helpers\data_preparation_plotting.py
```

Result: passed.

```powershell
.\.venv\Scripts\python.exe run_hh_residual_shift_diagnostic.py
```

Result: completed successfully and wrote `results/hh_residual_shift_diagnostic_20260624_130716/`.

Main diagnostic results:

- Best residual changepoint: sample `183`
- Sampling phase change: sample `309`
- Mean residual before jump: `-0.037`
- Mean residual after jump: `-0.345`
- Residual step change: `-0.308`
- Effective `pK_a` before jump: about `4.72`
- Effective `pK_a` after jump: about `4.42`
- Equivalent post-jump base/acid stock-ratio factor: about `0.46`

Visual check: both diagnostic figures rendered correctly. The local context figure shows the residual jump coinciding with `PH_1` jumping near 8 and reservoir masses resetting upward.

## Known limitations or next steps

- The diagnostic identifies the likely session boundary and class of cause, but the CSV does not contain direct pH calibration or stock concentration records.
- The result supports separate calibration regimes before and after sample 183.
- Raw observed flow columns do not explain the shift.
- The unrelated tracked deletion of `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv` was not touched or staged.
