# Simplify pH Read-Only Smoke Demo

## Objective

Make the pH read-only smoke-test entrypoint look like the expert demo script:
short, readable, and focused only on the BioSMB operations being checked.

## Files Changed

- `run_biosmb_ph_readonly_smoke_test.py`
- `helpers/biosmb_emulator.py`
- `reports/biosmb_ph_plumbing_smoke_test_report.md`
- `change-reports/20260528_021422_simplify_ph_readonly_smoke_demo.md`

No files under `BIOSMBControlLibrary/` were changed.

## Implementation Summary

- Moved the local emulator startup, temporary settings file, and stable fake
  sensor writes into `helpers/biosmb_emulator.py`.
- Rewrote the root smoke-test script as a small demo-style file:
  - define inlet labels,
  - create `BioSMBManager` through the helper context,
  - read pump 2/3/4 flow readbacks,
  - read `P2/P3/P4` valve states,
  - read `biosmb.get_ph(2)`,
  - print sensor keys and exit.
- Updated the plumbing report to clarify that the root script is intentionally
  simple and that the helper uses the existing emulator without modifying the
  BioSMB library.

## Generated Artifacts

None.

## Verification

```powershell
py -3.13 -m py_compile run_biosmb_ph_readonly_smoke_test.py helpers/biosmb_emulator.py
```

Result: passed.

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

- This remains emulator-only. It is not a real hardware test.
- The helper hides the emulator setup so the script stays easy to read.
- For a demo file that is literally only a `Client(...)` block, an emulator or
  hardware OPC server would need to be started separately with a compatible
  settings file.
