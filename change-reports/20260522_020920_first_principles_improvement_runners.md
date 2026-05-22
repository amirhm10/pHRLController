# First-Principles Improvement Runners

## Objective

Add four artifact-only runners to test first-principles pH model improvements from the current lab CSV. The workflows cover effective static chemistry calibration, settled-sample calibration, residual structure diagnostics, and empirical activity/dilution correction. No controller, MPC, RL, reward logic, or automatic report generation was added.

## Files Changed

- `run_effective_static_chemistry_calibration.py`
- `run_settled_sample_static_calibration.py`
- `run_residual_structure_diagnostics.py`
- `run_activity_dilution_correction.py`
- `helpers/first_principles_improvement.py`
- `helpers/first_principles_improvement_plotting.py`
- `simulation/henderson_hasselbalch_model.py`
- `change-reports/20260522_020920_first_principles_improvement_runners.md`

## Method Or Implementation Summary

- Added shared helper logic for HH/equilibrium feature generation, trial-aware train/test splitting, static calibration fitting, settled-sample flags, residual correlations, binned residual summaries, and empirical correction models.
- Added shared plotting for model comparison time plots, scatter plots, residual histograms, train/test RMSE bars, settled-sample diagnostics, residual-feature maps, and empirical correction coefficients.
- Added four root runners that save timestamped result folders under `results/` and do not write reports automatically.
- Used `PH_2` only as the measured output and mapped flows as acid `[0]`, acetate `[1]`, and water `[2]`.

## Generated Artifacts

Final verification result folders:

- `results/effective_static_chemistry_calibration_20260522_020810/`
- `results/settled_sample_static_calibration_20260522_020827/`
- `results/residual_structure_diagnostics_20260522_020833/`
- `results/activity_dilution_correction_20260522_020839/`

Each folder contains non-empty `tables/` and `figures/` outputs.

## Verification Commands And Results

Compile:

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile run_effective_static_chemistry_calibration.py run_settled_sample_static_calibration.py run_residual_structure_diagnostics.py run_activity_dilution_correction.py helpers\first_principles_improvement.py helpers\first_principles_improvement_plotting.py simulation\henderson_hasselbalch_model.py
```

Result: passed.

Run:

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_effective_static_chemistry_calibration.py
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_settled_sample_static_calibration.py
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_residual_structure_diagnostics.py
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_activity_dilution_correction.py
```

Result: all four runners completed successfully.

Artifact checks:

- All expected CSV tables were non-empty.
- All expected PNG figures were non-empty.
- No generated table matched `PH_1`, `target_ph`, or `target`.

Headline findings:

- Effective static calibration: equilibrium affine test RMSE `0.1148 pH`; raw equilibrium test RMSE `0.4412 pH`.
- Settled-sample primary rule selected `100` total samples, with `81` train and `19` test samples. Bias/effective-pKa corrections had test RMSE about `0.092 pH` on this small settled subset.
- Residual diagnostics: raw equilibrium residual was most correlated with elapsed time `-0.5992`, log acid/base ratio `-0.5142`, and acid flow `0.4562`.
- Activity/dilution correction: empirical physical correction improved held-out RMSE to `0.1102 pH`, slightly better than affine equilibrium `0.1148 pH`, but with a higher condition number.

## Known Limitations Or Next Steps

- Settled-sample results use a proxy based on chemistry-input stability, not guaranteed true steady state.
- The empirical activity/dilution correction is not a thermodynamic Davies activity model and should not be interpreted as physical activity coefficients.
- The next report should compare these new result folders and decide whether the small RMSE gain from empirical correction is worth including in the next first-principles model.
