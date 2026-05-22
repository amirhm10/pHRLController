# Add Data Dictionary And Sampling Analysis

## Objective

Extend the dynamic pH model report with a deeper explanation of the raw CSV columns, processed modeling columns, trial definitions, and sampling-time consistency.

## Files Changed

- `helpers/dynamic_model_identification.py`
- `run_dynamic_model_identification.py`
- `reports/dynamic_model_identification_report.md`
- `change-reports/20260522_133720_add_data_dictionary_and_sampling.md`

## Method Summary

- Added generic column profiling for raw and preprocessed data.
- Added sampling summaries overall, by regime, by session, and by trial.
- Updated the dynamic runner to save:
  - `raw_column_profile.csv`
  - `preprocessed_column_profile.csv`
  - `sampling_summary.csv`
  - `trial_sampling_summary.csv`
- Extended the report with:
  - a raw CSV column-by-column guide,
  - processed/derived column explanations,
  - trial and session definitions,
  - sampling-time consistency analysis.

## Generated Artifacts

- `results/dynamic_model_identification_20260522_133621/tables/raw_column_profile.csv`
- `results/dynamic_model_identification_20260522_133621/tables/preprocessed_column_profile.csv`
- `results/dynamic_model_identification_20260522_133621/tables/sampling_summary.csv`
- `results/dynamic_model_identification_20260522_133621/tables/trial_sampling_summary.csv`

## Verification Commands And Results

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile helpers\dynamic_model_identification.py run_dynamic_model_identification.py helpers\dynamic_model_plotting.py
```

Result: successful compile.

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_dynamic_model_identification.py
```

Result: successful run. The run wrote `results/dynamic_model_identification_20260522_133621/`.

Additional checks:

- Confirmed all report image links resolve.
- Confirmed the new profile and sampling CSV tables are non-empty.
- Confirmed no escaped-star KaTeX pattern remains.

## Known Limitations And Next Steps

- Column profiling is descriptive. It does not prove causality for the regime change.
- Sampling is not globally uniform: early and flat regions are about `141-142 s`, while later sessions are about `69-70 s`, with long gaps between sessions.
- Future dynamic identification should account for irregular sampling and session boundaries explicitly.
