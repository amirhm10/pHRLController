# Offline pH reward shaping functions

## Objective

Implement reusable pH reward-shaping functions for offline TD3 simulation while keeping the existing three-term reward as the default behavior.

## Files changed

- `simulation/ph_reward.py`
- `simulation/ph_environment.py`
- `run_offline_ph_td3_training.py`
- `helpers/offline_ph_td3_results.py`
- `analysis/generate_offline_ph_td3_report.py`
- `tests/test_offline_ph_rl.py`

## Method or implementation summary

- Added `PHRewardConfig`, `PHRewardBreakdown`, and reward helpers for:
  - `three_term`
  - `relative_band`
  - `relative_band_offset`
- Preserved the existing default reward:

  ```text
  r = -(q_squared * error^2 + q_absolute * abs(error) + move_weight * delta_action^2)
  ```

- Integrated reward dispatch into `PHEnvironment` and kept legacy environment weights mapped into the default reward configuration.
- Added setpoint-hold progress tracking so late-hold offset penalties can be applied when requested.
- Added CLI flags for shaped reward modes in `run_offline_ph_td3_training.py`.
- Added shaped reward components to trajectory tables, cycle summaries, metrics, config snapshots, and generated report text.
- Added focused unit tests for unchanged default behavior, reward ordering, shaped component exposure, late-hold offset penalty behavior, and invalid mode validation.

## Generated artifacts

Smoke runs generated ignored local result folders:

- `results/_smoke_ph_reward_default/`
- `results/_smoke_ph_reward_relative_band_offset/`

No raw lab data was edited.

## Verification commands and results

Used available interpreter:

```powershell
C:\Users\HAMEDI\miniconda3\envs\rl\python.exe
```

The preferred interpreter from `AGENTS.md` was not present at:

```powershell
C:\Users\hamediaa\.conda\envs\rl-env\python.exe
```

Commands run:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" -m py_compile simulation\ph_reward.py simulation\ph_environment.py run_offline_ph_td3_training.py helpers\offline_ph_td3_results.py analysis\generate_offline_ph_td3_report.py tests\test_offline_ph_rl.py
```

Result: passed.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" tests\test_offline_ph_rl.py
```

Result: `offline pH RL smoke tests passed`.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" run_offline_ph_td3_training.py --total-steps 18 --n-tests 3 --batch-size 4 --buffer-size 128 --actor-hidden 16 --critic-hidden 16 --seed 37 --output-dir results\_smoke_ph_reward_default
```

Result: passed with `reward_mode` set to `three_term`.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" run_offline_ph_td3_training.py --total-steps 18 --n-tests 3 --batch-size 4 --buffer-size 128 --actor-hidden 16 --critic-hidden 16 --seed 37 --reward-mode relative_band_offset --reward-tail-offset-weight 5.0 --output-dir results\_smoke_ph_reward_relative_band_offset
```

Result: passed with `reward_mode` set to `relative_band_offset`.

```powershell
git diff --check -- analysis/generate_offline_ph_td3_report.py helpers/offline_ph_td3_results.py run_offline_ph_td3_training.py simulation/ph_environment.py simulation/ph_reward.py tests/test_offline_ph_rl.py
```

Result: passed, with expected CRLF conversion warnings only.

## Known limitations or next steps

- The shaped rewards are integrated only into the offline pH TD3 simulation path.
- No BioSMB hardware, live controller, MPC, or deployment path was added.
- The shaped reward should remain a diagnostic/training tool until the dynamic pH model is validated against `PH_2`.
