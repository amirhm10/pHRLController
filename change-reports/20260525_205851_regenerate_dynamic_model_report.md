# Regenerate dynamic model report artifacts

## Objective

Regenerate the figures and tables used by `reports/dynamic_model_identification_report.md` from the restored lab CSV using the project Conda interpreter `rlenv`.

## Files changed

- `reports/dynamic_model_identification_report.md`
- `change-reports/20260525_205851_regenerate_dynamic_model_report.md`

## Method and implementation summary

- Used `C:\Users\hamed\miniconda3\envs\rlenv\python.exe`.
- Recompiled the relevant runners before execution.
- Ran the current static chemistry, dynamic identification, full transport-delay, and regime-specific transport-delay workflows.
- Updated the report to point to the new timestamped result folders.
- Replaced missing historical pre-patch image embeds with a provenance note because those old result folders are not present in the current checkout.
- Kept the model interpretation unchanged: static affine equilibrium calibration remains the best current empirical predictor, and transport delay remains weak or non-identifiable in this CSV.

## Generated artifacts

- `results/effective_static_chemistry_calibration_20260525_205542/`
- `results/dynamic_model_identification_20260525_205317/`
- `results/transport_delay_identification_20260525_205338/`
- `results/first_regime_transport_delay_identification_20260525_205417/`
- `results/second_regime_transport_delay_identification_20260525_205433/`

## Verification commands and results

```powershell
& 'C:\Users\hamed\miniconda3\envs\rlenv\python.exe' -m py_compile run_dynamic_model_identification.py run_transport_delay_identification.py run_first_regime_transport_delay_identification.py run_second_regime_transport_delay_identification.py run_effective_static_chemistry_calibration.py
```

Result: passed.

```powershell
& 'C:\Users\hamed\miniconda3\envs\rlenv\python.exe' run_dynamic_model_identification.py
```

Result: completed in `results/dynamic_model_identification_20260525_205317/`. Test RMSE values were equilibrium `0.4412`, static `0.0975`, lag `0.0975`, and dynamic `0.0975`.

```powershell
& 'C:\Users\hamed\miniconda3\envs\rlenv\python.exe' run_transport_delay_identification.py
```

Result: completed in `results/transport_delay_identification_20260525_205338/`. Best `V_tube` was `0.000 mL` with identifiability `weak_non_identifiable_near_zero_volume`.

```powershell
& 'C:\Users\hamed\miniconda3\envs\rlenv\python.exe' run_first_regime_transport_delay_identification.py
```

Result: completed in `results/first_regime_transport_delay_identification_20260525_205417/`. Best `V_tube` was `1.012 mL`, but test RMSE improved by only about `0.001 pH`.

```powershell
& 'C:\Users\hamed\miniconda3\envs\rlenv\python.exe' run_second_regime_transport_delay_identification.py
```

Result: completed in `results/second_regime_transport_delay_identification_20260525_205433/`. Best `V_tube` was `0.467 mL`, with no meaningful held-out improvement.

```powershell
& 'C:\Users\hamed\miniconda3\envs\rlenv\python.exe' run_effective_static_chemistry_calibration.py
```

Result: completed in `results/effective_static_chemistry_calibration_20260525_205542/`. Raw HH all-row RMSE was `0.3976`, raw equilibrium all-row RMSE was `0.3982`, and affine static test RMSE was about `0.0975`.

Markdown image-link audit result: all embedded report image links resolve.

## Known limitations and next steps

- The old standalone Henderson-Hasselbalch and equilibrium validation runners referenced in the historical AGENTS context are not present in this checkout, so the static section was regenerated with the current combined static-chemistry runner.
- The current CSV still does not identify a trustworthy nonzero transport volume. A designed open-loop experiment with faster logging and long holds is still the next safe modeling step.
