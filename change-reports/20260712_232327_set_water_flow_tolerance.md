# Set BioSMB water-flow tolerance to 0.1 mL/min

## Objective

Allow measured water-flow readback to differ from the fixed TD3 training value
of 5.0 mL/min by at most 0.1 mL/min, while keeping the existing BioSMB safety
and fallback structure unchanged.

## Files changed

- `Biosmb-run-online/Biosmb-run-online/main.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/contracts.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/controller.py`

## Implementation summary

- Changed `water_flow_tolerance` in `main.py` to `0.1`.
- Passed the main deployment setting into `BioSMBTD3Policy.load`.
- Applied the same tolerance during TD3 state construction and measured-flow
  conversion.
- Kept generated TD3 actions fixed at exactly 5.0 mL/min water.
- Logged the tolerance with the other controller settings in MongoDB deployment
  records.
- Added validation that the supplied tolerance is finite and nonnegative.

## Generated artifacts

No figures or result data were generated.

## Verification

The following compile check passed:

```powershell
python -m py_compile "Biosmb-run-online/Biosmb-run-online/main.py" "Biosmb-run-online/Biosmb-run-online/custom_td3/contracts.py" "Biosmb-run-online/Biosmb-run-online/custom_td3/controller.py"
```

A focused test using the `rl` environment and the saved TD3 actor passed:

- Water flow `5.1` mL/min was accepted.
- Water flow `5.1001` mL/min was rejected.
- TD3 state construction still returned the expected five-element state.

`git diff --check` also passed.

## Known limitations and next steps

- The complete `main.py` deployment import was not executed because the local
  `rl` environment does not currently contain the `redis` package.
- The 0.1 mL/min value is an engineering tolerance selected for deployment. It
  should later be checked against real pump readback noise and calibration data.
- This change does not relax acid-flow, acetate-flow, total-flow, or mass-safety
  checks.
