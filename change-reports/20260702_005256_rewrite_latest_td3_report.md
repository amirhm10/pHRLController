# Rewrite Latest TD3 Report

Date: 2026-07-02

## Objective

Rewrite the offline pH TD3 result report around the latest requested 50,000-step experiment:

```text
results/offline_ph_td3_training_20260702_003841/
```

The rewrite focuses on scientific interpretation and concrete next steps.

## Files Changed

- `reports/offline_ph_td3_training_result_analysis.md`

The unrelated dirty deletion `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv` was not modified or staged.

## Method Summary

- Re-read the latest requested 50,000-step result tables.
- Checked the newer on-disk folder `results/offline_ph_td3_training_20260702_004325/` and noted that it is a default 25,000-step run, not the requested 50,000-step experiment.
- Compared the 50,000-step run against the previous 25,000-step/200-step-hold run.
- Diagnosed the final evaluation offset using the target pH, final pH, ideal target action, and actor output action.

## Main Interpretation Added

- The 50,000-step run improves overall MAE and late-training MAE.
- The final deterministic evaluation cycle is worse than the previous run.
- The final evaluation offset comes from actor ratio-action bias:
  - final target pH: `4.97763`
  - final pH: `5.02067`
  - ideal target action: `0.72294`
  - final actor action: `0.86592`
  - final action bias: `0.14298`
- The ideal HH model residual is numerical zero, so this is a policy-selection issue rather than a chemistry-model issue.

## Next Step Recommended

Add a frozen-policy deterministic evaluation sweep to `run_offline_ph_td3_training.py`:

- freeze the actor after training,
- disable exploration and replay updates,
- evaluate a setpoint grid across `4.459-5.061` pH,
- hold each setpoint for 400 steps,
- save `tables/evaluation_sweep.csv`,
- save a figure of target pH, final pH, MAE, and action bias versus setpoint.

## Verification

This was a Markdown/report rewrite. Verification was by direct inspection of:

- `results/offline_ph_td3_training_20260702_003841/tables/training_summary.csv`
- `results/offline_ph_td3_training_20260702_003841/tables/trajectory.csv`
- `results/offline_ph_td3_training_20260702_003841/tables/flow_constraint_check.csv`
- `results/offline_ph_td3_training_20260701_221816/tables/training_summary.csv`
- `results/offline_ph_td3_training_20260702_004325/tables/training_summary.csv`

No code was changed.
