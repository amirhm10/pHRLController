# Restore BioSMB reference and add TD3 modules separately

## Objective

Undo the large replacement of the supplied BioSMB online application, restore
the original reference files, leave `main.py` without custom TD3 integration,
and add a self-contained custom TD3 package that can be imported later through
small policy-specific changes.

## Files Changed

### Original files restored

- `Biosmb-run-online/Biosmb-run-online/main.py`
- `Biosmb-run-online/Biosmb-run-online/dockerfile`
- `Biosmb-run-online/Biosmb-run-online/docker-compose.yml`
- `Biosmb-run-online/Biosmb-run-online/settings.json`
- `Biosmb-run-online/Biosmb-run-online/biosmb_interface/manager.py`
- `Biosmb-run-online/Biosmb-run-online/biosmb_interface/utility.py`
- `Biosmb-run-online/Biosmb-run-online/requirements.txt`

### Additive package added

- `Biosmb-run-online/Biosmb-run-online/custom_td3/__init__.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/actor.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/contracts.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/policy.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/controller.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/README.md`
- `tests/test_biosmb_additive_td3.py`

### Previous replacement files removed

- root `.dockerignore` created for the replaced root-context container
- `deployment_settings.json`
- `requirements-runtime.txt`
- monolithic `td3_deployment.py`
- TD3 example files under the original `models/` directory
- `tests/test_biosmb_td3_deployment.py`

### Reports

- Added `reports/biosmb_additive_td3_module_report.md`.
- Marked `reports/biosmb_custom_td3_implementation_walkthrough.md` as a
  superseded historical implementation.
- Updated the online `.gitignore` so the original requirements file is tracked
  while local model binaries remain ignored.

## Implementation Summary

- Used the Desktop BioSMB folder as the original source of truth.
- Verified the six restored file contents match the Desktop versions after
  normalizing line endings and final blank lines.
- Left the original Stable-Baselines3 SAC import, main loop, BioSMB manager,
  Dockerfile, and Compose service unchanged.
- Added an actor-only PyTorch network with layer names compatible with the
  offline training actor.
- Added strict manifest, SHA-256, state-dictionary, and golden-vector loading.
- Added the exact five-element TD3 state builder and two-action ratio/sum mapper.
- Added an inverse mapping from physical flows to the previous normalized TD3
  actions.
- Added `BioSMBTD3Policy`, a pure compatibility facade that has no hardware or
  database imports.
- Made `predict()` return `(action, None)` like the existing SAC call.
- Made `format_action()` return the original BioSMB action-dictionary schema.

## Latest Saved Model Inspected

```text
results/offline_ph_td3_training_20260710_183129/
```

Safe deployment artifacts:

```text
deployment_bundle/td3_actor_manifest.json
deployment_bundle/td3_actor_weights.pt
```

Actor weight SHA-256:

```text
0c10ce7b8602bd5c455f74009e233ecc990735a3f73c76b2c99a196d23f91777
```

The training `.pkl` was not opened. The manifest records a simulation-only,
not-lab-validated actor, so it was used only for loader verification.

## Generated Artifacts

Synthetic test bundles were written under the ignored path:

```text
results/_test_biosmb_additive_td3/
```

No actor files were copied into the online `models/` directory. That remains a
later deployment/containerization step.

## Verification Commands And Results

### Compilation

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m py_compile `
  Biosmb-run-online/Biosmb-run-online/main.py `
  Biosmb-run-online/Biosmb-run-online/custom_td3/__init__.py `
  Biosmb-run-online/Biosmb-run-online/custom_td3/actor.py `
  Biosmb-run-online/Biosmb-run-online/custom_td3/contracts.py `
  Biosmb-run-online/Biosmb-run-online/custom_td3/policy.py `
  Biosmb-run-online/Biosmb-run-online/custom_td3/controller.py `
  tests/test_biosmb_additive_td3.py
```

Result: passed.

### Additive TD3 tests

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' `
  -m unittest tests.test_biosmb_additive_td3 -v
```

Result: 9 tests passed.

The tests cover:

- original main and Docker entrypoint restoration
- absence of a custom TD3 import in `main.py`
- self-contained package imports
- training-actor versus exported-actor prediction parity
- exact state construction
- 49-point action-mapping parity with the training environment
- original action-dictionary compatibility
- default 5/5/5 flow representation
- hash-mismatch rejection
- safe loading of the real saved 500000-step actor

## Known Limitations Or Next Steps

- The original main file intentionally retains its existing configuration and
  safety limitations.
- The restored original main file contains a plaintext database credential.
  Nothing was pushed, and the credential should be moved to an environment
  variable and rotated before this folder is shared or pushed.
- No physical pump, MFCS, or outlet mapping is asserted by the additive package.
- The latest actor is suitable only for software and future shadow testing.
- Main integration is deliberately postponed. It should touch only model load,
  default action, state building, and action formatting.
- The original container can include the new package through `COPY . .`, but
  model mounting/copying and container-level policy validation remain to be done.
