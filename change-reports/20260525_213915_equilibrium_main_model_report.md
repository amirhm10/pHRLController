# Equilibrium Charge-Balance Main Model Report

## Objective

Promote the equilibrium charge-balance model as the main first-principles
chemistry core for the pH project, while documenting the current evidence that
the raw model still needs empirical affine calibration to match `PH_2`.

## Files Changed

- `run_equilibrium_main_model_report.py`
- `helpers/equilibrium_main_model_report.py`
- `reports/equilibrium_charge_balance_main_model_report.md`
- `results/equilibrium_main_model_20260525_213424/`
- `change-reports/20260525_213915_equilibrium_main_model_report.md`

## Method Summary

- Loaded `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv`.
- Preprocessed the lab data with the existing `helpers.lab_data` mapping.
- Used only `PH_2` as the validation output.
- Computed raw equilibrium charge-balance predictions.
- Fit the affine calibration on train trials:

  ```text
  PH_2 = 0.6567 + 0.7909 * pH_eq
  ```

- Generated a 1000-point pump-grid sweep across 1-10 mL/min for acid,
  acetate, and water.
- Generated a target-flow sweep over pH 3.76-5.76 at water flows 1, 5,
  and 10 mL/min.
- Wrote a project-level Markdown report with equations, lab validation,
  generated-data interpretation, figures, limitations, and literature links.

## Generated Artifacts

Tables:

- `results/equilibrium_main_model_20260525_213424/tables/lab_equilibrium_model_comparison.csv`
- `results/equilibrium_main_model_20260525_213424/tables/lab_metrics.csv`
- `results/equilibrium_main_model_20260525_213424/tables/calibration_parameters.csv`
- `results/equilibrium_main_model_20260525_213424/tables/generated_pump_grid.csv`
- `results/equilibrium_main_model_20260525_213424/tables/generated_target_flow_sweep.csv`
- `results/equilibrium_main_model_20260525_213424/tables/generated_grid_summary.csv`

Figures:

- `results/equilibrium_main_model_20260525_213424/figures/lab_equilibrium_validation_time.png`
- `results/equilibrium_main_model_20260525_213424/figures/lab_equilibrium_validation_scatter.png`
- `results/equilibrium_main_model_20260525_213424/figures/lab_equilibrium_residuals.png`
- `results/equilibrium_main_model_20260525_213424/figures/lab_equilibrium_train_test_rmse.png`
- `results/equilibrium_main_model_20260525_213424/figures/generated_pump_grid_heatmaps.png`
- `results/equilibrium_main_model_20260525_213424/figures/generated_target_flow_sweep.png`
- `results/equilibrium_main_model_20260525_213424/figures/generated_water_dilution_sensitivity.png`

## Verification

Compiled non-hardware code:

```powershell
& 'C:\Users\hamed\miniconda3\envs\rlenv\python.exe' -m py_compile run_equilibrium_main_model_report.py helpers/equilibrium_main_model_report.py
```

Result: passed.

Ran the new runner:

```powershell
& 'C:\Users\hamed\miniconda3\envs\rlenv\python.exe' run_equilibrium_main_model_report.py
```

Result: completed and wrote `results/equilibrium_main_model_20260525_213424/`.

Metric check:

```text
raw equilibrium all-row RMSE: 0.3982432760
equilibrium affine held-out test RMSE: 0.0974539227
```

Both match the expected values of about `0.3982` and `0.0975 pH`.

Artifact check:

```text
Missing or empty artifacts: []
Artifact and metric checks passed.
```

Markdown local-link audit:

```text
Checked 14 local report references.
All local report references exist.
```

Sensor/target-use check:

- `PH_1` appears only in report statements saying it is not used.
- `target_ph` appears only in generated target-flow sweep helper columns.
- The validation metrics are computed from `PH_2`, acid flow, acetate flow,
  and water flow.

Visual spot-check:

- Opened the lab time response, pump-grid heatmap, target-flow sweep, and
  water-dilution sensitivity figures.
- Adjusted the heatmap layout and water-sensitivity y-axis formatter before
  finalizing the result folder.

## Known Limitations And Next Steps

- The raw equilibrium model is still biased and compressed relative to `PH_2`.
- The affine calibration is empirical and specific to the current lab CSV.
- The generated pump-grid and target-flow tables are offline model-generated
  artifacts, not controller code.
- No MPC, RL, reward, policy, or autonomous feedback-control code was added.
- The next safe experiment remains open-loop dynamic identification with long
  holds, known valve paths, tubing geometry, and `PH_2` logging.
