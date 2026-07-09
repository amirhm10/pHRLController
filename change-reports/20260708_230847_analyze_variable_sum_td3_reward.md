# Analyze Variable-Sum Offline pH TD3 Reward

## Objective

Analyze the latest variable-sum offline pH TD3 run and address two plotting
issues: the setpoint-average reward plot should show trend with connected
points, and the reward-shape comparison should make the small bonus/linear
effects visible.

## Files Changed

- `helpers/offline_ph_td3_results.py`
- `reports/offline_ph_td3_training_result_analysis.md`
- `reports/figures/fig_reward_shape_comparison.png`

## Method And Findings

- Analyzed `results/offline_ph_td3_training_20260708_230047`.
- The 100000-step run has overall MAE `0.03978` pH and final evaluation MAE
  `0.01953` pH.
- Reward component totals show that absolute error and late-hold offset terms
  dominate the signal:
  - absolute-error cost share: `55.11%`
  - late-hold tail offset cost share: `33.71%`
  - squared-error cost share: `10.60%`
  - normalized total-flow move penalty share: `0.19%`
  - bonus contribution: `0.06%` negative-cost share
- The shaped reward curves look almost identical because the bonus is scaled by
  `band_floor_ph**2 = 0.0001`; with `beta = 25`, its maximum reward effect is
  only about `0.002`.

## Implementation Summary

- Changed `fig_setpoint_average_reward.png` from a bar chart to connected
  scatter points.
- Changed the reward-shape comparison to a two-panel plot:
  - top: full reward and ablations,
  - bottom: reward deltas from bonus and linear terms.
- Added a latest-run analysis section to
  `reports/offline_ph_td3_training_result_analysis.md`.
- Regenerated the latest result figures from saved CSV files without rerunning
  training.

## Generated Artifacts

- Updated:
  `results/offline_ph_td3_training_20260708_230047/figures/fig_setpoint_average_reward.png`
- Updated:
  `results/offline_ph_td3_training_20260708_230047/figures/fig_reward_shape_comparison.png`
- Updated:
  `reports/figures/fig_reward_shape_comparison.png`

## Verification

- Compile:
  `C:\Users\HAMEDI\miniconda3\envs\rl\python.exe -m py_compile helpers/offline_ph_td3_results.py tests/test_offline_ph_rl.py`
  - Result: passed.
- Direct smoke tests:
  `C:\Users\HAMEDI\miniconda3\envs\rl\python.exe tests/test_offline_ph_rl.py`
  - Result: passed, printed `offline pH RL smoke tests passed`.

## Known Limitations And Next Steps

- No reward defaults were changed in this task. The analysis recommends a next
  reward experiment with an absolute-unit near-zero bonus, lower tail offset
  weight, and stronger total-flow move penalty.
- The latest run still uses an ideal static Henderson-Hasselbalch plant only.
