# Correct July 31 water mapping and combine tracking with inputs

## Objective

Audit the July 31 water-flow channel after the user questioned the zero-flow
result, correct the historical stream mapping, and add one synchronized figure
containing pH tracking and all three manipulated inputs.

## Files inspected

- `Data/July31 BioSMB RL Test.csv`
- `analysis/plot_july31_biosmb_schedule.py`
- `run_biosmb_ph_readonly_smoke_test.py`
- `Biosmb-run-online/Biosmb-run-online/main.py`
- `reports/open_loop_ph_step_test_identification_plan.md`
- `change-reports/20260528_015517_update_live_ph_mapping.md`
- `change-reports/20260804_234138_plot_july31_input_flows.md`
- `results/july31_biosmb_schedule_20260731_205921/`

## Mapping diagnosis

The previous plot incorrectly used the compact project mapping
`biosmb-flows[2] = water`. That mapping does not describe the July 31 hardware
run.

The run-specific evidence is:

- The live pH plumbing documentation maps Arium water to pump 4.
- BioSMB exports pump 4 as the zero-based column `biosmb-flows[3]`.
- In the selected continuous run, `biosmb-flows[3]` is exactly 5.00 mL/min.
- In the same run, `biosmb-flows[2]` is exactly 0.00 mL/min.
- The configured fixed water command is 5.0 mL/min.
- Acid bottle mass decreased by 614.88 g while integrated
  `biosmb-flows[0]` was 624.50 mL.
- Sodium solution mass decreased by 552.23 g while integrated
  `biosmb-flows[1]` was 565.10 mL.

The acid and sodium mass balances support the `[0]` and `[1]` mappings. The
water mass channel increased by 71.82 g over the selected run, so it is
anomalous and was not used as independent proof of the water consumption.

## Mathematical representation

For each logged pump input \(u_j\), the plot uses a zero-order hold between
controller events:

\[
u_j(t) = u_{j,k}, \qquad t_k \leq t < t_{k+1}.
\]

The tracking panel compares the one-minute reliable outlet measurement with
the reconstructed scheduled target:

\[
e_k = \overline{\mathrm{PH2}}_k - r_k.
\]

The existing one-minute tracking metrics are unchanged because correcting the
water display does not alter `PH_2` or the reconstructed schedule. The MAE
remains 0.0574 pH.

## Files changed

- `analysis/plot_july31_biosmb_schedule.py`
  - Changes the July 31 water mapping from `biosmb-flows[2]` to
    `biosmb-flows[3]`.
  - Documents why this historical mapping differs from compact project data.
  - Corrects the input-only figure.
  - Adds a four-panel pH tracking and input-flow figure.
  - Records the corrected mapping and both figure paths in future manifests.
- `change-reports/20260804_234138_plot_july31_input_flows.md`
  - Adds a prominent correction to the earlier inaccurate water claim.
- `change-reports/20260804_234831_correct_july31_water_and_combine_plots.md`
  - Records the diagnosis, correction, figures, and verification.

The raw CSV was read without modification.

## Generated artifacts

Generated under:

`results/july31_biosmb_schedule_20260731_205921/figures/`

- `july31_water_acid_base_flows.png`
  - Corrected input-only figure with water fixed at 5.00 mL/min.
- `july31_ph2_tracking_and_input_flows.png`
  - New synchronized figure with pH tracking, water, acid, and sodium acetate.

The incorrect input-only PNG was replaced. The existing pH-only figure, tables,
and raw data were not overwritten.

## Quantitative evidence

Across the selected 141.81-minute run and 123 controller action events:

- Arium water, pump 4 and `biosmb-flows[3]`: 5.00 to 5.00 mL/min.
- Acetic acid, `biosmb-flows[0]`: 1.04 to 9.48 mL/min.
- Sodium acetate, `biosmb-flows[1]`: 1.00 to 9.04 mL/min.
- Reconstructed target switches: 22.
- One-minute tracking MAE: 0.0574 pH.

## Verification

Commands:

```powershell
& '.venv\Scripts\python.exe' -m py_compile `
  'analysis/plot_july31_biosmb_schedule.py'

& '.venv\Scripts\python.exe' `
  'analysis/plot_july31_biosmb_schedule.py' `
  --output-dir `
  (Join-Path ([System.IO.Path]::GetTempPath()) `
    'codex_july31_combined_plot_verify')
```

Results:

- Python compilation passed.
- The complete analysis ran successfully.
- Both corrected figures were visually inspected.
- The water subplot is fixed at 5.00 mL/min.
- Tracking and all three input plots share the same elapsed-time axis.
- Existing tracking metrics remained unchanged.
- `git diff --check` passed apart from the Windows line-ending notice.

## Known limitations and next step

- The water mass channel increases during the run and should not be treated as
  a valid water-consumption balance without checking scale handling, refilling,
  or channel semantics.
- The flow channels may be command readbacks rather than independently measured
  delivered flows.
- Future historical analyses should store an explicit run-specific pump map in
  their manifest rather than automatically applying the compact dataset map.
