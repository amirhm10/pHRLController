# Add BioSMB TD3 lab handoff report

## Objective

Create a standalone report inside the BioSMB run-online folder that explains
the custom TD3 changes to `main.py`, why they were made, what BioSMB behavior
was preserved, and what the lab team must verify before active use.

## Files changed

- `Biosmb-run-online/Biosmb-run-online/TD3_LAB_HANDOFF_REPORT.md`
- `change-reports/20260713_004832_add_biosmb_td3_lab_handoff_report.md`

## Method and implementation summary

- Reviewed the current BioSMB `main.py`, custom TD3 state/action contracts,
  online trainer, active reward, model files, Docker files, dependencies, and
  prior reference-comparison evidence.
- Documented the retained Redis, MongoDB, OPC UA, MFCS, `BioSMBManager`, pump
  command, mass-safety, and shutdown paths.
- Documented the custom five-value state, two-value TD3 action, physical flow
  mapping, exploration schedule, reward, replay buffer, online updates,
  logging, and checkpoints.
- Clearly separated the currently bundled `[128, 128]`, `gamma = 0.97` model
  from the incoming `[64, 64]`, `gamma = 0.99` offline model.
- Added verification evidence, known operational risks, a staged commissioning
  procedure, and a lab sign-off checklist.
- Documented that `suggest_only` commissioning must disable online training so
  an unapplied suggestion is not stored as a real process transition.

## Generated artifacts

- A shareable Markdown handoff report in the root of the run-online folder.
- No figures, data tables, or temporary test artifacts were generated because
  this task documents software integration rather than a new experiment.

## Verification commands and results

- `git diff --check -- Biosmb-run-online/Biosmb-run-online/TD3_LAB_HANDOFF_REPORT.md`
  - Passed with no whitespace errors.
- Checked every relative file and directory link used by the report with
  PowerShell `Test-Path`.
  - All referenced local paths exist.
- Reviewed the rendered Markdown source, equations, configuration values, model
  status, safety behavior, and stated limitations against the current code.
- No test suite was rerun because this work changes documentation only. The
  report cites the previously completed relevant result of `47 passed` and the
  focused BioSMB result of `24 passed`.

## Known limitations and next steps

- The replacement offline model is still training and has not been copied into
  the run-online `models` folder.
- Docker could not be built on the development computer because Docker was not
  available.
- Live Redis, MongoDB, OPC UA, MFCS, and pump behavior remains untested locally.
- Update the report's model-status section after the new four-file deployment
  set is installed and verified.
