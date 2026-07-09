# Variable-Sum Offline pH TD3 Reward/State Update

## Objective

Implement the offline pH TD3 update requested on 2026-07-08: remove `t/T`
from the steady-state tracking state, make the default action choose both
acetate/acid ratio and total acid+acetate flow, keep `PERRecentReplayBuffer`,
tighten the shaped reward band to `0.01`, add a normalized total-flow move
penalty, update plotting functions, and update the method report.

## Files Changed

- `simulation/ph_environment.py`
- `simulation/ph_reward.py`
- `run_offline_ph_td3_training.py`
- `helpers/offline_ph_td3_results.py`
- `tests/test_offline_ph_rl.py`
- `reports/offline_ph_td3_method_report.md`
- `reports/figures/fig_reward_shape_comparison.png`

## Implementation Summary

- Added default `action_mode="ratio_buffer_sum"` with action vector
  `[normalized_ratio, normalized_buffer_sum]`.
- Kept `--action-mode ratio` as the legacy one-action fixed-sum ablation.
- Removed `t/T` from observations. Default state is now
  `[pH, target_pH, pH-target_pH, ratio_action, buffer_sum_action]`.
- Mapped total acid+acetate flow over `[2, 20]` mL/min while preserving
  individual acid and acetate pump bounds `[1, 10]` mL/min.
- Added reward fields for normalized total-flow movement:
  `reward_sum_move_cost` and `reward_sum_move_penalty_term`.
- Set runner defaults to `buffer_size=60000`, `std_end=0.01`,
  `reward_band_floor_ph=0.01`, `move_penalty_weight=0.0`, and
  `sum_move_penalty_weight=0.1`.
- Updated plots to show variable buffer-flow sum, two action coordinates,
  reward-band-aware pH error lines, and the reward-shape comparison.
- Updated the method report with the new state, action, reward, defaults,
  PERRecent replay note, and reward-shape figure.

## Generated Artifacts

- `reports/figures/fig_reward_shape_comparison.png`
- Smoke output folder: `results/_smoke_variable_sum_td3/`
- Test artifact folder from direct smoke tests:
  `results/_test_offline_ph_td3_artifacts/`

## Verification

- Compile:
  `C:\Users\HAMEDI\miniconda3\envs\rl\python.exe -m py_compile simulation/ph_reward.py simulation/ph_environment.py run_offline_ph_td3_training.py helpers/offline_ph_td3_results.py tests/test_offline_ph_rl.py`
  - Result: passed.
- Direct smoke tests:
  `C:\Users\HAMEDI\miniconda3\envs\rl\python.exe tests/test_offline_ph_rl.py`
  - Result: passed, printed `offline pH RL smoke tests passed`.
- Tiny default runner smoke:
  `C:\Users\HAMEDI\miniconda3\envs\rl\python.exe run_offline_ph_td3_training.py --total-steps 20 --set-points-len 5 --batch-size 4 --buffer-size 64 --std-decay-steps 5 --output-dir results/_smoke_variable_sum_td3`
  - Result: passed and saved figures including `fig_reward_shape_comparison.png`.
- Pytest:
  `C:\Users\HAMEDI\miniconda3\envs\rl\python.exe -m pytest tests/test_offline_ph_rl.py`
  - Result: blocked because `pytest` is not installed in the `rl` environment.

## Known Limitations And Next Steps

- This remains an offline ideal Henderson-Hasselbalch simulation only.
- No BioSMB hardware, live controller, MPC deployment, or lab-data validation
  path was changed.
- The variable-sum action expands the ideal reachable target range, but it is
  still static and does not model delay, residence time, mixing, or pH sensor
  dynamics.
- A full 100000-step run should be executed next and interpreted using the new
  per-setpoint reward, last-five-setpoint tracking, and reward-component plots.
