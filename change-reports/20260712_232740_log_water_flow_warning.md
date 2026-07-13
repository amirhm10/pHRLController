# Log water-flow deviations without stopping BioSMB

## Objective

Treat imperfect measured water-pump readback as a warning instead of a process
shutdown, while continuing to require TD3 commands to request the trained fixed
water flow of 5.0 mL/min.

## Files changed

- `Biosmb-run-online/Biosmb-run-online/main.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/contracts.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/controller.py`

## Implementation summary

- Added separate validation behavior for commanded actions and measured pump
  readback.
- Kept fixed-water enforcement for actions before they are sent to BioSMB.
- Allowed TD3 state construction and measured-action reconstruction to continue
  when only the measured water flow differs from 5.0 mL/min.
- Added a non-blocking console warning when the absolute measured deviation is
  greater than 0.1 mL/min.
- Added a structured `water_flow_warning` object to every MongoDB deployment-step
  record. It contains the warning state, reason, measured value, fixed value,
  absolute deviation, and tolerance.
- Kept the existing physical pump bounds, buffer-flow bounds, total-flow limit,
  observation validation, and mass-safety shutdown behavior.

## Generated artifacts

No figures or result data were generated.

## Verification

The three edited Python files passed `py_compile` and `git diff --check`.

A focused test with the saved TD3 actor verified that:

- a measured water readback of 5.2 mL/min still constructs the five-element TD3
  state,
- the same 5.2 mL/min value remains invalid if treated as a commanded action,
- it is valid when treated as measured readback,
- the warning is active with a 0.2 mL/min deviation,
- the warning details are written into the MongoDB deployment record structure.

## Known limitations and next steps

- The warning does not mean all water values are accepted. Nonfinite values,
  values outside the existing 1-10 mL/min pump bounds, or actions violating the
  total-flow limit remain hard failures.
- Real pump data should be used to confirm whether 0.1 mL/min is an appropriate
  warning threshold.
- The complete live BioSMB, Redis, MongoDB, and OPC-UA loop was not run because
  those lab services are not available in this verification environment.
