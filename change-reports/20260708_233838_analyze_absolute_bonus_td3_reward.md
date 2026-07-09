# Analyze Absolute-Bonus pH TD3 Reward Run

## Objective

Analyze the latest full offline pH TD3 run with the absolute-unit reward bonus,
explain the late-operation drifts, and document the next recommended
experiment.

## Files Changed

- `reports/offline_ph_td3_training_result_analysis.md`
- `reports/figures/offline_ph_td3_training_20260708_233033_analysis/phase_metrics.csv`
- `reports/figures/offline_ph_td3_training_20260708_233033_analysis/reward_component_summary.csv`
- `reports/figures/offline_ph_td3_training_20260708_233033_analysis/cycle_drift_metrics.csv`

## Method Summary

- Inspected `results/offline_ph_td3_training_20260708_233033`.
- Confirmed the run used:
  - `reward_bonus_weight = 0.05`
  - `bonus_k = 6.0`
  - `tail_offset_weight = 0.0`
  - `sum_move_penalty_weight = 1.0`
- Compared the final evaluation offset against the previous full variable-sum
  run, `results/offline_ph_td3_training_20260708_230047`.
- Computed reward-component sums, phase metrics, final-evaluation tail error,
  late-cycle drift metrics, and edge-cycle action diagnostics.

## Main Findings

- The new reward helped remove steady final-evaluation offset.
  - Previous final evaluation tail MAE: `0.01910` pH.
  - New final evaluation tail MAE: `0.00193` pH.
- The reward bonus is now visible:
  - Previous bonus share was about `0.06%` of gross cost.
  - New bonus share is about `3.07%` of gross cost.
- Late training drifts are not process dynamics. The environment is static, so
  pH drift comes from action changes.
- The last training holds still include residual exploration at `std = 0.01`
  and ongoing TD3 updates. The final evaluation hold has no exploration and no
  training updates, and it becomes nearly flat.
- The worst late-cycle failures occur near the reachable pH edges, where the
  ratio action can saturate but the selected acid+acetate total flow can make
  the target ratio infeasible under individual pump bounds.

## Generated Artifacts

- `reports/figures/offline_ph_td3_training_20260708_233033_analysis/phase_metrics.csv`
- `reports/figures/offline_ph_td3_training_20260708_233033_analysis/reward_component_summary.csv`
- `reports/figures/offline_ph_td3_training_20260708_233033_analysis/cycle_drift_metrics.csv`

## Verification

- Recomputed metrics directly from:
  - `results/offline_ph_td3_training_20260708_233033/tables/trajectory.csv`
  - `results/offline_ph_td3_training_20260708_233033/tables/training_summary.csv`
  - `results/offline_ph_td3_training_20260708_230047/tables/trajectory.csv`
- No Python source code was changed in this task.

## Next Step

Add a deterministic frozen-policy evaluation sweep after training. It should
evaluate a fixed actor without exploration or training updates over a grid from
`3.76` to `5.76` pH, then save per-target tail MAE, final error, pump
saturation flags, and final acid/acetate/sum actions.
