# Henderson-Hasselbalch Prepared Validation

## Objective

Add a reusable static Henderson-Hasselbalch validation workflow using the new prepared pH dataset as the working analysis path.

## Files changed

- `helpers/henderson_hasselbalch_prepared.py`
- `helpers/henderson_hasselbalch_prepared_plotting.py`
- `run_henderson_hasselbalch_prepared_validation.py`
- `reports/henderson_hasselbalch_prepared_validation.md`

## Method or implementation summary

- Reused `simulation.henderson_hasselbalch_model.HendersonHasselbalchModel`.
- Loaded the updated CSV through the prepared-data helper, selecting `time`, `flow-acid`, `flow-sodium`, `flow-water`, and `pH-sensor`.
- Used the acetate-buffer relation:

```text
pH_HH = pKa + log10((C_A F_A) / (C_H F_H))
```

- Used `pKa = 4.76`, `C_H = 0.1 mol/L`, and `C_A = 0.1 mol/L` from `simulation/config.py`.
- Treated water as a retained diagnostic variable, not a direct term in the ideal HH ratio.
- Added model comparison columns, overall metrics, sampling-phase metrics, and model metadata.
- Added the three requested figures:
  - measured pH and HH predicted pH,
  - measured/predicted pH with acid/base flows below,
  - pH minus predicted pH with a zero-error line.
- Reused the phase shading based on the prepared-data sampling phases.

## Generated artifacts

Generated under:

```text
results/henderson_hasselbalch_prepared_validation_20260624_125349/
```

Tables:

- `tables/prepared_time_feature_data.csv`
- `tables/hh_model_comparison.csv`
- `tables/overall_metrics.csv`
- `tables/metrics_by_sampling_phase.csv`
- `tables/sampling_phase_summary.csv`
- `tables/model_metadata.csv`

Figures:

- `figures/ph_vs_hh_prediction.png`
- `figures/ph_vs_hh_prediction_with_acid_base_flows.png`
- `figures/ph_minus_hh_prediction.png`

Report:

- `reports/henderson_hasselbalch_prepared_validation.md`

## Verification commands and results

```powershell
.\.venv\Scripts\python.exe -m py_compile run_henderson_hasselbalch_prepared_validation.py helpers\henderson_hasselbalch_prepared.py helpers\henderson_hasselbalch_prepared_plotting.py
```

Result: passed.

```powershell
.\.venv\Scripts\python.exe run_henderson_hasselbalch_prepared_validation.py
```

Result: completed successfully and wrote `results/henderson_hasselbalch_prepared_validation_20260624_125349/`.

Overall metrics:

- `n = 962`
- mean error `pH - pH_HH = -0.286`
- MAE `0.287`
- RMSE `0.314`
- max absolute error `0.568`
- measured/predicted correlation `0.913`

Visual check: all three requested figures rendered with sampling-phase shading and sequential sample index.

## Known limitations or next steps

- This is a static ideal-buffer model only.
- The model does not include calibration, transport delay, residence time, sensor response, or phase-dependent dynamics.
- Phase 2 has stronger correlation but larger negative bias, which supports calibration/dynamic modeling as the next step.
- Existing older validation runners still target the previous CSV path.
- The unrelated tracked deletion of `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv` was not touched or staged.
