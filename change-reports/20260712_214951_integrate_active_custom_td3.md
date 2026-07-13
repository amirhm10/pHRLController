# Integrate the active custom TD3 path into BioSMB

## Objective

Replace the historical Stable-Baselines3 SAC model artifacts with the latest
custom TD3 artifacts, connect the verified frozen actor through minimal main
call-site changes, retain only currently active TD3 training components, and
configure future online exploration to continue from 0.02 to 0.01.

## Files changed

- `Biosmb-run-online/Biosmb-run-online/main.py`
- `Biosmb-run-online/Biosmb-run-online/.gitignore`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/`
- `Biosmb-run-online/Biosmb-run-online/models/`
- `tests/test_biosmb_additive_td3.py`
- `tests/test_biosmb_td3_training_fidelity.py`
- `reports/biosmb_custom_td3_active_path_report.md`
- `reports/biosmb_additive_td3_module_report.md`
- `reports/biosmb_online_td3_integration_roadmap.md`

## Implementation summary

- Removed the two historical SAC files from the online models directory.
- Copied the latest actor manifest, actor weights, training checkpoint, and
  immutable offline configuration.
- Added a separate online configuration with Gaussian exploration 0.02 to 0.01.
- Changed only the policy-specific seams in main and marked each area with the
  requested `# I changed this line:` reason comment.
- Forced `suggest_only` because the manifest is simulation-only.
- Tightened the total controlled flow safety limit from 30 to 25 mL/min to
  match a maximum 20 mL/min buffer sum plus fixed 5 mL/min water.
- Added the active one-step TD3 actor, twin critics, update, mixed replay,
  Gaussian exploration, and active pH reward.
- Excluded n-step, lambda returns, sequence sampling, parameter noise,
  behavioral cloning, hard targets, alternative losses, and inactive rewards.

## Generated artifacts

- `models/td3_actor_manifest.json`
- `models/td3_actor_weights.pt`
- `models/td3_training_checkpoint.pkl`
- `models/td3_training_config.json`
- `models/td3_online_training_config.json`
- `models/README.md`

## Verification

Python compilation passed with the available base interpreter.

The following command passed 20 hardware-free tests with PyTorch 2.8.0:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m unittest `
  tests.test_biosmb_additive_td3 `
  tests.test_biosmb_td3_training_fidelity -v
```

The tests include frozen actor parity, training-checkpoint actor parity, action
mapping, reward parity, four-step active update parity, model artifact identity,
noise schedule endpoints, and inactive-feature exclusion.

The documented preferred `rl-env` interpreter did not exist on this machine.
The available `C:\Users\HAMEDI\miniconda3\envs\rl\python.exe` interpreter was
used instead.

## Known limitations and next steps

- Online updates and exploratory actions are deliberately disabled.
- The research checkpoint is not a full replay, optimizer, counter, target,
  and RNG resume checkpoint.
- The saved actor remains simulation-only and not laboratory validated.
- Pump mapping and real PH_2 dynamics remain unresolved.
- The next step is reviewed transition collection in `suggest_only`, not
  immediate calls to `train_step()`.
