# Add pH Read-Only Smoke Test And Plumbing Report

## Objective

Add a safe emulator-only smoke test and a clean pH plumbing report before any
full open-loop pH experiment. The goal is to verify the OPC interface, pH valve
labels, inlet mapping, and `PH_2` readout without writing pump or valve state.

## Files Changed

- `run_biosmb_ph_readonly_smoke_test.py`
- `analysis/render_biosmb_ph_plumbing_figure.py`
- `reports/biosmb_ph_plumbing_smoke_test_report.md`
- `change-reports/20260528_020900_add_ph_readonly_smoke_report.md`

No files under `BIOSMBControlLibrary/` were changed.

## Implementation Summary

- Added an emulator-only read-only smoke test.
- The smoke test starts the local OPC emulator, creates a temporary settings
  file, connects through `BioSMBManager`, and reads only:
  - pump flow readbacks for pumps 2, 3, and 4,
  - valve states for `P2`, `P3`, and `P4`,
  - outlet pH from `biosmb.get_ph(2)`,
  - full sensor keys needed for later logging.
- Added a generated valve-grid schematic showing columns `A` through `P`,
  rows `1` through `15`, pH inlet rows `2`, `3`, and `4`, and the expert-sketch
  valves `P2/P3/P4`.
- Added a report that explains the confirmed inlet and pH-measurement mapping,
  and separates it from the still-unverified physical outlet tubing path.

## Generated Artifacts

- `results/biosmb_ph_plumbing_map_20260528_020759/figures/biosmb_ph_plumbing_map.png`

The generated results folder is intentionally not staged because `results/` is
for timestamped local artifacts.

## Verification

```powershell
py -3.13 -m py_compile run_biosmb_ph_readonly_smoke_test.py analysis/render_biosmb_ph_plumbing_figure.py
```

Result: passed.

```powershell
py -3.13 analysis/render_biosmb_ph_plumbing_figure.py
```

Result: passed. The generated PNG size was `281115` bytes.

```powershell
py -3.13 run_biosmb_ph_readonly_smoke_test.py --port 4865
```

Result: passed. It printed pump 2/3/4 readbacks at zero flow, `P2/P3/P4` as
closed, and `PH_2 = get_ph(2) = 4.5000`.

```powershell
git diff --check
```

Result: passed.

```powershell
git diff --name-only -- BIOSMBControlLibrary
```

Result: no tracked BioSMB library files changed.

## Known Limitations And Next Steps

- This is not a hardware test. It only verifies the emulator interface and
  expected OPC labels.
- The physical outlet tubing after the `PH_2` measurement path remains
  unverified.
- The next safe step is a supervised valve-only or very low-flow hardware check
  with guaranteed cleanup before running the full step-test schedule.
