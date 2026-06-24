# Sequential Phase Plots

## Objective

Revise the data-preparation plots so the updated lab dataset is shown as one continuous sample sequence, while still marking the two different sampling-time phases visible in the original timestamp spacing.

## Files changed

- `helpers/data_preparation.py`
- `helpers/data_preparation_plotting.py`
- `run_data_preparation.py`
- `reports/data_preparation_report.md`

## Method or implementation summary

- Added `delta_t_min` from the original `time` column.
- Added sampling-phase labels using the two observed time-step regimes:
  - Phase 1: slower sampling, median `delta_t_min` about 2.35 min.
  - Phase 2: faster sampling, median `delta_t_min` about 1.15 min.
- Kept the plot x-axis as chronological `sample_index` so long wall-clock gaps do not create empty plot regions.
- Added muted phase shading and a phase separator line to all requested plot types.
- Replaced the brighter plotting colors with a more restrained palette.
- Added `sampling_phase_summary.csv` to the generated tables.
- Updated the report method, tables, figure links, interpretation, and notes.

## Generated artifacts

Generated under:

```text
results/data_preparation_20260624_123926/
```

Tables:

- `tables/prepared_time_feature_data.csv`
- `tables/sampling_phase_summary.csv`
- `tables/preparation_overview.csv`
- `tables/feature_summary.csv`
- `tables/column_mapping.csv`
- `tables/selected_time_and_last_four_columns.csv`

Figures:

- `figures/acid_flow_timeseries.png`
- `figures/acetate_flow_timeseries.png`
- `figures/water_flow_timeseries.png`
- `figures/ph_measured_timeseries.png`
- `figures/all_features_four_subplots.png`
- `figures/ph_with_acid_base_flows.png`

## Verification commands and results

```powershell
.\.venv\Scripts\python.exe -m py_compile run_data_preparation.py helpers\data_preparation.py helpers\data_preparation_plotting.py
```

Result: passed.

```powershell
.\.venv\Scripts\python.exe run_data_preparation.py
```

Result: completed successfully and wrote `results/data_preparation_20260624_123926/`.

Visual check: `all_features_four_subplots.png` uses sequential sample index without long empty spaces, with Phase 1 and Phase 2 shaded separately.

## Known limitations or next steps

- The phase split is based on the observed sampling interval regimes, not on chemical behavior.
- The phase separator is drawn along the sample-index axis because phase changes occur horizontally in time-series plots.
- Physical delay estimation should still use `delta_t_min` rather than assuming uniform sampling.
- Existing model-validation runners still point to the previous CSV name.
