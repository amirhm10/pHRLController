# Regime Transport Delay Report Extension

## Objective

Run the transport-delay identification workflow on the remaining sampling-time regime and extend the dynamic model report with a side-by-side comparison of the two sampling regimes.

## Files Changed

- `run_first_regime_transport_delay_identification.py`
- `reports/dynamic_model_identification_report.md`
- `change-reports/20260522_140932_regime_transport_delay_report.md`

## Method Summary

- Added a first-regime runner for the two-minute sampling sessions:
  ```text
  session_id <= 3
  ```
- Reused the same transported-volume delay model:
  ```text
  theta_s = 60 V_tube / F_T
  ```
- Compared the new two-minute result against the existing one-minute runner:
  ```text
  session_id >= 4
  ```
- Extended the report with subset definitions, metrics, figures, and interpretation.

## Generated Artifacts

The verified first-regime run wrote:

```text
results/first_regime_transport_delay_identification_20260522_140759/
```

The report also references the existing second-regime run:

```text
results/second_regime_transport_delay_identification_20260522_140308/
```

## Verification Commands And Results

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile run_first_regime_transport_delay_identification.py run_second_regime_transport_delay_identification.py
```

Result: successful compile.

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_first_regime_transport_delay_identification.py
```

Result: successful run.

Console summary:

```text
Subset sessions=0,1,2,3; median dt=141.4 s.
Test RMSE: equilibrium=0.4272, static=0.2914, transport=0.2904, transport+dynamic=0.2904.
Best V_tube=1.012 mL; median theta=3.71 s; identifiability=weak_non_identifiable_small_rmse_gain.
```

Additional checks:

- All expected first-regime CSV tables are non-empty.
- All expected first-regime PNG figures are non-empty.
- `PH_1`, `target_ph`, and target metrics are absent from first-regime generated tables.
- Report image links resolve.
- No escaped-star KaTeX patterns were found.

## Known Limitations And Next Steps

- The two-minute regime gives only a tiny transport-delay improvement, about `0.001 pH` test RMSE.
- The one-minute regime gives no meaningful transport-delay improvement.
- Both subset fits estimate delays much shorter than the sampling interval, so neither should be treated as reliable tubing geometry.
- Faster open-loop step data are still needed to identify physical transport delay.
