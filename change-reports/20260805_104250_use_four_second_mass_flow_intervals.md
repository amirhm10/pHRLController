# Use four-second mass-derived flow intervals

## Objective

Replace the adjacent approximately one-second mass-loss calculation with
non-averaged approximately four-second intervals because the bottle-scale
values do not update at every CSV row. Keep the existing one-minute interval
calculation unchanged.

## Files inspected

- `Data/July31 BioSMB RL Test.csv`
- `analysis/plot_july31_mass_derived_flows.py`
- `change-reports/20260805_103133_compare_mass_derived_and_commanded_flows.md`
- `results/july31_biosmb_schedule_20260731_205921/`

## Scale-update cadence

The time between nonzero mass-value changes in the selected run is:

| Stream | Mass updates | Median gap | 90th percentile | 95th percentile | Fraction within 4 s |
|---|---:|---:|---:|---:|---:|
| Acid | 3,803 | 2.264 s | 3.517 s | 4.640 s | 91.95% |
| Sodium acetate | 3,451 | 2.273 s | 4.609 s | 5.783 s | 87.83% |
| Water | 724 | 5.797 s | 8.038 s | 8.133 s | 7.75% |

The acid and sodium scales update more often than every four seconds on
average, but they do not update every approximately one-second CSV row.
Selecting four-second bins captures most acid and sodium updates and greatly
reduces the quantization error from adjacent-row differentiation.

The water scale remains a separate anomalous case and cannot support an
actual-flow calculation for this run.

## Water-channel audit

The July 31 command and scale mappings were re-audited after the water
mass-derived values appeared near zero:

- Pump 4 is exported as `biosmb-flows[3]` and is exactly 5.00 mL/min for the
  full selected run.
- The named water scale is `mfcs-mass.water-mass-grams`.
- The water scale rises from 3273.48 to 3345.30 g, a change of +71.82 g.
- A 5.00 mL/min water withdrawal over 2.363 h would instead produce roughly
  709 mL of reservoir depletion.
- Reversing the derivative sign would yield only about 0.51 mL/min, so a sign
  reversal would not repair the signal.
- The one-minute acid scale derivative correlates 0.974 with pump 1.
- The one-minute sodium scale derivative correlates 0.942 with pump 2.

The pump mapping is therefore supported, but the logged water scale is not a
valid reservoir-depletion measurement in this file. The likely causes are a
wrong physical vessel on scale C, an invalid scale connection, or a logger or
instrument configuration problem that cannot be distinguished from the CSV.

## Corrected interval method

The first real CSV row is selected from each elapsed four-second bin. Flow is
calculated between consecutive selected rows:

\[
F_{\mathrm{actual}}
=
\frac{m(t_0)-m(t_1)}{\rho}
\frac{60}{t_1-t_0}.
\]

No mass or command samples are averaged. The selected short intervals have:

- 2,128 selected rows
- 2,127 intervals per stream
- mean duration of 4.000 s
- median duration of 3.592 s
- minimum duration of 2.358 s
- maximum duration of 5.504 s

The duration is not exactly four seconds because the CSV timestamps are
irregular. Using the actual \(t_1-t_0\) in every calculation preserves the
recorded timing.

## Files changed

- `analysis/plot_july31_mass_derived_flows.py`
  - Adds `--short-interval-seconds`, defaulting to 4.0 s.
  - Replaces adjacent-row selection with the first real CSV row from each
    elapsed four-second bin.
  - Generalizes interval-row selection for four-second and one-minute data.
  - Retains the invalid water-scale derivative as a diagnostic column, sets
    water actual flow to missing, and excludes water from actual-versus-command
    metrics.
  - Labels the water figure as an invalid scale diagnostic while preserving
    the verified 5.00 mL/min pump-4 command.
  - Updates figure labels, metadata, console output, and limitations.
- `change-reports/20260805_103133_compare_mass_derived_and_commanded_flows.md`
  - Adds a correction notice pointing to this work item.
- `change-reports/20260805_104250_use_four_second_mass_flow_intervals.md`
  - Records the cadence audit, corrected method, results, and verification.

The raw CSV was read without modification.

## Regenerated artifacts

The following generated artifacts were intentionally replaced with the
corrected four-second top-panel analysis:

- `figures/july31_acid_actual_vs_commanded_flow.png`
- `figures/july31_sodium_acetate_actual_vs_commanded_flow.png`
- `figures/july31_water_actual_vs_commanded_flow.png`
- `tables/mass_derived_flow_log_intervals.csv`
- `tables/mass_derived_flow_one_minute_intervals.csv`
- `tables/mass_derived_flow_metrics.csv`
- `mass_derived_flow_manifest.json`

They remain under:

`results/july31_biosmb_schedule_20260731_205921/`

## Quantitative result

For four-second intervals without a command change:

| Stream | Intervals | Mean actual | Mean command | Bias | MAE | RMSE | Correlation |
|---|---:|---:|---:|---:|---:|---:|---:|
| Acid | 2,005 | 4.319 | 4.404 | -0.085 | 1.082 | 1.399 | 0.8687 |
| Sodium acetate | 2,007 | 3.874 | 3.983 | -0.109 | 1.212 | 1.572 | 0.8439 |

All flow values and errors are in mL/min.

Water is excluded from this table because the scale signal is invalid for
actual-flow estimation. The interval CSVs retain
`mass_derived_flow_ml_min` for diagnostic inspection, set
`actual_flow_ml_min` to missing for water, and mark the rows with
`mass_signal_valid_for_actual_flow = False`.

Compared with the superseded adjacent-row calculation:

- Acid MAE decreases from 3.902 to 1.082 mL/min.
- Acid correlation increases from 0.430 to 0.869.
- Sodium acetate MAE decreases from 3.753 to 1.212 mL/min.
- Sodium acetate correlation increases from 0.437 to 0.844.

The four-second interval is therefore substantially more informative, although
scale quantization remains visible.

The one-minute calculation and results are unchanged.

## Limitations

- Four seconds is a bin width, not a guarantee of an exact four-second row
  separation.
- Density remains a provisional 1.0000 g/mL for each stream.
- Actual water flow cannot be recovered from this CSV because the named water
  mass channel increases during positive pump operation.
- Mass loss measures liquid leaving a reservoir, not necessarily liquid
  reaching the mixer.

## Verification

Commands:

```powershell
& '.venv\Scripts\python.exe' -m py_compile `
  'analysis/plot_july31_mass_derived_flows.py'

& '.venv\Scripts\python.exe' `
  'analysis/plot_july31_mass_derived_flows.py' `
  --short-interval-seconds 4 `
  --output-dir `
  'results/july31_biosmb_schedule_20260731_205921'
```

Results:

- Python compilation passed.
- The workflow selected 2,128 four-second rows and 142 one-minute rows.
- The short-interval table contains 6,381 rows across three streams.
- The one-minute table contains 423 rows.
- Water has 2,127 short diagnostic intervals, but zero valid actual-flow
  values and zero command-tracking metric rows.
- All three regenerated figures were visually inspected.
- Figure subtitles report a 4.000 s mean short interval.
- `git diff --check` passed apart from the Windows line-ending notice.

## Recommended next experiment

Repeat the analysis using calibrated stream densities and dedicated
constant-command pump holds. A 30 to 60 second fitted mass slope will remain
more reliable than a four-second difference for final pump calibration, while
the four-second estimate is useful for visualizing short-term behavior.
