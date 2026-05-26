# BioSMB Report Equilibrium Model Rewrite

## Objective

Rewrite the BioSMB control-library familiarization report so the pH experiment
workflow uses the equilibrium charge-balance model as the main chemistry core,
not the ideal Henderson-Hasselbalch model.

## Files Changed

- `reports/biosmb_control_library_familiarization.md`
- `change-reports/20260525_221324_biosmb_equilibrium_model_rewrite.md`

## Summary

- Added the current model framing:

  ```text
  equilibrium charge balance + empirical PH_2 calibration
  ```

- Added links to:
  - `simulation/equilibrium_charge_balance_model.py`
  - `reports/equilibrium_charge_balance_main_model_report.md`

- Added the exact current CSV/BioSMB mapping:
  - `observation.biosmb-flows[0]` as acetic acid,
  - `observation.biosmb-flows[1]` as sodium acetate,
  - `observation.biosmb-flows[2]` as Arium water,
  - `observation.biosmb-sensors.PH_2` as the reliable outlet pH.

- Rewrote the mathematical experiment section around:
  - mixed analytical concentrations,
  - total buffer concentration,
  - sodium charge,
  - acetate equilibrium,
  - water self-ionization,
  - charge-balance root solve,
  - affine `PH_2` calibration.

- Updated the safe experiment and next-engineering-step sections to log
  `pH_eq` and calibrated equilibrium predictions in addition to flows and
  sensor values.

## Verification

Markdown link audit:

```text
Checked 13 Markdown links.
All Markdown links exist.
```

Whitespace check:

```powershell
git -c safe.directory=C:/Users/hamed/Desktop/pHRLController diff --check -- reports/biosmb_control_library_familiarization.md
```

Result: passed.

## Known Limitations

- This change updates the project report and experiment guidance.
- It does not modify the low-level hardware wrapper because `BioSMBManager`
  should remain a direct OPC-UA interface.
- No hardware-facing scripts were run.
