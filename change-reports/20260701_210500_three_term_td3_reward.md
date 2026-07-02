# Add Three-Term Offline pH TD3 Reward

## Objective

Replace the single squared-error TD3 runner reward with a three-term objective:

```text
reward = -(q2 * (target_pH - pH)^2
           + q1 * abs(target_pH - pH)
           + r_move * mean((action_t - action_t_minus_1)^2))
```

The move term is an MPC-style move penalty on the normalized two-action vector for acid and acetate flow commands.

## Files Changed

- `simulation/ph_environment.py`
- `run_offline_ph_td3_training.py`
- `helpers/offline_ph_td3_results.py`
- `analysis/generate_offline_ph_td3_report.py`
- `tests/test_offline_ph_rl.py`
- `reports/offline_ph_rl_environment_report.md`
- `reports/offline_ph_td3_training_result_analysis.md`
- `reports/figures/offline_ph_td3_training_20260701_210401_analysis/`
- `change-reports/20260701_210500_three_term_td3_reward.md`

The unrelated worktree deletion `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv` was not touched or staged.

## Implementation Summary

- Added `absolute_error_weight` to `PHEnvironmentConfig`.
- Changed the default environment reward to use squared error, absolute error, and action move cost.
- Kept `default_flow_penalty_weight` available but set its default to `0.0` so the normal reward has the requested three terms.
- Updated `PHEnvironment.step()` to log:
  - `reward_setpoint_error`
  - `reward_squared_error_cost`
  - `reward_absolute_error_cost`
  - `reward_move_cost`
  - `reward_total_cost`
- Updated `run_offline_ph_td3_training.py` to train on the environment reward instead of recomputing only squared pH error.
- Added runner CLI weights:
  - `--reward-squared-weight`, default `1.0`
  - `--reward-absolute-weight`, default `1.0`
  - `--move-penalty-weight`, default `0.01`
- Updated saved summaries and config snapshots with reward weights and component-cost totals.
- Updated result plotting so the main tracking/reward figure includes a fourth panel for raw reward cost components.
- Updated report generation and Markdown reports for the new reward formula.

## Generated Artifacts

Smoke-run result folder:

```text
results/offline_ph_td3_training_20260701_210401/
```

Report artifacts:

```text
reports/figures/offline_ph_td3_training_20260701_210401_analysis/
```

The saved trajectory now includes reward component columns in addition to the scalar reward.

## Verification

Compiled the touched Python files:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" -m py_compile simulation\ph_environment.py run_offline_ph_td3_training.py helpers\offline_ph_td3_results.py analysis\generate_offline_ph_td3_report.py tests\test_offline_ph_rl.py
```

Passed direct smoke tests:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" tests\test_offline_ph_rl.py
```

Output:

```text
offline pH RL smoke tests passed
```

Ran the offline TD3 smoke runner:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" run_offline_ph_td3_training.py --total-steps 18 --n-tests 3 --batch-size 4 --buffer-size 128 --actor-hidden 16 --critic-hidden 16 --seed 37
```

Summary:

```text
total_steps:                 18
warm_start_steps:            0
td3_train_steps:             9
batch_size:                  4
overall_MAE:                 0.4771 pH
overall_RMSE:                0.6144 pH
eval_MAE:                    0.000031 pH
eval_RMSE:                   0.000033 pH
overall_squared_error_cost:  6.7954
overall_absolute_error_cost: 8.5869
overall_move_cost:           1.9773
```

Regenerated the report:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" analysis\generate_offline_ph_td3_report.py --result-dir results\offline_ph_td3_training_20260701_210401
```

## Known Limitations And Next Steps

- The move penalty is currently computed on normalized actions, not physical mL/min flow changes.
- The default move penalty weight is deliberately small at `0.01`.
- The short TD3 run is a software smoke test only, not controller validation.
- The next meaningful experiment is the default 25,000-step run with reward-weight sweeps for `q2`, `q1`, and `r_move`.
