# Data Integrity Checklist

## Structure

- [ ] File exists and can be decoded
- [ ] Schema or keys are documented
- [ ] Arrays have expected shape and dtype
- [ ] Time dimension is identified
- [ ] Episode or batch boundaries are identified
- [ ] No silent broadcasting changed a calculation

## Alignment

- [ ] State \(s_k\) aligns with action \(a_k\)
- [ ] Reward \(r_k\) aligns with the intended transition
- [ ] Next state \(s_{k+1}\) is correct
- [ ] Setpoints and disturbances use the same clock
- [ ] Controller source and fallback flags align with executed actions
- [ ] Training and evaluation trajectories are not mixed

## Coordinates and units

- [ ] Physical versus scaled values are identified
- [ ] Scaling artifacts match the run
- [ ] Units are recorded
- [ ] Delta inputs are distinguished from absolute inputs
- [ ] Log-transformed or normalized targets are identified

## Missing and invalid data

- [ ] NaNs and infinities counted
- [ ] Missing episodes recorded
- [ ] Early termination reason recorded
- [ ] Outliers inspected rather than automatically deleted
- [ ] Exclusion rules are declared before comparison

## Recalculation

Recompute at least one important metric or reward component from raw signals. If the stored and recomputed values disagree, stop interpretation until the mismatch is resolved.
