# pH Reward Absolute Bonus Update

## Objective

Update the offline pH TD3 shaped reward so the near-setpoint bonus is scaled in
physical pH reward units, remove the late-hold tail penalty from the default
reward, and increase the acid+acetate total-flow move penalty.

## Files Changed

- `simulation/ph_reward.py`
- `simulation/ph_environment.py`
- `run_offline_ph_td3_training.py`
- `helpers/offline_ph_td3_results.py`
- `tests/test_offline_ph_rl.py`
- `reports/offline_ph_td3_method_report.md`
- `reports/offline_ph_td3_training_result_analysis.md`
- `reports/figures/fig_reward_shape_comparison.png`

## Implementation Summary

- Added `bonus_weight_abs` to `PHRewardConfig` and changed the shaped reward
  bonus from `beta * q_band * band_floor_ph^2` to an absolute reward-unit
  bonus `bonus_weight_abs * f_bonus`.
- Set default `bonus_weight_abs = 0.05`, `bonus_k = 6.0`, legacy `beta = 0.0`,
  and `tail_offset_weight = 0.0`.
- Increased the default normalized total-flow move penalty weight from `0.1`
  to `1.0`.
- Updated runner CLI defaults and saved config/summary fields.
- Updated the reward-shape ablation plot so "no bonus" zeros
  `bonus_weight_abs`.
- Updated the method and result-analysis reports to describe the new active
  reward and the previous scaling issue.

## Generated Artifacts

- Regenerated `reports/figures/fig_reward_shape_comparison.png`.
- Ran a short end-to-end smoke run:
  `results/offline_ph_td3_training_20260708_232202`.

## Verification

- `py_compile` on touched Python files passed with `PYTHONPYCACHEPREFIX`
  redirected to a temp folder because the default Windows `__pycache__` write
  hit an access-denied error.
- `tests/test_offline_ph_rl.py` passed.
- Short runner smoke passed with:
  `--total-steps 20 --set-points-len 5 --batch-size 4 --buffer-size 64
  --std-decay-steps 5 --actor-hidden 16 --critic-hidden 16`.

## Known Limitations And Next Steps

- The linear inside/outside reward terms remain small on the current physical
  pH scale. The regenerated figure makes the bonus effect visible, but the
  linear contribution is still nearly zero compared with the absolute-error
  term.
- The next meaningful experiment is a full seeded training run with the new
  defaults, followed by the same reward-component share analysis and a
  setpoint-wise tracking plot review.
