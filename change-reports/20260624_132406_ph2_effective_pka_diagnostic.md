# PH2 Effective pKa Diagnostic Clarification

## Objective

Clarify the HH residual-shift diagnostic after confirming that `PH_1` is not reliable, `PH_2` is the reliable candidate, and `PH_2` is numerically the same as the last-column `pH-sensor`.

## Files Changed

- `helpers/hh_residual_shift_diagnostic.py`
- `run_hh_residual_shift_diagnostic.py`
- `reports/hh_residual_shift_diagnostic.md`

## Method Summary

- Added a reusable sensor-consistency diagnostic table comparing `observation.biosmb-sensors.PH_2` against `pH-sensor`.
- Added a charge-balance-versus-HH diagnostic using an internal bisection solver to test whether dilution/equilibrium effects could explain the residual shift.
- Updated the report to define the effective pKa calculation explicitly:
  `pKa_eff = pH_sensor - log10((C_acetate F_acetate) / (C_acid F_acid))`.
- Updated report interpretation so `PH_1` is treated only as an instrumentation/session-state flag, not as pH validation evidence.

## Generated Artifacts

- `results/hh_residual_shift_diagnostic_20260624_132406/`
- `results/hh_residual_shift_diagnostic_20260624_132406/tables/sensor_consistency.csv`
- `results/hh_residual_shift_diagnostic_20260624_132406/tables/charge_balance_metrics.csv`
- `results/hh_residual_shift_diagnostic_20260624_132406/figures/hh_residual_shift_overview.png`
- `results/hh_residual_shift_diagnostic_20260624_132406/figures/hh_residual_shift_local_context.png`

## Verification

- `.\.venv\Scripts\python.exe -m py_compile helpers\hh_residual_shift_diagnostic.py run_hh_residual_shift_diagnostic.py`
- `.\.venv\Scripts\python.exe run_hh_residual_shift_diagnostic.py`

Both commands completed successfully.

## Key Results

- `PH_2` and `pH-sensor` match over 962 rows with max absolute difference about `5e-10`.
- Best residual changepoint remains sample `183`, before the sampling-rate phase change at sample `309`.
- Mean HH residual changes from `-0.0366` before sample 183 to `-0.3364` for samples 183-308 and `-0.3466` after sample 309.
- Charge-balance predictions differ from HH by only about `0.001` pH on average and less than `0.009` pH in the checked segments, so dilution/equilibrium effects cannot explain the stable `0.3` pH bias.

## Known Limitations

The dataset does not include pH probe calibration records, stock concentration assay records, tubing/setup notes, or direct pump calibration measurements for the overnight boundary. The diagnostic identifies the timing and likely class of the shift, but it cannot prove which physical mechanism caused it.
