# Extend offline pH TD3 meeting report

## Objective

Update the offline pH TD3 reports with the latest full 200000-step run so the
results can be presented in a meeting.

## Files changed

- `reports/offline_ph_td3_training_result_analysis.md`
- `reports/offline_ph_td3_method_report.md`
- `change-reports/20260709_002041_extend_td3_meeting_report.md`

## Method summary

- Treated `results/offline_ph_td3_training_20260709_001341` as the latest full
  run after checking its config snapshot and summary tables.
- Added a meeting-summary section to the result-analysis report.
- Added a shorter latest-run section to the method report.
- Reported the current default protocol: 200000 steps, batch size 128,
  buffer size 60000, lab-data setpoint range, `sum_move_penalty_weight = 5.0`,
  and absolute reward-unit bonus weight 0.05.
- Summarized all-step, post-decay, last-100-cycle, and final-evaluation
  tracking metrics.
- Summarized reward-component magnitudes and the remaining low-pH edge issue.
- Linked the existing saved figures for average reward, last-five tracking,
  reward shape, and TD3 losses.

## Generated or used artifacts

No new result figures were generated. The report links existing artifacts from:

- `results/offline_ph_td3_training_20260709_001341/figures/fig_setpoint_average_reward.png`
- `results/offline_ph_td3_training_20260709_001341/figures/fig_last_5_setpoint_tracking.png`
- `results/offline_ph_td3_training_20260709_001341/figures/fig_reward_shape_comparison.png`
- `results/offline_ph_td3_training_20260709_001341/figures/fig_training_losses.png`

## Verification

- Read `config_snapshot.json`, `training_summary.csv`, `summary_metrics.csv`,
  `flow_diagnostics.csv`, and `hh_consistency.csv`.
- Recomputed phase, reward-component, drift, and edge-target diagnostics from
  `trajectory.csv`.
- Visually inspected the key saved figures.
- Checked that referenced figure files exist.
- `git diff --check` passed.

## Known limitations and next steps

- The latest final evaluation is still only one held setpoint, so it should not
  be used as a robust generalization claim.
- The next experiment should save an actor checkpoint and run a deterministic
  frozen-policy setpoint sweep from 3.76 to 5.7 pH.
