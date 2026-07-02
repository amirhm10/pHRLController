# Ratio Action Fixed Buffer Sum

Date: 2026-07-01

## Objective

Update the offline pH TD3 simulation so the RL agent controls only the acid/acetate ratio while keeping:

- `F_acid + F_acetate = 15` mL/min by default,
- `F_water = 5` mL/min,
- the accepted ideal Henderson-Hasselbalch first-principles pH model unchanged.

No BioSMB, emulator, hardware runner, MPC layer, valve logic, or live controller code was added.

## Files Changed

- `simulation/ph_environment.py`
- `run_offline_ph_td3_training.py`
- `helpers/offline_ph_td3_results.py`
- `analysis/generate_offline_ph_td3_report.py`
- `tests/test_offline_ph_rl.py`
- `reports/offline_ph_rl_environment_report.md`
- `reports/offline_ph_td3_training_result_analysis.md`
- `reports/figures/offline_ph_td3_training_20260701_212825_analysis/`

The unrelated dirty deletion `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv` was not modified or staged.

## Implementation Summary

- Changed the pH RL environment action space from two independent acid/base actions to one normalized ratio action.
- Mapped the ratio action in log-ratio space to `F_acetate / F_acid`.
- Enforced a fixed acid-plus-acetate flow sum through the environment and runner.
- Kept water fixed at `PHProcessConfig.default_water_flow`, currently 5 mL/min.
- Updated observations to `[current_pH, target_pH, pH_error, ratio_action, step_fraction]`.
- Added helpers for fixed-sum feasible acid bounds and reachable ideal-HH setpoint bounds.
- Updated TD3 agent creation to `state_dim=5` and `action_dim=1`.
- Updated setpoint generation to sample from the reachable fixed-sum ideal-HH pH range, about 4.45897-5.06103 for a 15 mL/min buffer-flow sum with 1-10 mL/min pump bounds.
- Updated trajectory logging, diagnostics, plots, and generated reports to use `action_ratio` and `buffer_flow_sum`.

## Generated Artifacts

Smoke run:

```text
results/offline_ph_td3_training_20260701_212825/
```

Generated report bundle:

```text
reports/offline_ph_td3_training_result_analysis.md
reports/figures/offline_ph_td3_training_20260701_212825_analysis/
```

Smoke-run summary:

```text
total_steps:              600
setpoint_cycles:          3
steps_per_cycle:          200
setpoint_strategy:        admissible_random
setpoint_min:             4.458970
setpoint_max:             5.061030
warm_start_steps:         0
td3_train_steps:          397
batch_size:               4
overall_MAE:              0.1543 pH
overall_RMSE:             0.1780 pH
eval_MAE:                 0.2444 pH
eval_RMSE:                0.2444 pH
fixed_buffer_flow_sum:    15.0 mL/min
fixed_water_flow:         5.0 mL/min
```

## Verification

Compiled changed Python files:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" -m py_compile simulation\ph_environment.py run_offline_ph_td3_training.py helpers\offline_ph_td3_results.py analysis\generate_offline_ph_td3_report.py tests\test_offline_ph_rl.py
```

Smoke tests:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" tests\test_offline_ph_rl.py
```

Result:

```text
offline pH RL smoke tests passed
```

Training smoke:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" run_offline_ph_td3_training.py --total-steps 600 --batch-size 4 --buffer-size 512 --actor-hidden 16 --critic-hidden 16 --seed 47
```

Report generation:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" analysis\generate_offline_ph_td3_report.py --result-dir results\offline_ph_td3_training_20260701_212825
```

## Known Limitations And Next Steps

- The plant is still a static ideal-HH simulation, not a validated dynamic plant.
- The fixed 15 mL/min buffer-flow sum narrows the reachable pH range under the current pump bounds.
- Water is fixed and logged but does not directly affect ideal HH pH.
- The smoke run is only a software verification run, not a performance claim.
- Next useful offline work is to sweep fixed buffer sums, setpoint ranges, reward weights, and seeds before replacing the static plant with an identified dynamic pH model.
