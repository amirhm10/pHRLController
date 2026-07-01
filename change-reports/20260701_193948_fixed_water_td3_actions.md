# Fixed Water Flow For Offline pH TD3 Actions

## Objective

Set Arium water flow to a fixed 5 mL/min in the offline pH TD3 scaffold and let TD3 control only acetic acid and sodium acetate flowrates. Clarify that `TD` in `TD3` means Twin Delayed and is not an action variable.

## Files Changed

- `simulation/ph_environment.py`
- `run_offline_ph_td3_training.py`
- `helpers/offline_ph_td3_results.py`
- `analysis/generate_offline_ph_td3_report.py`
- `tests/test_offline_ph_rl.py`
- `reports/offline_ph_rl_environment_report.md`
- `reports/offline_ph_td3_training_result_analysis.md`
- `reports/figures/offline_ph_td3_training_20260701_193823_analysis/`
- `change-reports/20260701_193948_fixed_water_td3_actions.md`

The unrelated worktree deletion `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv` was not touched or staged.

## Implementation Summary

- Changed `PHEnvironment.action_space` from `Box(-1, 1, shape=(3,))` to `Box(-1, 1, shape=(2,))`.
- Changed the observation vector from seven entries to six entries:
  `[current_pH, target_pH, pH_error, acid_action, acetate_action, step_fraction]`.
- Added `fixed_water_flow`, clipped from `PHProcessConfig.default_water_flow`, and used it for all environment flow outputs.
- Kept physical logging of `water_flow` in `info` and saved trajectories, with value fixed at 5 mL/min.
- Updated TD3 agent construction to `state_dim=6` and `action_dim=2`.
- Removed `action_water` from newly saved runner trajectories.
- Updated plotting/report helpers to work with new two-action trajectories while still tolerating older CSV files that contain `action_water`.
- Regenerated the analysis report from a new fixed-water smoke run.

## Generated Artifacts

Smoke-run result folder:

```text
results/offline_ph_td3_training_20260701_193823/
```

Report artifacts:

```text
reports/figures/offline_ph_td3_training_20260701_193823_analysis/
```

The saved smoke trajectory has only `action_acid` and `action_acetate` action columns. The logged `water_flow` column is constant at 5.0 mL/min.

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
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" run_offline_ph_td3_training.py --total-steps 18 --n-tests 3 --batch-size 4 --buffer-size 128 --actor-hidden 16 --critic-hidden 16 --seed 31
```

Summary:

```text
total_steps:      18
warm_start_steps: 0
td3_train_steps:  9
batch_size:       4
overall_MAE:      0.4560 pH
overall_RMSE:     0.6686 pH
eval_MAE:         0.0017 pH
eval_RMSE:        0.0018 pH
```

Regenerated the report:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" analysis\generate_offline_ph_td3_report.py --result-dir results\offline_ph_td3_training_20260701_193823
```

## Known Limitations And Next Steps

- This remains an offline static ideal Henderson-Hasselbalch simulation.
- No BioSMB, OPC emulator, hardware runner, MPC, pump runner, or live controller logic was added.
- Water is fixed and logged, but it still does not directly affect ideal HH pH with equal acid and acetate stock concentrations.
- The short TD3 run is a software smoke test only. The next meaningful run is the default 25,000-step offline training run with fixed water.
