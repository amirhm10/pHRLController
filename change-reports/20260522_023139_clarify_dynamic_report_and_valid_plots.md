# Clarify Dynamic Report And Valid-Sample Plots

## Objective

Address the observed weird behavior around sample indices `205-290`, clarify that those trials are excluded from model metrics, and rewrite the main pH model report so it presents the original modeling story first and then the flat-trial removal as a patch.

## Files Changed

- `helpers/model_validation_plotting.py`
- `helpers/equilibrium_model_validation_plotting.py`
- `helpers/dynamic_model_plotting.py`
- `reports/dynamic_model_identification_report.md`
- `change-reports/20260522_023139_clarify_dynamic_report_and_valid_plots.md`

## Method Summary

- Updated model-validation time plots so measured `PH_2`, predictions, and residual traces use `valid_for_model` and break across invalid regions.
- Reran the three core workflows after the plotting change:
  - Henderson-Hasselbalch validation
  - equilibrium charge-balance validation
  - dynamic model identification
- Rewrote the report to show the original pre-filter story first, then the flat-trial patch and rerun results.
- Limited the report scope to only ideal Henderson-Hasselbalch, equilibrium charge balance, and dynamic identification.
- Added an explanation for why performance differs before index `205` and after index `291`.

## Generated Artifacts

- `results/henderson_hasselbalch_lab_validation_20260522_022832/`
- `results/equilibrium_charge_balance_lab_validation_20260522_022832/`
- `results/dynamic_model_identification_20260522_022832/`

## Verification Commands And Results

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile helpers\model_validation_plotting.py helpers\equilibrium_model_validation_plotting.py helpers\dynamic_model_plotting.py run_first_principles_data_comparison.py run_equilibrium_charge_balance_data_comparison.py run_dynamic_model_identification.py
```

Result: successful compile.

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_first_principles_data_comparison.py
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_equilibrium_charge_balance_data_comparison.py
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_dynamic_model_identification.py
```

Result: all three workflows completed and wrote timestamped artifacts.

Additional checks:

- Confirmed no zero-byte PNG figures in the three `20260522_022832` result folders.
- Confirmed no escaped-star KaTeX pattern remains in the report.
- Confirmed the report no longer discusses the four additional improvement runners.

## Known Limitations And Next Steps

- The flat trials are still present in exported preprocessed CSV files for audit, but they are excluded from metrics and cleaned model-validation traces.
- The difference before index `205` and after index `291` suggests nonstationarity, synchronization issues, dead volume, or sensor/mixing regime changes.
- A designed open-loop experiment is still needed to estimate physical delay, mixing volume, and sensor dynamics.
