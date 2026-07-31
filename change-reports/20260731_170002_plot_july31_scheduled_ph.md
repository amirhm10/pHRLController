# Plot July 31 scheduled pH experiment

## Objective

Reconstruct the unlogged scheduled pH setpoint for
`Data/July31 BioSMB RL Test.csv` and plot it against the reliable outlet
measurement, `biosmb-sensors.PH_2`, averaged over consecutive elapsed
60-second bins.

## Files changed

- `analysis/plot_july31_biosmb_schedule.py`
  - Adds a reusable command-line analysis for controller-event detection,
    scheduled-target reconstruction, one-minute `PH_2` aggregation, tracking
    metrics, tabular exports, and plotting.
- `change-reports/20260731_170002_plot_july31_scheduled_ph.md`
  - Records the method, generated artifacts, verification, and limitations.

The raw lab CSV was read without modification.

## Method and implementation summary

1. Detected controller action events when any logged BioSMB flow changed.
2. Selected the continuous experiment beginning at
   `2026-07-31T12:02:22.080Z`, immediately after the largest event gap
   (414.396 seconds). This excluded 243 startup/restart rows.
3. Reproduced the implemented ping-pong scheduler using:
   - five evenly spaced setpoints,
   - 20 maximum steps per setpoint,
   - five consecutive measurements within tolerance,
   - a 0.1 pH tolerance.
4. Inferred the unlogged target range as 3.9 to 5.5 pH, giving target levels
   3.9, 4.3, 4.7, 5.1, and 5.5. The values remain command-line overrides if
   the original minimum and maximum are later recovered.
5. Averaged `PH_2` in consecutive elapsed 60-second bins anchored at the
   reconstructed run start. The target was kept as a step signal instead of
   being averaged, because averaging a within-bin target change would create
   an artificial intermediate setpoint.

The reconstruction found 123 controller action events and 22 target changes.
All 22 changes satisfied the five-consecutive-in-tolerance condition before
the 20-step maximum. As supporting evidence, the median absolute change in
`log10(acetate_flow / acid_flow)` was 0.3993 at reconstructed target changes
and 0.0225 while the target was held.

## Generated artifacts

Generated under:

`results/july31_biosmb_schedule_20260731_205921/`

- `figures/july31_ph2_vs_reconstructed_setpoint_1min.png`
- `tables/ph2_one_minute_average.csv`
- `tables/reconstructed_controller_events.csv`
- `tables/reconstructed_schedule_segments.csv`
- `tables/tracking_metrics_1min.csv`
- `tables/tracking_metrics_by_target_1min.csv`
- `manifest.json`

The one-minute comparison contains 142 bins. Relative to the reconstructed
setpoint active at each bin center, its tracking MAE is 0.0574 pH, RMSE is
0.1022 pH, and 82.4% of minute averages are within 0.1 pH. These values include
transition bins.

## Verification

Commands:

```powershell
& '.venv\Scripts\python.exe' -m py_compile `
  'analysis/plot_july31_biosmb_schedule.py'

& '.venv\Scripts\python.exe' `
  'analysis/plot_july31_biosmb_schedule.py' `
  --output-dir 'results/july31_biosmb_schedule_20260731_205921'
```

Results:

- Python compilation passed.
- Analysis completed successfully.
- The output contains 123 action events, 22 reconstructed target switches,
  and 142 one-minute bins.
- The generated PNG was visually inspected for legibility, correct step
  ordering, one-minute `PH_2` presentation, and explicit reconstruction
  labeling.

## Known limitations and next steps

- The CSV does not contain `target_ph`. The 3.9 to 5.5 pH range is an inference
  from the observed plateaus, the five-level schedule, switching behavior, and
  action-flow changes; it is not a directly recorded value.
- The reconstruction assumes the controller tolerance was 0.1 pH.
- The startup/restart portion before the continuous run is excluded rather
  than forced into the schedule.
- One-minute averaging intentionally suppresses sub-minute sensor and mixing
  transients. The raw CSV remains available for dynamic identification.
- If the original scheduled minimum, maximum, or tolerance is recovered,
  rerun the script with `--target-min`, `--target-max`, or `--tolerance`.
