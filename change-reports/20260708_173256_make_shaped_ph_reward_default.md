# Make shaped pH reward the offline trainer default

## Objective

Make the offset-focused shaped reward the default for `run_offline_ph_td3_training.py` and document the selected default parameters.

## Files changed

- `run_offline_ph_td3_training.py`
- `tests/test_offline_ph_rl.py`

## Method or implementation summary

- Changed the offline trainer default reward mode from `three_term` to `relative_band_offset`.
- Changed the default late-hold offset penalty from `0.0` to `5.0` so persistent offset is penalized by default during the final part of each setpoint hold.
- Kept the original three-term reward available through:

  ```powershell
  --reward-mode three_term
  ```

- Added a regression test proving the runner defaults resolve to the offset-focused shaped reward.

Default reward parameters after this change:

```text
mode = relative_band_offset
q_squared = 1.0
q_absolute = 1.0
move_weight = 0.01
band_floor_ph = 0.02
q_band = 1.0
r_move = 0.01
tau_frac = 0.7
gamma_out = 0.5
gamma_in = 0.5
beta = 7.0
bonus_kind = exp
bonus_k = 12.0
reward_scale = 1.0
absolute_error_weight = 1.0
tail_offset_weight = 5.0
tail_start_fraction = 0.75
```

## Generated artifacts

Smoke run generated an ignored local result folder:

- `results/_smoke_ph_reward_default_shaped/`

No raw lab data was edited.

## Verification commands and results

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" -m py_compile run_offline_ph_td3_training.py tests\test_offline_ph_rl.py
```

Result: passed.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" tests\test_offline_ph_rl.py
```

Result: `offline pH RL smoke tests passed`.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" run_offline_ph_td3_training.py --total-steps 18 --n-tests 3 --batch-size 4 --buffer-size 128 --actor-hidden 16 --critic-hidden 16 --seed 41 --output-dir results\_smoke_ph_reward_default_shaped
```

Result: passed. The saved summary reported:

```text
reward_mode = relative_band_offset
reward_band_floor_ph = 0.02
reward_tail_offset_weight = 5.0
```

```powershell
git diff --check -- run_offline_ph_td3_training.py tests/test_offline_ph_rl.py
```

Result: passed, with expected CRLF conversion warnings only.

## Known limitations or next steps

- This changes the offline training runner default only.
- The legacy three-term reward remains available for ablation and reproducibility.
- The shaped reward should be compared against `three_term` with matched seeds before using the new default as evidence of better pH tracking.
