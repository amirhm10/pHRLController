# Add BioSMB pH Emulator Step Test

## Objective

Check whether the BioSMB demo and quick-test scripts are runnable, then add an
emulator-safe pH step-test simulation without modifying `BIOSMBControlLibrary/`.

## Files changed

- `simulation/ph_emulator_process.py`
- `run_biosmb_ph_emulator_step_test.py`
- `change-reports/20260528_013154_add_biosmb_ph_emulator_step_test.md`

## Method or implementation summary

- Inspected `BIOSMBControlLibrary/quick_test.py`,
  `BIOSMBControlLibrary/demo_script.py`, `BIOSMBControlLibrary/5_21_2026_demo.py`,
  `BIOSMBControlLibrary/opc_emulator/run_opc_emulator.py`,
  `BIOSMBControlLibrary/opc_emulator/biosmb_opc_emulator.py`, and
  `BIOSMBControlLibrary/settings.json`.
- Verified that the scripts compile, but do not run directly in the project
  Conda interpreter because that interpreter is Python 3.14 and `asyncua`
  fails during secure-channel serialization.
- Installed and tested `asyncua` with local Python 3.13, where the local OPC
  emulator and `BioSMBManager` smoke test succeeded.
- Added `PHEmulatorProcess`, a small pH model that combines equilibrium
  charge-balance chemistry, the current affine `PH_2` calibration, and a
  first-order sensor response.
- Added `run_biosmb_ph_emulator_step_test.py`, a root runner that starts the
  existing BioSMB OPC emulator class, generates a temporary emulator settings
  map for the runtime namespace, drives a one-pump-at-a-time step schedule
  through `BioSMBManager`, and logs command flows, readback flows, sensors,
  `PH_2`, and chemistry predictions.
- Did not edit any file under `BIOSMBControlLibrary/`.

## Generated artifacts

Short verification run:

- `results/biosmb_ph_emulator_step_test_20260528_013115/tables/emulator_step_test_log.csv`

The result folder is under ignored `results/` output.

## Verification commands and results

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile BIOSMBControlLibrary/quick_test.py BIOSMBControlLibrary/demo_script.py BIOSMBControlLibrary/5_21_2026_demo.py BIOSMBControlLibrary/opc_emulator/run_opc_emulator.py BIOSMBControlLibrary/opc_emulator/biosmb_opc_emulator.py BIOSMBControlLibrary/biosmb_interface/manager.py
```

Result: passed.

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -c "import asyncua"
```

Initial result: failed because `asyncua` was not installed. After installing
and upgrading `asyncua`, OPC connection still failed under Python 3.14 with
`TypeError: issubclass() arg 1 must be a class`.

```powershell
py -3.13 -m py_compile simulation/ph_emulator_process.py run_biosmb_ph_emulator_step_test.py
```

Result: passed.

```powershell
py -3.13 run_biosmb_ph_emulator_step_test.py --port 4861 --hold-s 1.5 --sample-s 0.5 --server-sample-s 0.2
```

Result: completed and wrote `21` log rows. Command/readback flows matched, and
`PH_2` moved according to the emulator pH model.

## Known limitations or next steps

- Use Python 3.13 for the OPC emulator runner in this workspace. The preferred
  Conda environment currently uses Python 3.14, where `asyncua` fails before
  connecting.
- The existing `quick_test.py` points at the real BioSMB endpoint and should
  not be run casually.
- The existing `demo_script.py` targets localhost, but the default
  `settings.json` does not match the emulator node ids and namespace.
- The new runner is an emulator/simulation aid only. It is not a hardware
  experiment runner and not a feedback controller.
