# Increase offline TD3 steps and pH bonus weight

## Objective

Make the offline pH TD3 runner use a longer default rollout and strengthen the near-setpoint shaped reward bonus to encourage lower steady offset.

## Files changed

- `run_offline_ph_td3_training.py`
- `tests/test_offline_ph_rl.py`

## Method or implementation summary

- Changed the default rollout length from `25_000` steps to `100_000` steps in `run_offline_ph_td3_training.py`.
- Added a new CLI parameter:

  ```powershell
  --reward-bonus-weight
  ```

- Set `--reward-bonus-weight` default to `25.0`.
- Passed the bonus weight into `PHRewardConfig.beta`.
- Saved `reward_bonus_weight` in both:
  - `training_summary.csv`
  - `config_snapshot.json`
- Updated the offline pH RL smoke test to assert the new default `100_000` step rollout and `beta = 25.0`.

With `band_floor_ph = 0.02`, the maximum shaped bonus scales as:

```text
J_bonus,max = beta * q_band * band_floor_ph^2
```

So the default maximum near-zero-error bonus increases from:

```text
7.0 * 1.0 * 0.02^2 = 0.0028
```

to:

```text
25.0 * 1.0 * 0.02^2 = 0.0100
```

This makes the zero-offset region more attractive relative to the absolute-error penalty. It does not mathematically guarantee offset-free control, so the next full run should still check evaluation MAE, final offset, and per-setpoint tail error.

## Generated artifacts

Smoke run generated an ignored local result folder:

- `results/_smoke_ph_reward_100k_bonus_default/`

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
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" run_offline_ph_td3_training.py --total-steps 18 --n-tests 3 --batch-size 4 --buffer-size 128 --actor-hidden 16 --critic-hidden 16 --seed 43 --output-dir results\_smoke_ph_reward_100k_bonus_default
```

Result: passed. The saved summary reported:

```text
reward_mode = relative_band_offset
reward_bonus_weight = 25.0
reward_tail_offset_weight = 5.0
```

```powershell
git diff --check -- run_offline_ph_td3_training.py tests/test_offline_ph_rl.py
```

Result: passed, with expected CRLF conversion warnings only.

## Known limitations or next steps

- The smoke run intentionally used `--total-steps 18`, so it verifies configuration plumbing but not 100k-step training quality.
- Run the full default 100k protocol next and compare tail offset against the previous 50k run.
- If offset remains nonzero, the next controlled ablation should compare `reward_bonus_weight = 25.0`, `50.0`, and `100.0` with matched seeds.
