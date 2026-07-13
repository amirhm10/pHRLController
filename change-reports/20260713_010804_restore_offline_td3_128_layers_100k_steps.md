# Restore offline TD3 128-layer networks and 100k steps

## Objective

Change future offline pH TD3 runs to use `[128, 128]` actor and critic hidden
layers and reduce the default rollout length from 500000 to 100000 steps.

## Files changed

- `run_offline_ph_td3_training.py`
- `tests/test_offline_ph_rl.py`
- `reports/offline_ph_td3_method_report.md`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/README.md`
- `Biosmb-run-online/Biosmb-run-online/TD3_LAB_HANDOFF_REPORT.md`
- `change-reports/20260713_010804_restore_offline_td3_128_layers_100k_steps.md`

## Method and implementation summary

- Changed the default `--total-steps` value from `500_000` to `100_000`.
- Changed the default `--actor-hidden` and `--critic-hidden` values from
  `[64, 64]` to `[128, 128]`.
- Kept the previously approved defaults of `gamma = 0.99`, batch size `64`,
  and final exploration noise `0.02`.
- Updated the parser-default regression test.
- Updated current-default documentation without editing historical result
  descriptions or saved model configuration files.
- Documented that 100000 steps with a 200-step default setpoint hold produces
  500 setpoint cycles.

## Generated artifacts

- No training result, checkpoint, deployment bundle, or figure was generated.
- Existing model artifacts remain unchanged and still describe the run that
  produced them.

## Verification commands and results

- `python -m py_compile run_offline_ph_td3_training.py`
  - Passed.
- `python -m pytest tests/test_offline_ph_rl.py -q`
  - `23 passed`.
  - Pytest reported one non-test warning because it could not create its cache
    directory in the OneDrive workspace.
- Parsed the runner with no command-line overrides.
  - Confirmed `total_steps = 100000`.
  - Confirmed actor and critic layers `[128, 128]`.
  - Confirmed batch size `64`, `gamma = 0.99`, and final exploration noise
    `0.02`.
- `git diff --check`
  - Passed.

## Known limitations and next steps

- A training process that was already running before this edit keeps the
  arguments loaded at its startup. Stop and start a new run to use these
  defaults.
- The shorter training horizon reduces runtime by 80 percent but may alter
  final tracking quality. Compare the new frozen-policy evaluation sweep with
  the saved 500000-step baseline before replacing the BioSMB model files.
- After a successful new run, copy all four files from its
  `deployment_bundle` into the BioSMB `models` folder as one matched set.

