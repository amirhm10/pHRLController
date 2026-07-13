# Restore the successful offline TD3 500k defaults

## Objective

Make the offline pH TD3 runner default to the experiment definition used by the
selected successful 500000-step run, so the same settings can be launched
without command-line overrides.

## Files changed

- `run_offline_ph_td3_training.py`
  - changed the default rollout length from `100000` to `500000` steps.
- `tests/test_offline_ph_rl.py`
  - updated the default-setting regression assertion to `500000` steps.
- `reports/offline_ph_td3_method_report.md`
  - documented 500000 steps and 2500 default 200-step setpoint cycles.
- `Biosmb-run-online/Biosmb-run-online/custom_td3/README.md`
  - documented that the offline runner again defaults to the selected
    experiment settings.

## Method or implementation summary

The requested experiment defaults now resolve to:

- total rollout steps `500000`;
- actor hidden layers `[128, 128]`;
- critic hidden layers `[128, 128]`;
- discount factor `gamma = 0.97`;
- batch size `64`;
- final Gaussian exploration standard deviation `0.02`;
- checkpoint and deployment-bundle saving enabled.

Only the rollout-length default required a code change. The other requested
values were already active. No reward, TD3 update, plant, state, action, or
BioSMB deployment logic was changed.

## Generated artifacts

- This change report.
- No training run or result directory was generated.
- Verification bytecode was removed after testing.

## Verification commands and results

- Parsed `build_parser().parse_args([])` using
  `C:\Users\HAMEDI\miniconda3\envs\rl\python.exe` and confirmed all requested
  values plus automatic checkpoint saving.
- Compiled `run_offline_ph_td3_training.py` successfully.
- Ran `python -m pytest tests/test_offline_ph_rl.py -q -p no:cacheprovider`.
  Result: `23 passed in 7.65s`.
- Ran `git diff --check`. No whitespace errors were found.
- Searched the active runner, test, and documentation files for stale 100000-step
  default wording. No matches were found.

## Known limitations or next steps

- The 500000-step run is simulation-only and does not validate physical BioSMB
  performance.
- A new run can differ from an earlier run because TD3 optimization and the
  generated setpoint curriculum remain sensitive to experimental conditions.
- Review the new run's loss trace, last-25-setpoint tracking, evaluation MAE and
  RMSE, late-training drift, and frozen-policy behavior before replacing the
  selected shipment checkpoint.
- Running the offline script does not automatically replace files under
  `Biosmb-run-online/Biosmb-run-online/models`.
