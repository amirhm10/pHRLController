# Compare mass-derived and commanded July 31 flows

## Objective

Back-calculate bottle-out flow separately for acetic acid, sodium acetate, and
Arium water, then compare each stream with its commanded flow at:

1. every adjacent raw CSV log interval
2. consecutive approximately one-minute intervals selected directly from CSV
   rows

No mass or command samples are averaged.

## Files inspected

- `Data/July31 BioSMB RL Test.csv`
- `analysis/plot_july31_biosmb_schedule.py`
- `Biosmb-run-online/Biosmb-run-online/biosmb_interface/manager.py`
- `change-reports/20260804_234831_correct_july31_water_and_combine_plots.md`
- `change-reports/20260805_095255_plot_raw_july31_input_logs.md`
- `results/july31_biosmb_schedule_20260731_205921/`

## Mathematical method

For two selected CSV rows at times \(t_0\) and \(t_1\), bottle-out flow is:

\[
F_{\mathrm{actual}}
=
\frac{m(t_0)-m(t_1)}{\rho}
\frac{60}{t_1-t_0},
\]

where mass is in grams, density is in g/mL, time is in seconds, and flow is in
mL/min.

The commanded comparison value is the logged command at the interval start:

\[
F_{\mathrm{command}}=F_{\mathrm{log}}(t_0).
\]

The default density is a provisional `1.0000 g/mL` for all three streams.
Command-line options allow each density to be replaced with a calibrated
value.

## Interval construction

### Adjacent raw-log intervals

Every consecutive pair of the 7,499 selected-run CSV rows is used. This gives
7,498 intervals per stream. The median interval is 1.143 s.

### One-minute intervals without averaging

The first real CSV row is selected from each elapsed-minute bin. Consecutive
selected rows define the mass-loss intervals. This gives 142 selected rows and
141 intervals per stream.

The actual interval durations range from 58.819 to 61.059 s, with a median of
59.991 s. Neither mass nor command values are averaged. Intervals containing a
command change are retained and explicitly flagged.

## Files changed

- `analysis/plot_july31_mass_derived_flows.py`
  - Adds configurable stream densities.
  - Builds adjacent-log and selected-minute interval tables.
  - Back-calculates actual flow from mass loss.
  - Flags command changes inside each interval.
  - Calculates metrics for all intervals and constant-command intervals.
  - Generates one two-panel comparison figure per stream.
- `change-reports/20260805_103133_compare_mass_derived_and_commanded_flows.md`
  - Records the method, artifacts, quantitative findings, and limitations.

The raw CSV and previous generated artifacts were not modified.

## Generated artifacts

Generated under:

`results/july31_biosmb_schedule_20260731_205921/`

Figures:

- `figures/july31_acid_actual_vs_commanded_flow.png`
- `figures/july31_sodium_acetate_actual_vs_commanded_flow.png`
- `figures/july31_water_actual_vs_commanded_flow.png`

Each figure shows adjacent raw-log intervals in the top panel and selected
one-minute intervals in the bottom panel.

Tables:

- `tables/mass_derived_flow_log_intervals.csv`
- `tables/mass_derived_flow_one_minute_intervals.csv`
- `tables/mass_derived_flow_metrics.csv`

Metadata:

- `mass_derived_flow_manifest.json`

The `results/` directory remains ignored by Git.

## Quantitative findings

### Adjacent raw-log intervals

The approximately one-second estimates are dominated by scale quantization:

- Acid actual-flow range: -7.34 to 120.00 mL/min.
- Sodium acetate actual-flow range: -25.70 to 124.44 mL/min.
- Water actual-flow range: -30.00 to 3.73 mL/min.

These extreme values are numerical consequences of differentiating discrete
mass changes over short and slightly irregular intervals. They are preserved
in the figures and tables as evidence that adjacent-row mass differences are
not a reliable instantaneous flow estimate.

### Selected one-minute intervals

For intervals without any command change:

| Stream | Intervals | Mean actual | Mean command | Bias | MAE | RMSE | Correlation |
|---|---:|---:|---:|---:|---:|---:|---:|
| Acid | 19 | 4.372 | 4.430 | -0.058 | 0.076 | 0.096 | 0.9996 |
| Sodium acetate | 21 | 3.779 | 3.979 | -0.200 | 0.497 | 0.992 | 0.9414 |
| Water | 141 | -0.509 | 5.000 | -5.509 | 5.509 | 5.533 | undefined |

All flow values and errors are in mL/min.

Acid mass-derived flow agrees closely with the command in the limited set of
constant-command one-minute intervals. Sodium acetate follows the command but
has larger discrepancies. The water mass channel is not physically credible
for this purpose because it produces a negative estimated flow while the
command remains 5 mL/min.

## Important limitations

- Densities are provisional. Calibrated densities will scale every
  mass-derived estimate.
- Of 141 selected-minute intervals, 122 acid intervals and 120 sodium acetate
  intervals contain a command change. A single command value cannot represent
  the whole interval, so those points are flagged and excluded from the
  constant-command metrics.
- Bottle mass loss measures liquid leaving the reservoir. It does not prove
  that the same amount reached the inline mixer.
- Adjacent-row estimates amplify scale quantization and timestamp jitter.
- The water mass record increases through much of this experiment and cannot
  validate water delivery.

## Verification

Commands:

```powershell
& '.venv\Scripts\python.exe' -m py_compile `
  'analysis/plot_july31_mass_derived_flows.py'

& '.venv\Scripts\python.exe' `
  'analysis/plot_july31_mass_derived_flows.py' `
  --output-dir `
  'results/july31_biosmb_schedule_20260731_205921'
```

Results:

- Python compilation passed.
- The complete analysis ran successfully.
- The adjacent-log table has 22,494 rows.
- The one-minute table has 423 rows.
- Both tables contain finite actual-flow values.
- All three figures were visually inspected.
- Figure labels explicitly state that no sample averaging is used.
- `git diff --check` passed.

## Recommended next experiment

Run a dedicated gravimetric pump test with constant commands held for several
minutes. Fit mass-versus-time slopes within each constant segment using
calibrated density. This will provide more constant-command intervals and
avoid the severe identifiability problem caused by changing the acid and
sodium commands approximately every 69 seconds.
