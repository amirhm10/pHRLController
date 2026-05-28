# Open-Loop Step-Test Identification Plan

## Objective

Create a new planning report for a supervised open-loop pH step-test experiment
that can identify an input-output model from acid, acetate, and water flows to
`PH_2`.

## Files changed

- `reports/open_loop_ph_step_test_identification_plan.md`
- `change-reports/20260528_011044_open_loop_step_test_identification_plan.md`

## Method or implementation summary

- Inspected the BioSMB familiarization report, equilibrium main-model report,
  dynamic model identification report, lab-data helper, process configuration,
  BioSMB manager API, and existing result tables.
- Added a new report defining the experiment stage, variable names, pump bounds,
  step-test blocks, logging schema, identification equations, simulation model
  requirements, post-experiment analysis workflow, decision criteria, and total
  implementation plan.
- Kept the plan in open-loop identification mode. No MPC, RL, reward, policy,
  or autonomous feedback-control logic was added.

## Generated artifacts

- No figures or model outputs were generated.
- New report: `reports/open_loop_ph_step_test_identification_plan.md`

## Verification commands and results

```powershell
git diff --check -- reports/open_loop_ph_step_test_identification_plan.md
```

Result: passed.

```powershell
$reportPath = 'reports/open_loop_ph_step_test_identification_plan.md'
$base = Split-Path $reportPath
$text = Get-Content -Raw $reportPath
$matches = [regex]::Matches($text, '\[[^\]]+\]\(([^\)]+)\)')
```

Result: all `7` local links resolve.

## Known limitations or next steps

- This report is an experiment-design and modeling plan, not a runnable
  hardware script.
- The next implementation step is to create a reviewed step schedule and a
  dry-run capable `run_open_loop_ph_identification_experiment.py` script with
  explicit valve path, flow bounds, structured logging, and guaranteed cleanup.
