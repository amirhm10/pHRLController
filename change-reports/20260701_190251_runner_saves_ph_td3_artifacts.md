# Make Offline pH TD3 Runner Save Full Artifacts

## Objective

Move the richer offline pH TD3 plotting and diagnostic logic into reusable functions and call those functions directly from `run_offline_ph_td3_training.py`, so every runner execution saves analysis-ready figures and result tables for later editing.

## Files Changed

- `helpers/offline_ph_td3_results.py`
- `run_offline_ph_td3_training.py`
- `tests/test_offline_ph_rl.py`
- `change-reports/20260701_190251_runner_saves_ph_td3_artifacts.md`

## Method Or Implementation Summary

- Added `helpers/offline_ph_td3_results.py` with reusable functions for:
  - Henderson-Hasselbalch ratio consistency columns,
  - summary metrics by run phase,
  - flow diagnostics and saturation checks,
  - HH consistency checks,
  - pH tracking/error/reward plots,
  - flow and acid/acetate ratio plots,
  - per-cycle metric plots,
  - action-space diagnostic plots,
  - HH ratio consistency plots,
  - TD3 actor/critic loss plots when train-step losses are present,
  - result artifact manifest writing.
- Updated `run_offline_ph_td3_training.py` so the runner now writes the full diagnostic package under each result folder:
  - `tables/trajectory_diagnostics.csv`
  - `tables/summary_metrics.csv`
  - `tables/flow_diagnostics.csv`
  - `tables/hh_consistency.csv`
  - `tables/source_training_summary.csv`
  - `tables/result_artifact_manifest.json`
  - `figures/fig_ph_tracking_error_reward.png`
  - `figures/fig_flow_commands_and_ratio.png`
  - `figures/fig_cycle_metrics.png`
  - `figures/fig_action_diagnostics.png`
  - `figures/fig_hh_ratio_consistency.png`
  - `figures/fig_training_losses.png` when training losses exist.
- Extended the smoke tests to verify the artifact helper saves tables and figures.

No BioSMB, OPC emulator, hardware, MPC, valve, pump-runner, or raw lab CSV files were modified.

## Generated Artifacts

Verification runner output:

- `results/offline_ph_td3_training_20260701_190035/`

This generated result folder includes the full figure and diagnostic table package listed above. The folder is under ignored `results/` and was not staged.

Smoke-test output:

- `results/_test_offline_ph_td3_artifacts/`

This folder is also ignored and was not staged.

## Verification Commands And Results

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP 'pHRL_pycache'
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m py_compile helpers\offline_ph_td3_results.py run_offline_ph_td3_training.py analysis\generate_offline_ph_td3_report.py tests\test_offline_ph_rl.py
```

Result: passed.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' tests\test_offline_ph_rl.py
```

Result: passed with output `offline pH RL smoke tests passed`.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' run_offline_ph_td3_training.py --n-tests 3 --set-points-len 6 --warm-start-cycles 1 --batch-size 4 --buffer-size 128 --actor-hidden 16 --critic-hidden 16 --seed 17
```

Result: passed. The runner printed:

```text
Saved offline pH TD3 results to: results\offline_ph_td3_training_20260701_190035
Saved TD3 pH figures to: results\offline_ph_td3_training_20260701_190035\figures
td3_train_steps: 6
```

## Known Limitations Or Next Steps

- The saved artifacts still describe a static ideal Henderson-Hasselbalch simulation.
- Water remains a logged and controlled actuator but does not directly change ideal HH pH when acid and acetate stocks are equal.
- The next practical step is to run a longer training case and inspect the runner-saved figures directly from that result folder.
- The unrelated deleted file `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv` remains unstaged and untouched.
