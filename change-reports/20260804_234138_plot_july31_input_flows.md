# Plot July 31 manipulated input flows

## Objective

Add one figure to the existing July 31 BioSMB schedule analysis showing the
logged Arium water, acetic acid, and sodium acetate flow inputs as three
synchronized subplots.

## Files changed

- `analysis/plot_july31_biosmb_schedule.py`
  - Adds the manipulated-input channel mapping.
  - Adds a reusable three-subplot step-plot function.
  - Generates and records the new input-flow figure in future complete runs.
- `change-reports/20260804_234138_plot_july31_input_flows.md`
  - Records the implementation, generated artifact, verification, and
    limitations.

The raw lab CSV and existing generated result files were not modified.

## Method and implementation summary

The stream mapping follows the project convention:

- `biosmb-flows[2]` is Arium water.
- `biosmb-flows[0]` is 100 mM acetic acid.
- `biosmb-flows[1]` is 100 mM sodium acetate, labeled as base.

The figure uses controller action-event values from
`reconstructed_controller_events.csv`. For each input \(u_j\), the plotted
signal is piecewise constant:

\[
u_j(t) = u_{j,k}, \qquad t_k \leq t < t_{k+1}.
\]

This representation matches the held pump command between detected controller
events and avoids visually interpolating commands that changed as steps.
All three subplots share the same elapsed-time axis and 0 to 10 mL/min scale.

## Generated artifact

Generated under the user-specified existing result folder:

`results/july31_biosmb_schedule_20260731_205921/figures/`

- `july31_water_acid_base_flows.png`

The new PNG was added without regenerating or overwriting the existing pH
figure, tables, or manifest. The `results/` directory remains ignored by Git.

## Figure evidence

Across the 123 detected controller action events:

- Arium water remained at 0.00 mL/min for the full selected run.
- Acetic acid ranged from 1.04 to 9.48 mL/min.
- Sodium acetate ranged from 1.00 to 9.04 mL/min.

The flat water trace is a data result, not a plotting omission.

## Verification

Commands:

```powershell
& '.venv\Scripts\python.exe' -m py_compile `
  'analysis/plot_july31_biosmb_schedule.py'

& '.venv\Scripts\python.exe' `
  'analysis/plot_july31_biosmb_schedule.py' `
  --output-dir `
  (Join-Path ([System.IO.Path]::GetTempPath()) `
    'codex_july31_input_plot_verify')
```

Results:

- Python compilation passed.
- The complete analysis ran successfully.
- It retained 123 action events, 22 reconstructed target switches, and a
  one-minute tracking MAE of 0.0574 pH.
- The new PNG is 2704 by 1684 pixels in RGBA mode.
- The generated and copied figure was visually inspected for stream mapping,
  step timing, common axis scaling, labels, and readability.
- `git diff --check` passed apart from the existing Windows line-ending
  notice.

## Known limitations and next steps

- Water was logged at zero throughout this selected run, so its subplot is
  intentionally flat.
- The plot shows commanded or logged held flow inputs at action events. It
  does not establish the delivered physical flow or pump calibration.
- Sub-minute pump and mixing dynamics require separate measured flow data if
  they are to be identified.
