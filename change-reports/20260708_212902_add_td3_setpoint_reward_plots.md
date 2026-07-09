# Add offline TD3 setpoint reward plots

## Objective

Update the offline pH TD3 plotting functions so new training runs automatically save:

- average reward per held setpoint segment,
- focused tracking diagnostics for the last five setpoint holds,
- a table backing the setpoint-average reward plot.

## Files changed

- `helpers/offline_ph_td3_results.py`
- `run_offline_ph_td3_training.py`
- `tests/test_offline_ph_rl.py`

## Method or implementation summary

- Added `compute_setpoint_reward_metrics(...)` to summarize each setpoint hold with:
  - cycle index,
  - target pH,
  - start and end step,
  - number of steps,
  - mean reward,
  - reward sum,
  - MAE,
  - RMSE,
  - maximum absolute pH error.
- Added `fig_setpoint_average_reward.png`, where each bar is:

  ```text
  mean_reward_i = mean_t_in_cycle_i(reward_t)
  ```

  This is the average reward per step within each setpoint-length hold, not the total reward sum.
- Updated `fig_cycle_metrics.png` so the reward panel uses mean reward rather than reward sum.
- Added `fig_last_5_setpoint_tracking.png`, with the last setpoint holds showing:
  - pH and target,
  - pH error,
  - reward,
  - acid, acetate, and water flows,
  - ratio action and exploration sigma when available.
- Added `setpoint_reward_metrics.csv` to the result tables and artifact manifest.
- Added smoke-test assertions that the new table and plots are generated.

This change is limited to the runner artifact functions used by new offline TD3 runs. Historical report generation and previous result analysis were not modified.

## Generated artifacts

Smoke run generated an ignored local result folder:

- `results/_smoke_ph_plot_functions/`

Confirmed generated figures:

- `fig_setpoint_average_reward.png`
- `fig_last_5_setpoint_tracking.png`
- existing standard TD3 diagnostic figures

Confirmed generated table:

- `setpoint_reward_metrics.csv`

No raw lab data was edited.

## Verification commands and results

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" -m py_compile helpers\offline_ph_td3_results.py run_offline_ph_td3_training.py tests\test_offline_ph_rl.py
```

Result: passed.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" tests\test_offline_ph_rl.py
```

Result: `offline pH RL smoke tests passed`.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" run_offline_ph_td3_training.py --total-steps 18 --n-tests 3 --batch-size 4 --buffer-size 128 --actor-hidden 16 --critic-hidden 16 --seed 45 --output-dir results\_smoke_ph_plot_functions
```

Result: passed and generated the new plot/table artifacts.

```powershell
git diff --check -- helpers/offline_ph_td3_results.py run_offline_ph_td3_training.py tests/test_offline_ph_rl.py
```

Result: passed, with expected CRLF conversion warnings only.

## Known limitations or next steps

- The smoke run verifies plotting and table generation only, not 100k-step training quality.
- The last-five-setpoints figure uses however many cycles exist when fewer than five are present.
- The previous report-analysis script is intentionally unchanged for this task.
