# Update Dynamic Report After Flat-Trial Filter

## Objective

Update the main dynamic model-identification report after the latest Henderson-Hasselbalch, equilibrium charge-balance, and dynamic identification runners were executed with the default flat-trial preprocessing filter.

## Files Changed

- `reports/dynamic_model_identification_report.md`
- `change-reports/20260522_022218_update_dynamic_report_after_flat_trial_filter.md`

## Method Summary

- Read the latest generated result folders:
  - `results/henderson_hasselbalch_lab_validation_20260522_021555/`
  - `results/equilibrium_charge_balance_lab_validation_20260522_021608/`
  - `results/dynamic_model_identification_20260522_021628/`
- Updated the report with the latest raw steady-state metrics, dynamic train/test metrics, fitted static calibration parameters, fitted time constant, and figure links.
- Added an explicit preprocessing section explaining that low-information flat-pH trials are kept in exported data for audit but excluded from model metrics.
- Documented flagged trials `8`, `9`, `10`, and `33`, with `96` flat-pH rows flagged and `990` rows used after all filters.

## Generated Artifacts Used

- `results/henderson_hasselbalch_lab_validation_20260522_021555/tables/overall_metrics.csv`
- `results/henderson_hasselbalch_lab_validation_20260522_021555/tables/affine_diagnostic.csv`
- `results/equilibrium_charge_balance_lab_validation_20260522_021608/tables/overall_metrics.csv`
- `results/equilibrium_charge_balance_lab_validation_20260522_021608/tables/affine_diagnostic.csv`
- `results/dynamic_model_identification_20260522_021628/tables/preprocessed_lab_data.csv`
- `results/dynamic_model_identification_20260522_021628/tables/model_metrics_train_test.csv`
- `results/dynamic_model_identification_20260522_021628/tables/static_calibration_parameters.csv`
- `results/dynamic_model_identification_20260522_021628/tables/dynamic_parameters.csv`
- `results/dynamic_model_identification_20260522_021628/tables/trial_split_summary.csv`

## Verification

- Confirmed the report references the latest result folders `20260522_021555`, `20260522_021608`, and `20260522_021628`.
- Confirmed no stale old result folders remain in the report.
- Confirmed no escaped-star KaTeX pattern such as `^\*` remains.
- Confirmed updated key results:
  - raw HH RMSE `0.3976 pH`
  - raw equilibrium RMSE `0.3982 pH`
  - static calibrated dynamic test RMSE `0.0975 pH`
  - best lag `0` samples
  - fitted first-order time constant `1.8741 s`

## Known Limitations And Next Steps

- The report update did not rerun models because the user had already run the three validation scripts.
- The identified first-order time constant remains smaller than the median sampling interval, so it is only a diagnostic and not a trusted hardware parameter.
- The next modeling step should compare the four additional improvement runners after the same flat-trial preprocessing.
