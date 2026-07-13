# Set online TD3 recent replay window to 200

## Objective

Reduce the BioSMB online TD3 recent-sampling window from 1000 to 200
transitions so the recent portion of each replay batch represents a useful lab
time horizon.

## Files changed

- `Biosmb-run-online/Biosmb-run-online/models/td3_online_training_config.json`
- `tests/test_biosmb_td3_training_fidelity.py`
- `Biosmb-run-online/Biosmb-run-online/models/README.md`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/README.md`
- `Biosmb-run-online/Biosmb-run-online/TD3_LAB_HANDOFF_REPORT.md`
- `change-reports/20260713_011426_set_online_td3_recent_window_200.md`

## Method and implementation summary

- Changed only the online configuration's `replay.recent_window` from `1000`
  to `200`.
- Kept the generic and offline replay-buffer default at `1000` to preserve the
  previously verified offline implementation.
- Kept replay capacity `10000`, batch size `64`, and the sampling mixture of
  50 percent prioritized, 20 percent recent, and 30 percent uniform.
- Added tests that verify the JSON value and the value received by the loaded
  online trainer.
- Updated the model, custom TD3, and lab handoff documentation.

## Generated artifacts

- No training result, model checkpoint, replay checkpoint, or figure was
  generated.

## Verification commands and results

- Parsed `td3_online_training_config.json` with Python JSON loading.
  - Confirmed recent window `200`, batch size `64`, and capacity `10000`.
- `python -m pytest tests/test_biosmb_td3_training_fidelity.py -q -p no:cacheprovider`
  - `13 passed`.
- `git diff --check`
  - Passed.
- Confirmed the tests left no temporary online-config or checkpoint files in
  `results/`.

## Known limitations and next steps

- The sampling behavior is unchanged until more than 200 transitions exist.
- At a 60-second decision interval, 200 transitions represent about 3 hours 20
  minutes. Shorter sessions use every available transition as the recent pool.
- Each batch of 64 contains 32 prioritized, 12 recent, and 20 uniform samples
  because the implementation converts requested fractions to integer counts.
- Lab data are not yet available to determine whether 200 is optimal. Monitor
  tracking error, critic loss, action saturation, and performance drift during
  supervised online operation.

