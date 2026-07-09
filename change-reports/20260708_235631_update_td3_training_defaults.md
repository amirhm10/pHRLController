# Update Offline pH TD3 Training Defaults

## Objective

Update the next offline pH TD3 run configuration based on the latest reward
analysis and plotting feedback.

## Files Changed

- `run_offline_ph_td3_training.py`
- `simulation/ph_environment.py`
- `helpers/offline_ph_td3_results.py`
- `tests/test_offline_ph_rl.py`
- `reports/offline_ph_td3_method_report.md`
- `reports/offline_ph_td3_training_result_analysis.md`

## Implementation Summary

- Increased the default rollout length from `100000` to `200000` steps.
- Increased the default TD3 batch size from `64` to `128`.
- Increased the normalized acid+acetate total-flow move penalty from `1.0` to
  `5.0`.
- Added a lab-data setpoint-range resolver:
  - default CSV: `Data/dsp_db.biosmb-rl-controller-treated-dataset-weights.csv`
  - default column: `target_ph`
  - desired range from data: `3.7` to `5.7` pH
  - resolved default training range after simulator-bound intersection:
    `3.76` to `5.7` pH
- Updated config snapshots and training summaries to save desired, reachable,
  and resolved setpoint ranges.
- Changed TD3 training-loss plotting:
  - critic loss uses a log axis when positive,
  - actor loss uses signed-log scaling,
  - NaN loss entries are dropped separately so delayed actor-update losses
    render correctly.

## Generated Artifacts

- Regenerated latest result training-loss plot:
  `results/offline_ph_td3_training_20260708_233033/figures/fig_training_losses.png`
- Ran a short end-to-end smoke run:
  `results/offline_ph_td3_training_20260708_235452`

## Verification

- `py_compile` passed with `PYTHONPYCACHEPREFIX` redirected to a temp folder.
- `tests/test_offline_ph_rl.py` passed.
- Short runner smoke passed with:
  `--total-steps 20 --set-points-len 5 --batch-size 4 --buffer-size 64
  --std-decay-steps 5 --actor-hidden 16 --critic-hidden 16`.

## Known Limitations And Next Steps

- The new defaults have not yet been tested in a full `200000`-step run.
- The lab-data desired lower setpoint `3.7` is below the current simulator
  lower bound `3.76`, so the runner clips the actual training lower bound to
  `3.76` and records that clipping in the snapshot.
- The next full run should be analyzed for edge-setpoint feasibility,
  total-flow smoothness, final deterministic offset, and the updated
  log-scaled actor/critic loss trends.
