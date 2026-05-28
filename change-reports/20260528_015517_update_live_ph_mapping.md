# Update Live pH Mapping

## Objective

Update the pH step-test runner and planning notes so the live experiment uses
the current expert/operator mapping: pump 1 is not used, pumps 2, 3, and 4 are
the acetic acid, sodium acetate, and Arium water inlets, and the outlet pH
measurement is read from `biosmb.get_ph(2)` / `PH_2`.

## Files Changed

- `run_biosmb_ph_emulator_step_test.py`
- `reports/open_loop_ph_step_test_identification_plan.md`
- `reports/biosmb_control_library_familiarization.md`
- `change-reports/20260528_015517_update_live_ph_mapping.md`

No files under `BIOSMBControlLibrary/` were changed.

## Implementation Summary

- Changed the emulator step-test runner defaults to use pump 2 for acetic acid,
  pump 3 for sodium acetate, and pump 4 for Arium water.
- Added metadata fields for pump numbers, inlet row labels, open valves,
  outlet path verification, outlet pH sensor number/name, and `ph_measured`.
- Logged `ph_measured` from `get_ph(2)` while still logging the full sensor
  snapshot including `PH_1` and `PH_2`.
- Set the default valve sketch to `P2 P3 P4`, matching the expert pH demo file.
- Added validation for BioSMB valve labels (`A1` through `P15`) and documented
  that columns run left-to-right from `A` through `P`, so `P2/P3/P4` are the
  far-right `P` column on stream rows 2, 3, and 4.
- Updated the reports to separate confirmed output measurement (`PH_2`) from
  the still-unverified physical outlet valve/tubing route.

## Generated Artifacts

- `results/biosmb_ph_emulator_step_test_20260528_015747/tables/emulator_step_test_log.csv`

The generated results folder is intentionally not staged because `results/` is
for timestamped run artifacts.

## Verification

```powershell
py -3.13 -m py_compile simulation/ph_emulator_process.py run_biosmb_ph_emulator_step_test.py
```

Result: passed.

```powershell
git diff --check
```

Result: passed, with only existing LF-to-CRLF working-copy warnings.

```powershell
py -3.13 run_biosmb_ph_emulator_step_test.py --port 4864 --hold-s 1.0 --sample-s 0.5 --server-sample-s 0.2
```

Result: passed. The CSV confirmed `acid_pump_number = 2`,
`acetate_pump_number = 3`, `water_pump_number = 4`,
`valve_path_id = p_column_rows_2_3_4_outlet_path_unverified`,
`open_valves = P2 P3 P4`, `outlet_ph_sensor_name = PH_2`, and
`ph_measured = PH_2`.

```powershell
git diff --name-only -- BIOSMBControlLibrary
```

Result: no tracked BioSMB library files changed.

## Known Limitations And Next Steps

- The physical outlet valve/tubing route is still not confirmed. The runner
  therefore logs `outlet_path_verified = False`.
- `conda` was not available on the active PowerShell PATH, so verification used
  `py -3.13`, which is the Python version that successfully ran `asyncua` for
  this emulator workflow.
- Before any real hardware run, the operator should confirm the valve path and
  endpoint, then run a short supervised dry run with the same pump and sensor
  metadata.
