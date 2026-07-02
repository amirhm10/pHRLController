# Latest TD3 Result Analysis

Date: 2026-07-01

## Objective

Analyze the latest offline pH TD3 result bundle and update the generated report so it explains both performance and next experimental steps.

Latest result analyzed:

```text
results/offline_ph_td3_training_20260701_221816/
```

## Files Changed

- `analysis/generate_offline_ph_td3_report.py`
- `reports/offline_ph_td3_training_result_analysis.md`
- `reports/figures/offline_ph_td3_training_20260701_221816_analysis/`

The unrelated dirty deletion `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv` was not modified or staged.

## Method Summary

- Regenerated the report from the saved 25,000-step trajectory and summary tables.
- Added reproducible diagnostics to the report generator:
  - learning-phase metrics,
  - cycle-group metrics,
  - settling diagnostics at 0.05 and 0.02 pH tolerance bands,
  - best and worst setpoint-cycle tables,
  - dynamic provenance for the analyzed result folder.
- Kept the analysis simulation-only. No BioSMB, emulator, hardware, MPC, valves, or pumps were launched.

## Main Findings

- Overall MAE was `0.02842` pH and RMSE was `0.05332` pH over 25,000 steps.
- The final evaluation cycle MAE was `0.01586` pH and RMSE was `0.01617` pH.
- The first 5,000 steps had `0.08404` pH MAE, while the post-exploration-decay region had `0.01452` pH MAE.
- The first 25 setpoint cycles dominated the failures. Later cycle groups were near `0.012-0.016` pH MAE.
- At 0.05 pH tolerance with a 20-step hold, 99 of 125 cycles settled. At 0.02 pH tolerance, 66 of 125 cycles settled.
- Acid plus acetate stayed fixed at 15 mL/min, and water stayed fixed at 5 mL/min.

## Generated Artifacts

Updated report:

```text
reports/offline_ph_td3_training_result_analysis.md
```

Updated report bundle:

```text
reports/figures/offline_ph_td3_training_20260701_221816_analysis/
```

New or regenerated diagnostics include:

- `learning_phase_metrics.csv`
- `cycle_group_metrics.csv`
- `settling_diagnostics.csv`
- `cycle_extremes.csv`
- `summary_metrics.csv`
- `flow_diagnostics.csv`
- `cycle_metrics.csv`
- six PNG figures

## Verification

Compiled the updated report generator:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" -m py_compile analysis\generate_offline_ph_td3_report.py
```

Regenerated the latest report:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" analysis\generate_offline_ph_td3_report.py --result-dir results\offline_ph_td3_training_20260701_221816
```

Result:

```text
Wrote report: reports/offline_ph_td3_training_result_analysis.md
Wrote figures and tables under: reports/figures/offline_ph_td3_training_20260701_221816_analysis
```

## Recommended Next Steps

1. Add a deterministic evaluation sweep after training, using a frozen actor and many reachable setpoints rather than only the final setpoint cycle.
2. Run a seed batch, for example seeds 7, 21, 47, 73, and 101, and compare mean and worst-case evaluation MAE.
3. Run a fixed-buffer-sum sweep such as 12, 15, and 18 mL/min, recording reachable pH range, saturation frequency, and tracking metrics.
4. Keep these experiments simulation-only until the dynamic pH model with delay, mixing, and sensor response is ready.
