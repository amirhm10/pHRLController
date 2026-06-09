# Equilibrium Weights Data Report

## Objective

Analyze the new weight-corrected pH dataset:

```text
Data/dsp_db.biosmb-rl-controller-treated-dataset-weights.csv
```

The requested goal was to repeat the previous equilibrium-affine data report
using the corrected last four columns, then determine whether the
first-principles equilibrium model makes better sense and performs better.

## Files Changed

- `run_equilibrium_weights_data_report.py`
- `reports/equilibrium_affine_weights_data_report.md`
- `change-reports/20260608_235648_equilibrium_weights_data_report.md`

## Method Or Implementation Summary

Added a reproducible runner that:

- loads the new CSV,
- maps `flow-acid`, `flow-sodium`, `flow-water`, and `pH-sensor` into the pH
  modeling variables,
- reuses the existing equilibrium charge-balance model and affine calibration
  workflow,
- profiles raw and preprocessed columns,
- compares weight-backcalculated flows against legacy logged flow columns,
- saves lab metrics, bounded-flow sensitivity metrics, calibration parameters,
  sampling summaries, row summaries, and generated pump-grid tables,
- creates equilibrium-validation figures and new corrected-flow diagnostic
  figures.

Created a new report summarizing:

- BioSMB pH plumbing,
- the new last-four-column interpretation,
- row counts and nominal-bound checks,
- flow-source correction summaries,
- equilibrium equations,
- affine calibration results,
- old-versus-new model performance,
- whether the new dataset improves the first-principles interpretation.

## Generated Artifacts

Generated result folder:

```text
results/equilibrium_weights_data_report_20260608_235235/
```

Key tables:

- `tables/lab_metrics.csv`
- `tables/bounded_metrics.csv`
- `tables/calibration_parameters.csv`
- `tables/flow_source_comparison_summary.csv`
- `tables/row_summary.csv`
- `tables/preprocessed_lab_data.csv`
- `tables/lab_equilibrium_model_comparison.csv`

Key figures:

- `figures/corrected_input_output_behavior.png`
- `figures/legacy_vs_weight_flows.png`
- `figures/flow_correction_deltas.png`
- `figures/lab_equilibrium_validation_time.png`
- `figures/lab_equilibrium_validation_scatter.png`
- `figures/lab_equilibrium_residuals.png`
- `figures/lab_equilibrium_train_test_rmse.png`
- `figures/weights_residual_histogram.png`

## Main Result

The corrected dataset improves the first-principles model interpretation.

Previous logged-flow fit:

```text
PH_2 ~= 0.6567 + 0.7909 pH_eq
```

New weight-corrected fit:

```text
pH-sensor ~= -0.3164 + 1.0106 pH_eq
```

The near-unity slope is much more physically sensible. It suggests the corrected
flows largely remove the earlier apparent compression between equilibrium
chemistry and measured pH.

Key metric comparison:

| Metric | Previous logged-flow data | New weight-corrected data |
| --- | ---: | ---: |
| raw equilibrium test RMSE | `0.4412 pH` | `0.3524 pH` |
| raw equilibrium all-row RMSE | `0.3982 pH` | `0.3149 pH` |
| affine test RMSE | `0.0975 pH` | `0.0951 pH` |
| affine all-row RMSE | `0.1382 pH` | `0.1307 pH` |
| affine slope | `0.7909` | `1.0106` |

The final calibrated RMSE improves only slightly because affine calibration had
already corrected much of the old mismatch, but the raw first-principles model
and fitted calibration are clearly more coherent with the new data.

## Verification Commands And Results

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile run_equilibrium_weights_data_report.py
```

Result: passed.

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_equilibrium_weights_data_report.py
```

Result:

```text
Equilibrium weights-data report artifacts complete: results\equilibrium_weights_data_report_20260608_235235
Tables written: results\equilibrium_weights_data_report_20260608_235235\tables
Figures written: results\equilibrium_weights_data_report_20260608_235235\figures
Key checks: valid rows=962; rows with any inferred flow above 10 mL/min=180; raw equilibrium test RMSE=0.3524 pH; affine test RMSE=0.0951 pH; bounded affine test RMSE=0.0929 pH; affine b0=-0.3164, b1=1.0106.
```

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -c "import pathlib,re; report=pathlib.Path('reports/equilibrium_affine_weights_data_report.md'); text=report.read_text(encoding='utf-8'); links=re.findall(r'!\[[^\]]*\]\(([^)]+)\)', text); missing=[link for link in links if not (report.parent / link).resolve().exists()]; print('image_links:', len(links)); print('missing:', missing)"
```

Result:

```text
image_links: 11
missing: []
```

## Known Limitations Or Next Steps

- The new weight-backcalculated flows include `180` rows where at least one
  inferred flow is above the nominal `10 mL/min` pump bound. These rows were
  retained because the corrected columns were provided as the intended model
  inputs, but the above-bound values should be checked with the data provider.
- The new affine model is better and more physical, but it is still a static
  calibration. It should not be treated as a dynamic plant simulator.
- The next safe modeling step remains open-loop dynamic identification with
  verified routing, synchronized flow and pH logging, and long enough holds for
  settling.
