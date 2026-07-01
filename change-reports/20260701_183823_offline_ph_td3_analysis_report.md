# Add Offline pH TD3 Analysis Report Generator

## Objective

Create editable plots, figure assets, CSV diagnostics, and a Markdown write-up for the offline pH TD3 simulation results, following the saved-result reporting style used in the RL-assisted MPC repository.

## Files Changed

- `analysis/generate_offline_ph_td3_report.py`
- `reports/offline_ph_td3_training_result_analysis.md`
- `reports/figures/offline_ph_td3_training_20260701_181330_analysis/*`
- `change-reports/20260701_183823_offline_ph_td3_analysis_report.md`

## Method Or Implementation Summary

- Inspected the external RL-assisted MPC repository patterns:
  - `Simulation/rl_sim.py`
  - `utils/plotting_core.py`
  - `report/scripts/analyze_distillation_all_runners_latest_20260609.py`
  - `report/generate_rl_state_scaling_report.py`
- Added a local pH-specific report generator that reads saved result CSV/JSON files only.
- The generator defaults to the latest `results/offline_ph_td3_training_*` folder and writes:
  - a Markdown report,
  - pH tracking, flow, reward, action, HH-ratio, and loss figures,
  - summary metrics, flow diagnostics, cycle metrics, HH consistency checks, and a manifest.
- Kept the analysis offline and simulation-only. It does not launch BioSMB, the OPC emulator, hardware, MPC, valves, or pumps.

## Generated Artifacts

Report:

- `reports/offline_ph_td3_training_result_analysis.md`

Generated figure/data folder:

- `reports/figures/offline_ph_td3_training_20260701_181330_analysis/`

Files in the generated folder:

- `summary_metrics.csv`
- `flow_diagnostics.csv`
- `cycle_metrics.csv`
- `hh_consistency.csv`
- `source_training_summary.csv`
- `manifest.json`
- `fig_ph_tracking_error_reward.png`
- `fig_flow_commands_and_ratio.png`
- `fig_cycle_metrics.png`
- `fig_action_diagnostics.png`
- `fig_hh_ratio_consistency.png`
- `fig_training_losses.png`

## Verification Commands And Results

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP 'pHRL_pycache'
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m py_compile analysis\generate_offline_ph_td3_report.py
```

Result: passed.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' analysis\generate_offline_ph_td3_report.py
```

Result: passed. The script wrote:

- `reports/offline_ph_td3_training_result_analysis.md`
- `reports/figures/offline_ph_td3_training_20260701_181330_analysis/`

## Known Limitations Or Next Steps

- The report is based on the latest saved offline result folder, `results/offline_ph_td3_training_20260701_181330`.
- The result is still a static ideal-Henderson-Hasselbalch software diagnostic, not a validated controller result.
- After running a longer TD3 experiment, rerun `analysis/generate_offline_ph_td3_report.py` to refresh the plots and write-up.
- The unrelated deleted file `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv` remains unstaged and untouched.
