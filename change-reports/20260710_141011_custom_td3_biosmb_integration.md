# Custom TD3 BioSMB integration

## Objective

Replace the Stable-Baselines3 SAC policy path in the imported BioSMB online reference with the repository's custom TD3 actor, add a safe actor export/load contract, keep deployment shadow-first, and document the complete implementation for joint review.

## Files changed

- `.dockerignore`
- `helpers/td3_deployment_export.py`
- `run_offline_ph_td3_training.py`
- `tests/test_biosmb_td3_deployment.py`
- `Biosmb-run-online/Biosmb-run-online/.gitignore`
- `Biosmb-run-online/Biosmb-run-online/main.py`
- `Biosmb-run-online/Biosmb-run-online/td3_deployment.py`
- `Biosmb-run-online/Biosmb-run-online/deployment_settings.json`
- `Biosmb-run-online/Biosmb-run-online/requirements-runtime.txt`
- `Biosmb-run-online/Biosmb-run-online/dockerfile`
- `Biosmb-run-online/Biosmb-run-online/docker-compose.yml`
- `Biosmb-run-online/Biosmb-run-online/models/README.md`
- `Biosmb-run-online/Biosmb-run-online/models/td3_actor_manifest.example.json`
- imported BioSMB interface/settings files required by the online runtime
- `reports/biosmb_custom_td3_implementation_walkthrough.md`

## Implementation summary

- Added actor-only TD3 export with CPU tensors, SHA-256, semantic state/action schema, measured/target pH bounds, physical action mapping, provenance, and golden vectors.
- Wired `--save-checkpoint` in the offline training runner to create both a research checkpoint and a deployment bundle for two-action ratio/sum TD3.
- Replaced the online SAC path with deterministic custom TD3 inference.
- Reproduced the training environment's exact ratio/sum action mapping and inverse state reconstruction.
- Made `PH_2` the only controller pH input.
- Separated logical streams from candidate physical pump numbers 2/3/4.
- Added finite observation, action, flow, inventory, deadline, slew, readback, and shutdown checks.
- Made `suggest_only` the default and tested that one complete mocked step makes zero hardware writes.
- Gated active mode with physical verification, exclusive ownership, verified readback semantics, dynamic/frozen-policy evidence, pinned manifest SHA-256, finite steps, and nonpersistent arming.
- Added SIGTERM cleanup and a zero/disable/readback shutdown receipt.
- Added a non-root, actor-only Docker layout with separate explicit shadow/active profiles.

## Generated artifacts

Hardware-free verification artifacts were generated under ignored paths:

- `results/_test_biosmb_td3_deployment/`
- `results/_verify_td3_export_final/`

The four-step smoke-run bundle is test data only and is not a deployable controller.

## Verification commands and results

### Compilation

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m py_compile `
  helpers/td3_deployment_export.py `
  run_offline_ph_td3_training.py `
  Biosmb-run-online/Biosmb-run-online/td3_deployment.py `
  Biosmb-run-online/Biosmb-run-online/main.py `
  Biosmb-run-online/Biosmb-run-online/biosmb_interface/*.py `
  tests/test_biosmb_td3_deployment.py
```

Result: passed.

### New contract/safety tests

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' `
  -m unittest tests.test_biosmb_td3_deployment -v
```

Result: 16 tests passed.

### Existing offline pH RL tests

Pytest was not installed in the available environment, so the 21 plain zero-argument test functions in `tests/test_offline_ph_rl.py` were imported and invoked directly.

Result: 21 tests passed.

### End-to-end training/export smoke test

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' `
  run_offline_ph_td3_training.py `
  --total-steps 4 `
  --n-tests 2 `
  --set-points-len 2 `
  --setpoint-range-source reachable `
  --save-checkpoint `
  --output-dir results/_verify_td3_export_final
```

Result: research checkpoint, actor weights, manifest, golden cases, figures, and tables were generated successfully.

### Policy-only online validation

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' `
  Biosmb-run-online/Biosmb-run-online/main.py `
  --config Biosmb-run-online/Biosmb-run-online/deployment_settings.json `
  --manifest results/_verify_td3_export_final/deployment_bundle/td3_actor_manifest.json `
  --validate-policy-only
```

Result: manifest, hash, architecture, semantics, weights, and golden inference checks passed with no network connection.

### Other checks

- Three committed JSON files parsed successfully.
- CLI help loaded without laboratory communication dependencies.
- No Stable-Baselines3/Gymnasium package appears in effective runtime requirements.
- Docker was not available on this workstation, so image build and container policy-only validation were not run.
- Ruff was not installed; compilation and the focused test suites were used instead.

## Known limitations and next steps

- The prior 500,000-step actor cannot be recovered because checkpoint saving was disabled.
- A four-step smoke actor is not a policy candidate.
- Active control remains scientifically blocked by use of an ideal static training plant instead of validated lab delay/mixing/sensor dynamics.
- The deployment slew rule is not yet represented in training and frozen evaluation.
- Redis target freshness, dwell, and target-step rules remain to be implemented.
- OPC `FLOW`, pump numbers, MFCS channels, exclusive pump ownership, and the outlet path require physical verification.
- A local audit write-ahead log and a hardware emulator/fault-injection suite remain recommended before active trials.
- Build and validate the Docker image on the intended deployment host.
