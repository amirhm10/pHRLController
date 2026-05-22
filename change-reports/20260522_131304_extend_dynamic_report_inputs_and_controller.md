# Extend Dynamic Report With Inputs And Controller Implications

## Objective

Extend the dynamic pH model report with input/output behavior, regime-specific input analysis, clarification of what the dynamic model is fitting, and implications for future acid/base/water flow selection.

## Files Changed

- `helpers/dynamic_model_identification.py`
- `helpers/dynamic_model_plotting.py`
- `run_dynamic_model_identification.py`
- `reports/dynamic_model_identification_report.md`
- `change-reports/20260522_131304_extend_dynamic_report_inputs_and_controller.md`

## Method Summary

- Added `regime_summary.csv` to the dynamic identification workflow.
- Added dynamic figures for:
  - measured input/output behavior,
  - prediction-only behavior,
  - regime input distributions,
  - trial-level input/output examples.
- Updated the report to explain that the dynamic model uses equilibrium charge-balance pH followed by ordinary least-squares affine calibration.
- Added a controller-readiness section explaining acid/base ratio degeneracy, scale selection, total-flow policy, and water-flow selection.
- Updated report links to the latest dynamic result folder:
  - `results/dynamic_model_identification_20260522_131048/`

## Generated Artifacts

- `results/dynamic_model_identification_20260522_131048/tables/regime_summary.csv`
- `results/dynamic_model_identification_20260522_131048/figures/measurement_input_output_behavior.png`
- `results/dynamic_model_identification_20260522_131048/figures/prediction_behavior_only.png`
- `results/dynamic_model_identification_20260522_131048/figures/regime_input_distributions.png`
- `results/dynamic_model_identification_20260522_131048/figures/trial_input_output_examples.png`

## Verification Commands And Results

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile helpers\dynamic_model_identification.py helpers\dynamic_model_plotting.py run_dynamic_model_identification.py
```

Result: successful compile.

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_dynamic_model_identification.py
```

Result: successful run. The run wrote `results/dynamic_model_identification_20260522_131048/`.

Additional checks:

- Confirmed all report image links resolve.
- Confirmed dynamic PNG figures are non-empty.
- Confirmed `regime_summary.csv` is non-empty.
- Confirmed no escaped-star KaTeX pattern remains.

## Known Limitations And Next Steps

- Regime analysis is diagnostic, not causal proof.
- The early and later regimes have similar flow ranges, so the performance difference likely reflects nonstationarity, timing, mixing, or measurement effects rather than simple input-range differences.
- A designed open-loop experiment is still needed before using this as a physical dynamic simulator or controller model.
