# Replace SAC import with custom TD3 policy import

## Objective

Perform only the first reviewed `main.py` integration step by replacing the
Stable-Baselines3 SAC import with the additive custom TD3 policy facade.

## Files Changed

- `Biosmb-run-online/Biosmb-run-online/main.py`
- `tests/test_biosmb_additive_td3.py`
- `reports/biosmb_additive_td3_module_report.md`
- `change-reports/20260712_211901_replace_sac_import.md`

## Implementation Summary

The only change inside `main.py` is:

```python
from custom_td3 import BioSMBTD3Policy
```

replacing:

```python
from stable_baselines3 import SAC
```

Redis, MongoDB, OPC-UA, and `BioSMBManager` imports were not changed. No other
main-file line was changed.

The existing `SAC.load(...)` calls remain temporarily and will be replaced in
the next separate review step. Therefore this import-only intermediate state is
not yet a complete runnable TD3 integration.

## Verification

```powershell
git diff --unified=0 -- Biosmb-run-online/Biosmb-run-online/main.py
```

Result: exactly one removed import line and one added import line.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m py_compile `
  Biosmb-run-online/Biosmb-run-online/main.py `
  tests/test_biosmb_additive_td3.py
```

Result: passed.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' `
  -m unittest tests.test_biosmb_additive_td3 -v
```

Result: 9 tests passed.

## Known Limitations Or Next Steps

- `load_trained_model()` still calls `SAC.load(...)` and is the next policy
  seam to edit.
- No state, action, BioSMB, safety, database, or container logic changed.
