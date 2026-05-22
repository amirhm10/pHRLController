# Dynamic Model Identification

## Objective

Implement a staged dynamic-identification workflow for the pH lab CSV. The workflow tests whether `PH_2` can be predicted from inlet flows using equilibrium chemistry, static affine calibration, integer sample delay, and a first-order dynamic wrapper. This task intentionally excludes `PH_1`, target-pH metrics, MPC, RL, reward logic, and feedback-control code.

## Files Changed

- `run_dynamic_model_identification.py`
- `helpers/dynamic_model_identification.py`
- `helpers/dynamic_model_plotting.py`
- `reports/dynamic_model_identification_report.md`
- `change-reports/20260522_012352_dynamic_model_identification.md`

This workflow also depends on the existing lab-data and equilibrium charge-balance modules:

- `helpers/lab_data.py`
- `simulation/equilibrium_charge_balance_model.py`

## Implementation Summary

- Added a root runner that orchestrates loading, preprocessing, equilibrium prediction, staged identification, table generation, plotting, and report writing.
- Added dynamic-identification helpers for train/test trial splitting, affine calibration, lag search, first-order response simulation, tau fitting, metrics, and report tables.
- Added plotting helpers for measured-vs-predicted pH, scatter diagnostics, residual time plots, residual histograms, lag-search RMSE, example trial overlays, and train/test RMSE comparison.
- Used a chronological trial split: first 70 percent of trials for fitting and last 30 percent for held-out evaluation.
- Treated the dynamic time constant and effective volume as empirical diagnostics only because tubing geometry, dead volume, probe response time, and logging synchronization are unknown.

## Generated Artifacts

Result folder:

- `results/dynamic_model_identification_20260522_012324/`

Tables:

- `preprocessed_lab_data.csv`
- `dynamic_model_comparison.csv`
- `model_metrics_train_test.csv`
- `static_calibration_parameters.csv`
- `lag_search_metrics.csv`
- `dynamic_parameters.csv`
- `trial_split_summary.csv`

Figures:

- `measured_vs_dynamic_prediction_time.png`
- `measured_vs_dynamic_prediction_scatter.png`
- `residual_time_by_model.png`
- `residual_histogram_by_model.png`
- `lag_search_rmse.png`
- `dynamic_prediction_by_trial_examples.png`
- `train_test_metric_comparison.png`

Report:

- `reports/dynamic_model_identification_report.md`

## Verification Commands And Results

Compile:

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile run_dynamic_model_identification.py helpers\dynamic_model_identification.py helpers\dynamic_model_plotting.py helpers\lab_data.py simulation\equilibrium_charge_balance_model.py
```

Result: passed.

Run:

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_dynamic_model_identification.py
```

Result: passed.

Key metrics:

- Equilibrium baseline test RMSE: `0.4412 pH`
- Static calibrated test RMSE: `0.1148 pH`
- Lag calibrated test RMSE: `0.1148 pH`
- First-order dynamic test RMSE: `0.1148 pH`
- Selected lag: `0` samples
- Fitted dynamic time constant: `1.70 s`
- Median sampling interval: `69.98 s`

Artifact checks:

- All expected CSV tables were generated and non-empty.
- All expected PNG figures were generated and non-empty.
- `model_metrics_train_test.csv` contains no `PH_1`, `target_ph`, or target metrics.

## Known Limitations And Next Steps

- The improvement is dominated by static affine calibration. The data do not identify a useful sample delay or first-order dynamic effect at the current sampling interval.
- The fitted time constant is much smaller than the median sampling interval, so the first-order wrapper collapses to the static calibrated prediction.
- The residual mean on held-out data remains about `-0.0903 pH`, so calibration bias is not fully eliminated.
- The next safe step is a designed open-loop identification experiment with known flow-ratio steps, total-flow changes, sufficient settling time, and hardware metadata for mixing location, tubing volume, flow-cell volume, and pH probe response time.
