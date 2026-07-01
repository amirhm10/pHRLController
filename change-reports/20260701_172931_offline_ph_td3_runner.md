# Add Repo-Style Offline pH TD3 Runner

## Objective

Explain the Gymnasium choice, document the current offline pH RL scaffold, and add a simulation-only TD3 runner that follows the custom loop style used in the RL-assisted repository.

## Files Changed

- `simulation/ph_environment.py`
- `run_offline_ph_td3_training.py`
- `tests/test_offline_ph_rl.py`
- `reports/offline_ph_rl_environment_report.md`
- `change-reports/20260701_172931_offline_ph_td3_runner.md`

## Implementation Summary

- Kept the accepted ideal Henderson-Hasselbalch pH model unchanged.
- Added public pH environment helpers for setpoint updates, normalized action to physical flow mapping, physical flow to normalized action mapping, and ideal-HH nominal target allocation.
- Added `run_offline_ph_td3_training.py`, a repo-style offline simulation loop using:
  - piecewise-constant pH setpoints,
  - HH warm-start cycle,
  - TD3 `take_action`, `push`, and `train_step`,
  - three direct flow actions for acid, acetate, and water,
  - reward `-(pH - target_pH)^2`.
- Added a Markdown report explaining the current scaffold, why Gymnasium was used, how the new custom runner fits the other repo style, verification results, and limitations.
- Extended smoke tests to cover public flow helpers and target updates.

No BioSMB, OPC emulator, hardware, MPC, valve, pump-runner, raw lab CSV, or generated source-repo result files were modified.

## Generated Artifacts

Smoke run output:

- `results/offline_ph_td3_training_20260701_172827/tables/trajectory.csv`
- `results/offline_ph_td3_training_20260701_172827/tables/episode_metrics.csv`
- `results/offline_ph_td3_training_20260701_172827/tables/training_summary.csv`
- `results/offline_ph_td3_training_20260701_172827/tables/config_snapshot.json`
- `results/offline_ph_td3_training_20260701_172827/figures/ph_tracking.png`
- `results/offline_ph_td3_training_20260701_172827/figures/flow_commands.png`
- `results/offline_ph_td3_training_20260701_172827/figures/reward_trace.png`

The generated `results/` folder is ignored by git and was not staged.

## Verification Commands and Results

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP 'pHRL_pycache'
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m py_compile simulation\ph_environment.py run_offline_ph_td3_training.py tests\test_offline_ph_rl.py
```

Result: passed.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' tests\test_offline_ph_rl.py
```

Result: passed with output `offline pH RL smoke tests passed`.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' run_offline_ph_td3_training.py --n-tests 3 --set-points-len 6 --warm-start-cycles 1 --batch-size 4 --buffer-size 128 --actor-hidden 16 --critic-hidden 16 --seed 11
```

Result: passed. The run saved `results/offline_ph_td3_training_20260701_172827` and reported `td3_train_steps = 6`.

## Known Limitations and Next Steps

- The environment remains a static ideal-HH plant, not a validated dynamic model.
- Water is controlled and logged but does not directly change ideal HH pH.
- The TD3 run is a software smoke test, not a scientific controller result.
- Next simulation work should tune the setpoint protocol and decide when to replace the static plant with an identified dynamic pH model.
