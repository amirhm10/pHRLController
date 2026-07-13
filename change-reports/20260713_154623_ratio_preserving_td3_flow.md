# Ratio-Preserving TD3 Flow Action

## Objective

Implement a single-agent offline TD3 action mode that selects the acetate/acid
ratio first and then selects optional total flow only inside the physical
total-flow interval that preserves that ratio. Add an economic reward term,
diagnostics, tests, and a scientific algorithm report without modifying the
BioSMB online runner.

## Files changed

- `simulation/ph_environment.py`
- `simulation/ph_reward.py`
- `run_offline_ph_td3_training.py`
- `helpers/offline_ph_td3_results.py`
- `tests/test_offline_ph_rl.py`
- `tests/test_biosmb_td3_training_fidelity.py`
- `reports/offline_ph_td3_ratio_preserving_flow_algorithm.md`
- `change-reports/20260713_154623_ratio_preserving_td3_flow.md`

## Implementation summary

- Added the backward-compatible `ratio_preserving_flow` offline action mode.
- Kept one two-output TD3 actor.
- Mapped the first action to a global log acetate/acid ratio.
- Calculated ratio-specific feasible acid+acetate total-flow bounds.
- Mapped the second action to the optional fraction between those bounds.
- Added a squared optional-flow cost with default weight 0.01.
- Added explicit optional-flow, feasible-bound, and reward-component logging.
- Updated action figures to use the label `optional-flow action`.
- Restored the default experiment to `gamma = 0.97` and final exploration
  standard deviation 0.02 for the first controlled run of the new method.
- Preserved the older `ratio` and `ratio_buffer_sum` modes for ablations.
- Prevented the new action contract from being exported as the existing
  `ratio_buffer_sum_v1` BioSMB bundle.
- Left all files under `Biosmb-run-online` unchanged.

## Generated artifacts

- Added the algorithm report at
  `reports/offline_ph_td3_ratio_preserving_flow_algorithm.md`.
- Generated and inspected a disposable 400-step smoke-result directory under
  `results/codex_smoke_ratio_preserving_flow`.
- Removed the disposable smoke directory after verification.
- No full 500,000-step scientific result was generated in this work item.

## Verification commands and results

Compilation:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m py_compile simulation/ph_environment.py simulation/ph_reward.py helpers/offline_ph_td3_results.py run_offline_ph_td3_training.py tests/test_offline_ph_rl.py tests/test_biosmb_td3_training_fidelity.py
```

Result: passed.

Repository tests:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m pytest -p no:cacheprovider tests -q
```

Result: 50 passed.

End-to-end smoke run:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' run_offline_ph_td3_training.py --total-steps 400 --set-points-len 20 --output-dir results/codex_smoke_ratio_preserving_flow --no-save-checkpoint
```

Result: completed with 317 TD3 updates and all expected tables and figures.
The run was too short for tracking-performance interpretation.

Action-contract checks from the smoke trajectory:

- maximum log-ratio conversion error: `9.315872095960742e-08`
- maximum optional-flow fraction conversion error: `2.5158143778236663e-06`
- ratio-specific infeasible rows: `0`
- global pump, total-flow, and water constraint violations: `0`

Diff validation:

```powershell
git diff --check
```

Result: passed.

## Known limitations and next steps

- The plant remains an instantaneous ideal Henderson-Hasselbalch model.
- The 2 mL/min configured total-flow minimum has not been validated as a safe
  laboratory operating minimum.
- The economic weight of 0.01 is an initial value, not an optimized result.
- Existing checkpoints and replay data are incompatible with the new second
  action meaning.
- The new mode is intentionally not wired into `Biosmb-run-online`.
- Run a full 500,000-step training experiment and evaluate the frozen actor over
  a common 25-target grid before considering online integration.
