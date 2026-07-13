# Clean TD3 state and action handling

## Objective

Remove unused SAC state and action code, enforce the saved TD3 flow rules, and
prepare the current and next states plus measured action for later online
training without adding reward or learning updates yet.

## Files changed

- `Biosmb-run-online/Biosmb-run-online/main.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/controller.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/README.md`
- `tests/test_biosmb_additive_td3.py`
- `reports/biosmb_custom_td3_active_path_report.md`

## Implementation summary

- Removed the unused SAC `build_state()`, `get_default_action()`, and
  `action_to_flow_rates()` functions.
- Kept `get_controller_ph()` and the single TD3 state builder used by the loop.
- Added measured-flow conversion back to normalized ratio and buffer-sum action.
- Added TD3 checks for action dimension, normalized bounds, pump-array mapping,
  individual flow bounds, buffer sum, fixed water, and reported total flow.
- Built and logged `next_state` after the decision interval.
- Logged the measured normalized action and used measured flows as the next
  step's previous-action reference.
- Added `# I changed this line:` comments to the changed main-file areas.

## Generated artifacts

- This change report.

## Verification commands and results

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m py_compile `
  Biosmb-run-online/Biosmb-run-online/main.py `
  Biosmb-run-online/Biosmb-run-online/custom_td3/controller.py `
  tests/test_biosmb_additive_td3.py

& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m unittest `
  tests.test_biosmb_additive_td3 `
  tests.test_biosmb_td3_training_fidelity -v
```

Compilation and all 22 hardware-free tests passed.

## Known limitations and next steps

- `get_all_flows()` must still be confirmed as measured readback rather than
  command values.
- The 0.001 mL/min fixed-water tolerance comes from the saved TD3 flow converter
  and may be too strict for physical measurements.
- No hard maximum flow change was added because no reviewed value is available.
- Pump writes remain sequential and do not have an immediate acknowledgement
  or readback check.
- Reward, replay insertion, `train_step()`, and online saving remain unconnected.
