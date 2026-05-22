# Restore Report Visualizations

## Objective

Restore the richer visual evidence in the pH model report after the previous rewrite made the number of embedded figures too small.

## Files Changed

- `helpers/dynamic_model_plotting.py`
- `reports/dynamic_model_identification_report.md`
- `change-reports/20260522_023611_restore_report_visualizations.md`

## Method Summary

- Added the `+/- 0.2 pH` residual tolerance band to the dynamic residual-over-time plot.
- Reran the dynamic model-identification workflow to regenerate dynamic figures with the tolerance band.
- Expanded the report figure coverage to include:
  - measured-versus-predicted scatter plots,
  - residual-over-time plots,
  - residual histograms,
  - flow-ratio response plots,
  - flow and concentration diagnostics,
  - lag scans,
  - dynamic trial examples,
  - train/test RMSE comparison.
- Kept the report scoped to the three core model families: ideal Henderson-Hasselbalch, equilibrium charge balance, and dynamic identification.

## Generated Artifacts

- `results/dynamic_model_identification_20260522_023453/`

The Henderson-Hasselbalch and equilibrium figure links continue to use the already-generated filtered result folders:

- `results/henderson_hasselbalch_lab_validation_20260522_022832/`
- `results/equilibrium_charge_balance_lab_validation_20260522_022832/`

## Verification Commands And Results

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile helpers\dynamic_model_plotting.py run_dynamic_model_identification.py
```

Result: successful compile.

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_dynamic_model_identification.py
```

Result: successful run, with unchanged metrics and regenerated dynamic figures under `results/dynamic_model_identification_20260522_023453/`.

Additional checks:

- Confirmed `42` Markdown image embeds in the report.
- Confirmed all report image links resolve to existing files.
- Confirmed dynamic PNG figures are non-empty.
- Confirmed no escaped-star KaTeX pattern remains.

## Known Limitations And Next Steps

- The report is intentionally more visual and longer now.
- The added figures are diagnostic evidence only. The physical conclusion remains unchanged: static calibration helps, while delay and first-order dynamics are not identifiable from the current CSV.
