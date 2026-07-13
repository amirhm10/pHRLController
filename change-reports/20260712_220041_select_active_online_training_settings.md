# Select active control and online-training settings

## Objective

Set the BioSMB main settings to active pump control and mark the intended run
for online TD3 learning, while reviewing Data collection and Target pH without
changing those two code sections.

## Files changed

- `Biosmb-run-online/Biosmb-run-online/main.py`
- `tests/test_biosmb_additive_td3.py`
- `reports/biosmb_custom_td3_active_path_report.md`

## Implementation summary

- Set `control_mode = "active_control"`.
- Added `online_training_enabled = True`.
- Added a clear `# I changed this line:` reason above each setting.
- Left Data collection and Target pH code unchanged.
- Recorded the later validation improvements needed by those two sections.

## Generated artifacts

- This change report.

## Verification commands and results

```powershell
python -m py_compile Biosmb-run-online/Biosmb-run-online/main.py

& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m unittest `
  tests.test_biosmb_additive_td3 `
  tests.test_biosmb_td3_training_fidelity -v
```

Compilation and all 20 hardware-free tests passed.

## Known limitations and next steps

- `active_control` already enables pump writes when the program runs.
- `online_training_enabled` is currently a setting only. The main loop does
  not yet calculate reward, push replay transitions, call `train_step()`, or
  save an updated online model.
- Therefore this intermediate version must not be run on the laboratory system
  until the full online-learning path and its safety checks are connected.
