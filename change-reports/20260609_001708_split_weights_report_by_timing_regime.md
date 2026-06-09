# Split Weights Report By Timing Regime

## Objective

Divide the weight-corrected equilibrium-affine report into two parts based on
the two measurement timing regimes:

- sessions `0-3`, approximately `140 s` sampling,
- sessions `4-6`, approximately `69 s` sampling.

## Files Changed

- `run_equilibrium_weights_data_report.py`
- `reports/equilibrium_affine_weights_data_report.md`
- `change-reports/20260609_001708_split_weights_report_by_timing_regime.md`

## Method Or Implementation Summary

Updated the runner to generate timing-regime diagnostics:

- `timing_regime_comparison.csv`,
- `timing_regime_summary.csv`,
- `timing_regime_metrics.csv`,
- `timing_regime_equilibrium_scatter.png`,
- `timing_regime_residual_boxplot.png`.

The report now includes:

- a `Split By Measurement Timing` section,
- `Part 1: Two-Minute Timing Regime`,
- `Part 2: One-Minute Timing Regime`,
- a timing-regime interpretation table,
- timing-regime figures and tables.

The timing-local affine fits are documented as diagnostic fits inside each
timing regime, not independent held-out controller-ready models.

## Generated Artifacts

Generated result folder:

```text
results/equilibrium_weights_data_report_20260609_001457/
```

Key added artifacts:

```text
tables/timing_regime_summary.csv
tables/timing_regime_metrics.csv
tables/timing_regime_comparison.csv
figures/timing_regime_equilibrium_scatter.png
figures/timing_regime_residual_boxplot.png
```

## Main Result

The two timing regimes behave differently.

| Quantity | Two-minute regime | One-minute regime |
| --- | ---: | ---: |
| sessions | `0-3` | `4-6` |
| median `dt_s` | `141.2375 s` | `69.3550 s` |
| valid rows | `307` | `655` |
| raw RMSE | `0.2209 pH` | `0.3503 pH` |
| global affine RMSE | `0.1862 pH` | `0.0941 pH` |
| timing-local affine RMSE | `0.1518 pH` | `0.0448 pH` |
| timing-local affine slope | `0.9603` | `1.0842` |

The one-minute regime is much more internally consistent after local affine
calibration. The two-minute regime should be reported separately when
discussing static model accuracy.

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
Equilibrium weights-data report artifacts complete: results\equilibrium_weights_data_report_20260609_001457
Tables written: results\equilibrium_weights_data_report_20260609_001457\tables
Figures written: results\equilibrium_weights_data_report_20260609_001457\figures
Key checks: valid rows=962; rows with any inferred flow above 10 mL/min=180; raw equilibrium test RMSE=0.3524 pH; affine test RMSE=0.0951 pH; bounded affine test RMSE=0.0929 pH; two-minute local RMSE=0.1518 pH; one-minute local RMSE=0.0448 pH; affine b0=-0.3164, b1=1.0106.
```

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -c "import pathlib,re; report=pathlib.Path('reports/equilibrium_affine_weights_data_report.md'); text=report.read_text(encoding='utf-8'); links=re.findall(r'!\[[^\]]*\]\(([^)]+)\)', text); missing=[link for link in links if not (report.parent / link).resolve().exists()]; print('image_links:', len(links)); print('missing:', missing)"
```

Result:

```text
image_links: 13
missing: []
```

```powershell
rg -n ";" reports/equilibrium_affine_weights_data_report.md
```

Result: no matches.

## Known Limitations Or Next Steps

- Timing-local affine fits are diagnostic fits on each timing block. They are
  not a replacement for held-out open-loop validation.
- Both timing regimes are still too slow to identify short transport delay or
  pH sensor response reliably.
- The one-minute regime should be preferred for static model interpretation,
  while sessions `0-3` should be treated as a separate earlier regime.
