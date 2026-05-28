# Add One-Pump Step-Test Block

## Objective

Refine the open-loop pH identification plan to include the proposed simple
step-test pattern where all three flows start at `3 mL/min` and each pump is
stepped individually to `6 mL/min`.

## Files changed

- `reports/open_loop_ph_step_test_identification_plan.md`
- `change-reports/20260528_012036_add_one_pump_step_test_block.md`

## Method or implementation summary

- Added `Block 0: One-Pump-At-A-Time Local Steps`.
- Defined the baseline vector \(u_0 = [3, 3, 3]\ \mathrm{mL/min}\).
- Added a return-to-baseline sequence for acid, acetate, and water positive
  steps.
- Explained that this block is good for local empirical input-output
  identification, but each single-pump step also changes total flow, so it does
  not fully separate chemistry from residence-time effects.
- Added a compact local dynamic model structure using
  \(G_H(q^{-1})\), \(G_A(q^{-1})\), and \(G_W(q^{-1})\).

## Generated artifacts

- No figures or result tables were generated.

## Verification commands and results

```powershell
git diff --check -- reports/open_loop_ph_step_test_identification_plan.md
```

Result: passed.

```powershell
Select-String -Path reports/open_loop_ph_step_test_identification_plan.md -Pattern ';'
```

Result: no semicolons found.

## Known limitations or next steps

- This is still a planning report, not a runnable hardware schedule.
- The next step is to turn the proposed blocks into a reviewed schedule file
  before writing the hardware-facing runner.
