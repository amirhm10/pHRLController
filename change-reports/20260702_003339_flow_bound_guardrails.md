# Flow Bound Guardrails

Date: 2026-07-02

## Objective

Make the offline pH TD3 workflow explicitly enforce and verify that physical pump flowrates stay inside configured bounds, especially the 10 mL/min upper bound for each stream.

## Files Changed

- `simulation/ph_environment.py`
- `run_offline_ph_td3_training.py`
- `analysis/generate_offline_ph_td3_report.py`
- `tests/test_offline_ph_rl.py`
- `reports/offline_ph_td3_training_result_analysis.md`
- `reports/figures/offline_ph_td3_training_20260701_221816_analysis/manifest.json`

The unrelated dirty deletion `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv` was not modified or staged.

## Implementation Summary

- Added environment-level flow assertions after action-to-flow mapping and flow clipping.
- Added `PHEnvironment.assert_current_flow_constraints()` for direct checks in tests and future diagnostics.
- Added `PHEnvironment.flow_constraint_summary()` for readable active constraint values.
- Added `validate_trajectory_flow_constraints(...)` in `run_offline_ph_td3_training.py`.
- The runner now validates all logged acid, acetate, and water flows before saving final result tables.
- The runner now saves `tables/flow_constraint_check.csv` in new training result folders.
- Updated tests to sweep extreme normalized actions from `-5` to `5` and confirm the clipped physical flows remain within bounds.
- Updated tests to verify that invalid saved trajectories fail with a `ValueError`.
- Updated the generated report text to state whether any logged flow exceeded configured pump bounds.

## Constraint Logic

For the current default setup:

```text
F_acid + F_acetate = 15 mL/min
1 <= F_acid <= 10
1 <= F_acetate <= 10
F_water = 5 mL/min
```

The feasible fixed-sum acid range becomes:

```text
5 <= F_acid <= 10
```

Since:

```text
F_acetate = 15 - F_acid
```

the acetate range is also:

```text
5 <= F_acetate <= 10
```

Therefore acid and acetate cannot exceed 10 mL/min under the current ratio-action mapping. The new runtime guards make this fail loudly if a future code change breaks that property.

## Verification

Compiled touched Python files:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" -m py_compile simulation\ph_environment.py run_offline_ph_td3_training.py analysis\generate_offline_ph_td3_report.py tests\test_offline_ph_rl.py
```

Ran smoke tests:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" tests\test_offline_ph_rl.py
```

Result:

```text
offline pH RL smoke tests passed
```

Ran a short runner smoke in the temp directory and confirmed `flow_constraint_check.csv` reported zero below-bound and above-bound violations for acid, acetate, and water.

Regenerated the latest analysis report:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -X pycache_prefix="$env:TEMP\pHRL_pycache" analysis\generate_offline_ph_td3_report.py --result-dir results\offline_ph_td3_training_20260701_221816
```

The report now states:

```text
Flow-limit check: no logged acid, acetate, or water flow exceeded its configured pump bounds. The maximum logged physical flow was 10 mL/min.
```

## Known Limitations

- This guarantees simulated/logged flow bounds only.
- It does not validate hardware pump calibration.
- The plant model is still static ideal Henderson-Hasselbalch and does not include mixing delay or sensor dynamics.
