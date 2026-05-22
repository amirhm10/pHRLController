# Dynamic Runner Artifact-Only Refactor

## Objective

Refactor the dynamic model-identification runner so it matches the project workflow: the runner creates timestamped tables and figures first, and the Markdown report is created later after reviewing those artifacts.

## Files Changed

- `run_dynamic_model_identification.py`
- `change-reports/20260522_013251_dynamic_runner_artifact_only.md`

## Implementation Summary

- Removed automatic report writing from `run_dynamic_model_identification.py`.
- Removed report-specific constants, imports, and helper functions from the runner.
- Kept the runner focused on orchestration: load data, preprocess, fit staged models, compute metrics, save tables, save plots, and print a concise console summary.
- Preserved all dynamic-identification logic in helpers and all generated artifacts under timestamped `results/dynamic_model_identification_YYYYMMDD_HHMMSS/` folders.

## Generated Artifacts

Verification run output:

- `results/dynamic_model_identification_20260522_013234/tables/`
- `results/dynamic_model_identification_20260522_013234/figures/`

Expected tables and figures were generated in the timestamped results folder. No Markdown report was written by the runner.

## Verification Commands And Results

Compile:

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile run_dynamic_model_identification.py
```

Result: passed.

Run:

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_dynamic_model_identification.py
```

Result: passed.

Console summary:

```text
Test RMSE: equilibrium=0.4412, static=0.1148, lag=0.1148, dynamic=0.1148.
Best test stage=Static calibrated; lag=0; tau=1.7 s.
```

Additional checks:

- All expected CSV tables were non-empty.
- All expected PNG figures were non-empty.
- `model_metrics_train_test.csv` contained no `PH_1`, `target_ph`, or target metrics.
- `reports/dynamic_model_identification_report.md` was not updated to the new run timestamp.

## Known Limitations And Next Steps

- The existing dynamic report file remains a separate report artifact from the previous report-generation pass.
- Future report creation should be done after selecting the desired result folder and reviewing the generated tables and figures.
