# Make pH Smoke Test Self-Contained Emulator Style

## Objective

Make `run_biosmb_ph_readonly_smoke_test.py` look like the expert demo script:
direct imports from the actual BioSMB library, no project helper import, local
emulator use, and only read-only BioSMB manager calls.

## Files Changed

- `run_biosmb_ph_readonly_smoke_test.py`
- `analysis/render_biosmb_ph_plumbing_figure.py`
- `reports/biosmb_ph_plumbing_smoke_test_report.md`
- `helpers/biosmb_emulator.py`
- `change-reports/20260528_022022_make_ph_smoke_direct_library.md`

No files under `BIOSMBControlLibrary/` were changed.

## Implementation Summary

- Rewrote the smoke-test script to import directly from:
  - `asyncua.sync.Client`
  - `biosmb_interface.manager.BioSMBManager`
- `biosmb_opc_emulator.BioSMBOPCEmulator`
- Removed the helper-based emulator startup from the smoke-test entrypoint and
  put the minimal emulator startup directly in the script.
- Deleted `helpers/biosmb_emulator.py`, since the user asked for no helper
  import in the simple file.
- Kept the smoke test read-only:
  - `get_all_flows()`
  - `get_valve("P2")`, `get_valve("P3")`, `get_valve("P4")`
  - `get_ph(2)`
  - `get_all_sensors()`
- Improved the generated plumbing schematic with a cleaner panel, highlighted
  pH inlet rows, highlighted `P` column, stream labels, and clearer PH_2 callout.
- Updated the report to describe the script as a self-contained local emulator
  smoke test that imports from the actual BioSMB library and emulator package.

## Generated Artifacts

- `results/biosmb_ph_plumbing_map_20260528_021943/figures/biosmb_ph_plumbing_map.png`

The generated result is intentionally not staged because `results/` contains
timestamped local artifacts.

## Verification

```powershell
py -3.13 -m py_compile run_biosmb_ph_readonly_smoke_test.py analysis/render_biosmb_ph_plumbing_figure.py
```

Result: passed.

```powershell
py -3.13 analysis/render_biosmb_ph_plumbing_figure.py
```

Result: passed and generated the updated plumbing figure. The PNG size was
`399836` bytes.

```powershell
py -3.13 run_biosmb_ph_readonly_smoke_test.py
```

Result: passed. It printed zero-flow readbacks for pumps 2, 3, and 4,
`P2/P3/P4` as closed, and `current pH from PH_2: 4.5000`.

```powershell
git diff --check
```

Result: passed, with only LF-to-CRLF working-copy warnings.

```powershell
git diff --name-only -- BIOSMBControlLibrary
```

Result: no tracked BioSMB library files changed.

## Known Limitations And Next Steps

- The script starts the local emulator and reads through `BioSMBManager`, but it
  still does not issue pump enables, flow writes, or valve-open commands.
- The physical outlet tubing after the `PH_2` measurement path remains
  unverified before write-enabled hardware checks.
