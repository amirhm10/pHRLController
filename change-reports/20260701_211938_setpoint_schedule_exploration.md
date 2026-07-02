# Update Offline pH TD3 Setpoint Schedule And Exploration Logging

## Objective

Change the offline pH TD3 runner so setpoints change every 200 steps by default, avoid repeating the old fixed five-target cycle, and make exploration behavior visible in saved results and figures.

## Files Changed

- `run_offline_ph_td3_training.py`
- `helpers/offline_ph_td3_results.py`
- `analysis/generate_offline_ph_td3_report.py`
- `tests/test_offline_ph_rl.py`
- `reports/offline_ph_rl_environment_report.md`
- `reports/offline_ph_td3_training_result_analysis.md`
- `reports/figures/offline_ph_td3_training_20260701_211724_analysis/`
- `change-reports/20260701_211938_setpoint_schedule_exploration.md`

The unrelated worktree deletion `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv` was not touched or staged.

## Implementation Summary

- Added `DEFAULT_SET_POINTS_LEN = 200`.
- Changed default setpoint selection to `admissible_random`.
- The default 25,000-step run now resolves to 125 setpoint segments of 200 steps each.
- `admissible_random` uses seeded stratified random targets over the configured pH range `[3.76, 5.76]`, avoiding the previous repeated fixed target cycle.
- Kept the previous hard-coded target pattern available as `--setpoint-strategy legacy_fixed`.
- Added `tables/setpoint_schedule.csv` to runner outputs.
- Logged exploration diagnostics in `trajectory.csv`:
  - `exploration_sigma`
  - `exploration_magnitude`
  - `action_saturation_fraction`
- Made runner exploration explicit:
  - Gaussian action noise during training cycles only.
  - Default linear decay from `std_start = 0.35` to `std_end = 0.03` over `5000` exploratory action calls.
  - Evaluation cycles use `agent.act_eval(...)` with no exploration noise.
- Updated action diagnostic figures to include exploration traces when available.
- Updated reports to explain the schedule and exploration protocol.

## Generated Artifacts

Smoke-run result folder:

```text
results/offline_ph_td3_training_20260701_211724/
```

Saved setpoint schedule:

```text
cycle,start_step,end_step,target_ph,is_test
0,0,199,5.177313804626465,False
1,200,399,4.938621520996094,False
2,400,599,4.3961005210876465,True
```

Report artifacts:

```text
reports/figures/offline_ph_td3_training_20260701_211724_analysis/
```

## Verification

Compiled the touched Python files:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" -m py_compile run_offline_ph_td3_training.py helpers\offline_ph_td3_results.py analysis\generate_offline_ph_td3_report.py tests\test_offline_ph_rl.py
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
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" run_offline_ph_td3_training.py --total-steps 600 --batch-size 4 --buffer-size 512 --actor-hidden 16 --critic-hidden 16 --seed 41
```

Summary:

```text
total_steps:                       600
setpoint_cycles:                   3
steps_per_cycle:                   200
setpoint_strategy:                 admissible_random
warm_start_steps:                  0
td3_train_steps:                   397
overall_MAE:                       0.3350 pH
overall_RMSE:                      0.3793 pH
eval_MAE:                          0.4353 pH
eval_RMSE:                         0.4353 pH
mean_exploration_sigma:            0.2248
mean_exploration_magnitude:        0.1660
mean_action_saturation_fraction:   0.0425
```

Regenerated the analysis report:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" analysis\generate_offline_ph_td3_report.py --result-dir results\offline_ph_td3_training_20260701_211724
```

## Known Limitations And Next Steps

- The setpoints are random but deterministic for a given seed.
- The final cycle is still used as the evaluation segment.
- The 600-step run is only a software smoke test.
- The next substantive run should use `--total-steps 25000 --set-points-len 200`, which gives 125 setpoint segments.
