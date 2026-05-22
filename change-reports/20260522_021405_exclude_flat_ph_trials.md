# Exclude Low-Information Flat-pH Trials

## Objective

Identify and exclude the nearly straight-line `PH_2` trial segments from model-validation metrics, because they are low-information for inlet-flow-to-pH model identification. Preserve the rows and diagnostic flags in preprocessed outputs so the exclusion remains auditable.

## Files Changed

- `helpers/lab_data.py`
- `helpers/first_principles_improvement.py`
- `AGENTS.md`
- `change-reports/20260522_021405_exclude_flat_ph_trials.md`

## Method Or Implementation Summary

- Added flat-pH trial diagnostics to preprocessing:
  - `trial_n_total`
  - `trial_n_model_valid`
  - `trial_ph_range`
  - `trial_log10_flow_ratio_range`
  - `trial_total_flow_range`
  - `uninformative_flat_ph_trial`
  - `valid_for_model_before_flat_trial_filter`
- Excluded rows from `valid_for_model` by default when:
  - trial has at least `5` samples,
  - `trial_ph_range <= 0.05`,
  - `trial_log10_flow_ratio_range >= 0.5`.
- Added these diagnostic columns to first-principles improvement comparison outputs.
- Documented the convention in `AGENTS.md`.

## Generated Artifacts

Verification result folders generated after the preprocessing change:

- `results/effective_static_chemistry_calibration_20260522_021302/`
- `results/settled_sample_static_calibration_20260522_021302/`
- `results/residual_structure_diagnostics_20260522_021302/`
- `results/activity_dilution_correction_20260522_021311/`
- `results/dynamic_model_identification_20260522_021326/`

## Verification Commands And Results

Compile:

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile helpers\lab_data.py helpers\first_principles_improvement.py run_effective_static_chemistry_calibration.py run_settled_sample_static_calibration.py run_residual_structure_diagnostics.py run_activity_dilution_correction.py
```

Result: passed.

Flat-trial diagnostic:

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -c "..."
```

Result:

- valid rows before filter: `1085`
- valid rows after filter: `990`
- excluded valid rows: `95`
- flagged trials: `8`, `9`, `10`, `33`

Runner verification:

- Effective static chemistry calibration completed.
- Settled-sample static calibration completed.
- Residual structure diagnostics completed.
- Activity/dilution correction completed.
- Dynamic model identification completed.
- Generated result tables and figures were non-empty.
- Generated tables had no `PH_1`, `target_ph`, or target metrics.

Updated headline metrics:

- Effective static equilibrium affine test RMSE improved to `0.0975 pH`.
- Settled primary bias/effective-pKa test RMSE improved to about `0.075 pH` on the small 19-sample test subset.
- Activity/dilution empirical physical correction test RMSE improved to `0.0912 pH`.
- Dynamic static/dynamic calibrated test RMSE improved to `0.0975 pH`; best lag remained `0`.

## Known Limitations Or Next Steps

- The filter removes low-information trials for model metrics, not from the raw CSV.
- The exclusion rule is intentionally conservative and auditable, but it is still a heuristic.
- The next report should explain that trials `8`, `9`, `10`, and `33` were excluded from fitted model metrics because `PH_2` stayed nearly flat while chemistry input changed strongly.
