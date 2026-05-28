# BioSMB pH Plumbing Smoke-Test Report

## Objective

This report records the current pH plumbing interpretation before running a
full open-loop step-test experiment. The immediate goal is not control. The
goal is to verify the BioSMB OPC interface, pH-relevant valve labels, inlet
names, and reliable pH readout in a safe emulator-only smoke test.

The intended pH measurement for modeling is:

$$
y(t) = PH_2(t)
$$

In the BioSMB Python API, this is read as:

```python
current_ph = biosmb.get_ph(2)
```

## Source Evidence

The pH setup interpretation comes from three local sources:

- `BIOSMBControlLibrary/5_21_2026_demo.py` opens `P2`, `P3`, and `P4`, then
  reads `biosmb.get_ph(2)`.
- `BIOSMBControlLibrary/Presentation.pptx` visibly identifies the three pH
  streams as acetic acid, sodium acetate, and water. The visible `2` extracted
  from the slide XML is a slide-number placeholder, not an outlet label.
- The BioSMB valve grid is addressed by column letter and row number. Columns
  run left-to-right from `A` through `P`, so `P2`, `P3`, and `P4` are the
  far-right `P` column on rows 2, 3, and 4.

## Confirmed Working Interpretation

For the current pH setup:

| Item | Interpretation |
| --- | --- |
| Pump 1 | Do not use, reported not working |
| Pump 2 | Acetic acid inlet |
| Pump 3 | Sodium acetate inlet |
| Pump 4 | Arium water inlet |
| `P2` | Valve at column `P`, row 2, aligned with acetic acid row |
| `P3` | Valve at column `P`, row 3, aligned with sodium acetate row |
| `P4` | Valve at column `P`, row 4, aligned with water row |
| `PH_2` | Reliable outlet pH measurement |
| `PH_1` | Diagnostic only, not a validation output |

The physical outlet tubing after the routed pH measurement path is still not
fully confirmed. Scripts should therefore log the open valve labels and keep an
explicit outlet-path verification flag until that route is checked on hardware.

## Clean Valve Schematic

The following generated schematic reproduces the useful information from the
PowerPoint figure in a cleaner, labeled form.

![BioSMB pH plumbing map](../results/biosmb_ph_plumbing_map_20260528_020759/figures/biosmb_ph_plumbing_map.png)

The key point is that the expert sketch's `P2`, `P3`, and `P4` are valve
coordinates, not pump numbers. They indicate column `P` on the three pH inlet
rows.

## Read-Only Smoke Test

The new smoke-test script is:

```powershell
py -3.13 run_biosmb_ph_readonly_smoke_test.py
```

It is intentionally emulator-only and read-only from the BioSMB manager side.
It does not call:

```python
biosmb.enable_pump(...)
biosmb.set_flow(...)
biosmb.open_valve(...)
```

The root script is intentionally written in the same simple style as the expert
demo: create a `BioSMBManager`, read the pH-related flows, read `P2/P3/P4`,
read `biosmb.get_ph(2)`, print, and exit. The local emulator startup and
temporary settings-file setup are hidden in `helpers/biosmb_emulator.py` so that
the demonstration script remains easy to read. That helper imports and runs the
existing emulator but does not modify any file under `BIOSMBControlLibrary/`.

Instead, it verifies that:

- the local OPC emulator starts,
- a temporary emulator `settings.json` mapping can be created,
- `BioSMBManager` can connect to the emulator,
- the pH valve labels `P2`, `P3`, and `P4` resolve,
- pump-flow readbacks for pumps 2, 3, and 4 are readable,
- `PH_2` can be read using `biosmb.get_ph(2)`,
- the full sensor dictionary contains the keys needed for later logging.

Expected output includes:

```text
Pump readbacks
pump 2: acetic acid
pump 3: sodium acetate
pump 4: Arium water
P2: closed
P3: closed
P4: closed
current pH from PH_2: 4.5000
Read-only emulator smoke test complete.
```

## What This Does Not Prove

This smoke test does not prove that the real hardware route is safe, clean, or
physically connected exactly as expected. It only proves that the emulator
interface can resolve and read the pH-relevant OPC nodes without issuing any
pump or valve writes.

Before a hardware test, the operator should still confirm:

- the physical tubing for pumps 2, 3, and 4,
- the physical meaning of the `P2/P3/P4` valve path,
- the downstream outlet tubing after the `PH_2` measurement location,
- that pump 1 remains unavailable and should not be used,
- that `PH_2` is connected and calibrated.

## Next Step

After this read-only smoke test passes, the next safe script should be a
supervised valve-only or very low-flow hardware check with guaranteed cleanup.
Only after that should the full open-loop step-test schedule be run.
