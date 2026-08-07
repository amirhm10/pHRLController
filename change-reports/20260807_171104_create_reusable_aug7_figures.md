# Create Reusable Aug. 7 Figures

## Objective

Create July 31-style figures for the cleaned Aug. 7 BioSMB experiment while
keeping raw/short-interval results separate from one-minute results. Move the
stable data preparation and plotting logic into reusable helpers so future
experiments can be processed by configuration rather than new plotting code.

## Research contract

- Question: What do the Aug. 7 pH, FLOW-register, and gravimetric signals look
  like at raw/short-second and one-minute resolutions?
- Decision supported: Which resolution should be used for visual diagnostics
  and subsequent quantitative modeling?
- Scope: `Data/Aug7 BioSMB RL Test.csv`, Aug. 7 UTC only.
- Allowed actions: create reusable code, tests, tables, figures, and a manifest.
- Evidence cutoff: data ending `2026-08-07T14:31:27.699Z`.
- Deliverable: separate seconds and minutes result packages.

## Files changed

- `helpers/biosmb_experiment_data.py`
  - Defines reusable stream mappings with explicit physical units and
    experiment-specific mass-signal validity.
  - Loads and validates BioSMB CSVs with an optional UTC-date filter.
  - Detects controller actions from controlled FLOW-register changes.
  - Reconstructs configurable ping-pong target schedules.
  - Aggregates independent elapsed-time bins.
  - Calculates mass-derived flow using exact timestamp differences and
    time-weighted commands.
  - Provides tracking and mass-flow metrics.
- `helpers/biosmb_experiment_plotting.py`
  - Plots every raw second-level pH and command log without averaging.
  - Plots one-minute pH and command summaries with within-bin variability.
  - Plots one stream at one gravimetric resolution per figure.
  - Automatically adds a full-range and central-range pair when short-interval
    outliers would otherwise hide the normal trajectory.
- `analysis/plot_biosmb_experiment.py`
  - Adds a generic CLI runner with configurable input, UTC date, label, target
    values, steps per setpoint, intervals, densities, and water-mass validity.
  - Saves separate `seconds/` and `minutes/` figures and tables.
  - Saves shared reconstructed action and block metadata.
  - Saves input hash, effective configuration, repository state, artifacts,
    limitations, and a claim ledger in a manifest.
- `tests/test_biosmb_experiment_plotting.py`
  - Adds five deterministic tests covering schedule cycling, action/block
    assignment, mass-flow sign and units, invalid water handling, independent
    minute aggregation, and figure generation.
- `change-reports/20260807_171104_create_reusable_aug7_figures.md`
  - Records implementation, artifacts, evidence, and verification.

Unrelated existing modifications under `.agents/skills/` and
`Biosmb-run-online/Biosmb-run-online/main.py` were not changed or included.

## Method

### Seconds package

- Tracking and input figure: every one of the 14,426 raw CSV records at its
  actual timestamp, with no averaging or resampling.
- Gravimetric figures: first real CSV row in each elapsed four-second bin.
- Exact consecutive selected-row duration is used in every mass derivative.
- FLOW commands are time-weighted using all raw rows within each interval.

### Minutes package

- Tracking and input figure: 274 independent elapsed 60-second bins.
- PH_2 is shown as mean plus or minus within-minute standard deviation.
- Commands are shown as one-minute means with their within-minute ranges.
- Gravimetric figures: first real CSV row in each elapsed 60-second bin, with
  no mass averaging.

For both packages, reservoir-out flow is:

\[
F_{\mathrm{mass}}
=
\frac{m(t_0)-m(t_1)}{\rho}
\frac{60}{t_1-t_0}.
\]

The provisional density is 1 g/mL for every stream. Acid and sodium-acetate
mass signals are valid. The water mass signal remains diagnostic only.

The target schedule is reconstructed as 3.9, 4.3, 4.7, 5.1, and 5.5 pH in
ping-pong order with 30 detected actions per block. The source CSV does not log
`target_ph`, so target-dependent metrics remain reconstructed evidence.

## Generated artifacts

Output folder:

`results/aug7_biosmb_figures_20260807_210733/`

### Seconds figures

- `seconds/figures/aug7_ph2_tracking_and_inputs_seconds.png`
- `seconds/figures/aug7_acid_flow_4_second.png`
- `seconds/figures/aug7_sodium_acetate_flow_4_second.png`
- `seconds/figures/aug7_water_flow_4_second.png`

### Seconds tables

- `seconds/tables/tracking_and_flows_seconds.csv`, 14,426 rows
- `seconds/tables/mass_derived_flow_4_second.csv`, 12,288 rows
- `seconds/tables/tracking_metrics_seconds.csv`
- `seconds/tables/mass_flow_metrics_seconds.csv`

### One-minute figures

- `minutes/figures/aug7_ph2_tracking_and_inputs_one_minute.png`
- `minutes/figures/aug7_acid_flow_one_minute.png`
- `minutes/figures/aug7_sodium_acetate_flow_one_minute.png`
- `minutes/figures/aug7_water_flow_one_minute.png`

### One-minute tables

- `minutes/tables/tracking_and_flows_one_minute.csv`, 274 rows
- `minutes/tables/mass_derived_flow_one_minute.csv`, 819 rows
- `minutes/tables/tracking_metrics_one_minute.csv`
- `minutes/tables/mass_flow_metrics_one_minute.csv`

### Shared metadata

- `metadata/reconstructed_controller_actions.csv`
- `metadata/reconstructed_setpoint_blocks.csv`
- `biosmb_figure_manifest.json`

## Quantitative evidence

### Tracking including transients

| Resolution | Samples | Mean error [pH] | MAE [pH] | RMSE [pH] | Maximum absolute error [pH] |
|---|---:|---:|---:|---:|---:|
| Raw seconds | 14,426 | -0.0081 | 0.0238 | 0.0686 | 0.8658 |
| One-minute | 274 | -0.0075 | 0.0213 | 0.0638 | 0.8375 |

The maximum error is dominated by the initial transition from the startup pH,
not settled performance. These metrics intentionally retain the full transient.

### Four-second mass-derived flow

For intervals without command changes:

| Stream | Intervals | Mean actual | Mean command | Bias | MAE | RMSE | Correlation |
|---|---:|---:|---:|---:|---:|---:|---:|
| Acid | 3,860 | 4.261 | 4.291 | -0.031 | 1.084 | 1.409 | 0.817 |
| Sodium acetate | 3,860 | 6.357 | 6.087 | +0.270 | 1.465 | 2.971 | 0.744 |

The short-interval sodium calculation includes preserved scale spikes near 96
minutes. Its figure contains both the complete range and a central-range panel.

### One-minute mass-derived flow

Across all intervals:

| Stream | Intervals | Mean actual | Mean command | Bias | MAE | RMSE | Correlation |
|---|---:|---:|---:|---:|---:|---:|---:|
| Acid | 273 | 4.252 | 4.291 | -0.040 | 0.084 | 0.121 | 0.9985 |
| Sodium acetate | 273 | 6.357 | 6.087 | +0.270 | 0.273 | 0.326 | 0.9993 |

All flow values and errors are in mL/min. The one-minute results are much less
sensitive to scale update quantization and are the preferred calibration view.

## Figure audit

All eight figures were visually inspected against their source tables.

- Axes, units, stream labels, interval definitions, and generation times are
  present.
- Reconstructed targets are explicitly labeled as reconstructed.
- Raw pH and command trajectories are retained in the seconds figure.
- One-minute variability is shown rather than only the smoothed mean.
- Full-range sodium outliers are retained rather than clipped or deleted.
- Water plots explicitly state that the derivative is invalid for actual flow.
- Seconds and minutes artifacts have independent directories and tables.

## Verification

Commands:

```powershell
& '.venv\Scripts\python.exe' -m py_compile `
  'helpers/biosmb_experiment_data.py' `
  'helpers/biosmb_experiment_plotting.py' `
  'analysis/plot_biosmb_experiment.py' `
  'tests/test_biosmb_experiment_plotting.py'

& '.venv\Scripts\python.exe' -m unittest discover `
  -s tests -p 'test_biosmb_experiment_plotting.py' -v

& '.venv\Scripts\python.exe' `
  'analysis/plot_biosmb_experiment.py' `
  --utc-date 2026-08-07 `
  --output-dir 'results/aug7_biosmb_figures_20260807_210733'
```

Results:

- Python compilation passed.
- All five tests passed.
- The runner selected 14,426 samples and 236 controller actions.
- Four seconds figures and four minutes figures were generated.
- Every figure was visually inspected.
- The source CSV hash remained
  `750B74E526E941FE99412B6E2DC526B0B2A2CA5D61975B70AF969DF851651C44`.
- `git diff --check` passed for the implementation files.

## Limitations and next steps

- `target_ph` is reconstructed because it is not present in the CSV.
- FLOW registers are commands or readbacks, not independent flowmeter data.
- Four-second mass derivatives remain sensitive to scale update timing and are
  diagnostic rather than preferred pump-calibration measurements.
- Water actual flow is unavailable because its scale signal is invalid.
- The generic runner is ready for later datasets through CLI configuration.
  Future experiments should supply their UTC date, target values, step count,
  densities, and water validity rather than editing plotting code.
