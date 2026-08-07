# Review Aug. 7 Experiment Data

## Objective

Review the cumulative `Data/Aug7 BioSMB RL Test.csv` export, isolate the
Aug. 7 UTC experiment without modifying the raw CSV, verify timestamp and
measurement integrity, and test whether the supplied 30-step scheduler
configuration produced one-hour setpoint holds.

## Files inspected

- `Data/Aug7 BioSMB RL Test.csv`
- `analysis/plot_july31_biosmb_schedule.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/runtime_modes.py`
- `Biosmb-run-online/Biosmb-run-online/main.py`
- Previous July 31 data-audit and mass-derived-flow change reports

## Files changed

- `analysis/audit_aug7_lab_data.py`
  - Adds a reusable UTC-date filter and data-integrity audit.
  - Preserves the raw cumulative CSV and verifies its SHA-256 before and
    after the audit.
  - Exports a date-only derivative with fixed-format ISO-8601 UTC timestamps.
  - Detects controller actions from logged FLOW-register changes.
  - Groups detected actions into supplied 30-step setpoint blocks.
  - Calculates PH_2 block summaries, command integrals, and gravimetric mass
    balances using a provisional density of 1 g/mL.
  - Generates a synchronized pH, command, and reservoir-mass audit figure.
- `change-reports/20260807_162113_review_aug7_experiment_data.md`
  - Records the method, evidence, limitations, and verification.

The existing uncommitted edit in
`Biosmb-run-online/Biosmb-run-online/main.py` is unrelated and was not changed
as part of this task.

## UTC-date audit

The cumulative raw export contains 38,030 rows covering 13 UTC dates from
April 16 through Aug. 7, 2026. It is not an Aug. 7-only file.

The selected Aug. 7 experiment contains:

- 14,426 rows
- 23,604 excluded rows from other UTC dates
- start time `2026-08-07T09:58:21.743Z`
- end time `2026-08-07T14:31:27.699Z`
- duration 4.5517 h
- zero duplicate timestamps
- zero gaps longer than 5 s
- median sample interval 1.143 s
- maximum sample interval 3.154 s
- 14,426 rows marked as valid observations

The cumulative raw export has one backward timestamp transition and one
duplicate timestamp. Neither occurs in the selected Aug. 7 derivative, which
is sorted monotonically by UTC time.

## Scheduler interpretation

The audit detects 236 controller actions after the initial 2 mL/min startup
condition. The controller interval is:

- mean 69.292 s
- median 69.273 s

Grouping consecutive actions into 30-step blocks gives:

- seven complete 30-step blocks
- one final partial block containing 26 actions
- mean complete-block duration 34.656 min
- complete-block range 34.506 to 34.739 min

The two scheduler conditions are combined with OR in
`ScheduledSetpointManager.observe()`. Therefore
`max_steps_per_setpoint = 30` and `consecutive_steps_required = 30` do not add
to 60 steps. The maximum-step condition advances the target after 30 completed
steps. At the observed 69.292 s controller interval, approximately 52 steps,
not 30, would be needed for a one-hour block. A wall-clock hold would be more
precise than a step count because loop overhead makes the observed interval
longer than the nominal 60 s decision interval.

## PH_2 evidence

The final five-minute PH_2 means for blocks 0 through 7 are:

| Block | Actions | Complete | Duration [min] | Final 5-min PH_2 mean | Final 5-min PH_2 std |
|---:|---:|:---:|---:|---:|---:|
| 0 | 30 | yes | 34.506 | 3.8763 | 0.0139 |
| 1 | 30 | yes | 34.666 | 4.2923 | 0.0112 |
| 2 | 30 | yes | 34.739 | 4.6983 | 0.0131 |
| 3 | 30 | yes | 34.669 | 5.0958 | 0.0153 |
| 4 | 30 | yes | 34.707 | 5.4835 | 0.0148 |
| 5 | 30 | yes | 34.621 | 5.0986 | 0.0153 |
| 6 | 30 | yes | 34.685 | 4.6954 | 0.0121 |
| 7 | 26 | no | 29.356 | 4.2894 | 0.0137 |

This is strong evidence of a clean increasing then decreasing setpoint
sequence. If the intended targets were the previous 3.9, 4.3, 4.7, 5.1, and
5.5 pH ping-pong schedule, the inferred final-five-minute tracking MAE is
0.0088 pH and the maximum absolute error is 0.0237 pH. This remains an
inference because the CSV does not log `target_ph` or the active scheduler
configuration.

## Mass-balance evidence

Using 1 g/mL and the full selected experiment:

| Stream | Mass-derived volume [mL] | Integrated command [mL] | Difference |
|---|---:|---:|---:|
| Acetic acid | 1161.09 | 1171.86 | -0.92% |
| Sodium acetate | 1735.86 | 1662.20 | +4.43% |
| Arium water | -6.23 diagnostic | 1362.04 | invalid |

The acid and sodium mass balances are physically consistent and quantify
run-wide pump or measurement mismatch. The water mass increases from 2518.67
g to 2524.90 g during positive pump operation, so it remains invalid for
actual-flow estimation.

## Generated artifacts

Under `results/aug7_data_audit_20260807_201845/`:

- `tables/biosmb_20260807_utc_only.csv`
- `tables/utc_date_counts.csv`
- `tables/controller_action_events.csv`
- `tables/thirty_step_setpoint_blocks.csv`
- `tables/stream_mass_balance.csv`
- `tables/data_audit_summary.csv`
- `figures/aug7_utc_only_data_audit.png`
- `aug7_data_audit_manifest.json`

The raw CSV SHA-256 before and after the audit is:

`A8C609A285F99C40BE511171187F8ED27A04704F9610553B99B5FC5060B3802D`

## Verification

Commands:

```powershell
& '.venv\Scripts\python.exe' -m py_compile `
  'analysis/audit_aug7_lab_data.py'

& '.venv\Scripts\python.exe' `
  'analysis/audit_aug7_lab_data.py' `
  --output-dir 'results/aug7_data_audit_20260807_201845'
```

Verification results:

- Python compilation passed.
- The raw file remained unchanged.
- The UTC-only derivative contains exactly 14,426 rows.
- Every derivative timestamp parses successfully and belongs to Aug. 7 UTC.
- Derivative timestamps are monotonic and contain no duplicates.
- The audit figure was inspected and matches the pH, flow-command, mass, and
  block-boundary tables.
- `git diff --check` passed for the new analysis script.

## Limitations and next steps

- Target values and scheduler settings are not logged in the CSV. The target
  sequence is therefore inferred from the supplied settings and observed pH
  plateaus.
- FLOW registers may be commands or readbacks, not independent flowmeter
  measurements.
- The acid and sodium gravimetric results are reservoir-out averages and do
  not include transport delay to the mixer.
- The water scale remains unusable for actual-flow calculation.
- For future experiments, log `target_ph`, scheduler counters, target-change
  events, raw action, clipped action, and final commanded flows directly.
- If a one-hour hold is required, use an elapsed-time condition or revise the
  step count based on the observed controller interval and verify it before
  the next lab run.
