# Transport Delay Identification Runner

## Objective

Add a separate artifact-only runner to test whether the current lab CSV can identify a physical transport delay using an effective tubing-volume parameter:

```text
theta(t) ~= V_tube / F_T(t)
```

## Files Changed

- `run_transport_delay_identification.py`
- `helpers/transport_delay_identification.py`
- `helpers/transport_delay_plotting.py`
- `change-reports/20260522_134928_transport_delay_identification.md`

## Method Summary

- Reused existing lab CSV loading, preprocessing, flat-trial filtering, trial-aware train/test splitting, and equilibrium charge-balance prediction.
- Built a within-trial cumulative transported-volume coordinate:
  ```text
  Q[k] = Q[k-1] + F_T[k-1] dt[k] / 60
  ```
- For each candidate `V_tube_mL`, delayed equilibrium pH in transported-volume space and fit:
  ```text
  PH_2 = b0(V_tube) + b1(V_tube) pH_eq_delayed
  ```
- Selected `V_tube_mL` by train RMSE over `0-60 mL`, with grid search and local refinement.
- Added an optional first-order diagnostic after the transport-delay model, marked as empirical smoothing rather than a physical tubing-volume estimate.

## Generated Artifacts

The verified run wrote:

```text
results/transport_delay_identification_20260522_134840/
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
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile run_transport_delay_identification.py helpers\transport_delay_identification.py helpers\transport_delay_plotting.py
```

Result: successful compile.

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_transport_delay_identification.py
```

Result: successful run.

Console summary:

```text
Test RMSE: equilibrium=0.4412, static=0.0975, transport=0.0975, transport+dynamic=0.0975.
Best V_tube=0.000 mL; median theta=0.00 s; identifiability=weak_non_identifiable_near_zero_volume.
```

Additional checks:

- All expected CSV tables are non-empty.
- All expected PNG figures are non-empty.
- `PH_1`, `target_ph`, and target metrics are absent from the generated transport-delay tables.

## Known Limitations And Next Steps

- The current CSV does not support a nonzero transport-delay estimate; the best volume is exactly `0.0 mL`.
- The result means delay is either below the sampling resolution, confounded with static calibration, or not excited clearly enough by the current closed-loop data.
- A designed open-loop step experiment with faster pH logging and known tubing geometry is still needed to estimate a physical tubing volume reliably.
