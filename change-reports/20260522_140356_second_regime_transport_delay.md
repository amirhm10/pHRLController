# Second-Regime Transport Delay Test

## Objective

Add and run a separate transport-delay identification test using only the later one-minute-sampling regime.

## Files Changed

- `run_second_regime_transport_delay_identification.py`
- `change-reports/20260522_140356_second_regime_transport_delay.md`

## Method Summary

- Reused the transport-delay identification workflow.
- Filtered the preprocessed lab data to:
  ```text
  session_id >= 4
  ```
- This selects sessions `4,5,6`, corresponding to sample indices `417-1085`.
- The subset median sampling interval is `69.355 s`, with a 5-95 percent range of `69.0218-70.2136 s`.
- Refit train/test split, static calibration, transported-volume delay, and first-order dynamic diagnostic only inside this subset.

## Generated Artifacts

The verified run wrote:

```text
results/second_regime_transport_delay_identification_20260522_140308/
```

Tables:

- `preprocessed_lab_data.csv`
- `transport_delay_model_comparison.csv`
- `model_metrics_train_test.csv`
- `transport_delay_search.csv`
- `transport_delay_parameters.csv`
- `trial_transport_delay_summary.csv`
- `trial_split_summary.csv`
- `sampling_summary.csv`
- `second_regime_subset_summary.csv`

Figures:

- `transport_delay_rmse_search.png`
- `measured_vs_transport_delay_prediction_time.png`
- `measured_vs_transport_delay_prediction_scatter.png`
- `transport_delay_residual_time.png`
- `transport_delay_residual_histogram.png`
- `theta_transport_time.png`
- `total_flow_cumulative_volume.png`
- `transport_delay_trial_examples.png`
- `transport_delay_metric_comparison.png`

## Verification Commands And Results

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile run_second_regime_transport_delay_identification.py
```

Result: successful compile.

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_second_regime_transport_delay_identification.py
```

Result: successful run.

Console summary:

```text
Subset sessions=4,5,6; median dt=69.4 s.
Test RMSE: equilibrium=0.4414, static=0.0513, transport=0.0513, transport+dynamic=0.0516.
Best V_tube=0.467 mL; median theta=1.72 s; identifiability=weak_non_identifiable_near_zero_volume.
```

Additional checks:

- All expected CSV tables are non-empty.
- All expected PNG figures are non-empty.
- `PH_1`, `target_ph`, and target metrics are absent from generated tables.

## Known Limitations And Next Steps

- The best volume is below the `0.5 mL` near-zero threshold and gives no held-out RMSE improvement over static calibration.
- The one-minute regime supports a very small effective delay diagnostic, about `1.72 s`, but this is far below the `69.355 s` sampling interval and should not be interpreted as reliable tubing geometry.
- A faster open-loop step test remains necessary for physical transport-delay identification.
