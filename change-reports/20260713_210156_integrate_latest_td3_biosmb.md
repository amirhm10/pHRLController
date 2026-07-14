# Integrate the latest ratio-preserving TD3 model into BioSMB online control

## Objective

Install the requested latest offline TD3 checkpoint in `Biosmb-run-online`,
make the online action and reward paths exactly compatible with the refined
ratio-preserving algorithm, and preserve the existing lab-facing BioSMB
communication and pump-control code.

## Files changed

- `run_offline_ph_td3_training.py`
- `helpers/td3_deployment_export.py`
- `Biosmb-run-online/Biosmb-run-online/main.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/agent.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/contracts.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/online_training.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/reward.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/README.md`
- `Biosmb-run-online/Biosmb-run-online/models/README.md`
- `Biosmb-run-online/Biosmb-run-online/models/td3_actor_manifest.json`
- `Biosmb-run-online/Biosmb-run-online/models/td3_actor_weights.pt`
- `Biosmb-run-online/Biosmb-run-online/models/td3_training_checkpoint.pkl`
- `Biosmb-run-online/Biosmb-run-online/models/td3_training_config.json`
- `Biosmb-run-online/Biosmb-run-online/models/td3_online_training_config.json`
- `Biosmb-run-online/Biosmb-run-online/TD3_LAB_HANDOFF_REPORT.md`
- `tests/test_biosmb_additive_td3.py`
- `tests/test_biosmb_td3_training_fidelity.py`

## Method and implementation summary

The selected source is
`results/offline_ph_td3_training_20260713_204554`, trained for 500000 steps
with `[64, 64]` actor and critic layers, `gamma = 0.99`, batch size 64, and the
`ratio_preserving_flow` action mode.

The two actor outputs now have the same meaning offline and online:

1. choose the global log-scaled acetate/acid ratio;
2. calculate the physical total-flow interval feasible at that ratio; and
3. choose an optional-flow fraction within that interval.

The online reward now includes the offline economic-flow term
`0.01 * optional_flow_fraction**2`, in addition to the existing pH tracking,
total-flow movement, and near-target terms. The only new `main.py` behavior is
passing this executed optional-flow fraction to the online trainer. It is marked
with the requested `# I changed this line:` comment.

The Redis, MongoDB, OPC UA, `BioSMBManager`, pump application, observation,
mass safety, water warning, and shutdown paths were not changed in this task.

Future refined offline runs now export a four-file `deployment_bundle`
automatically when `ratio_preserving_flow` is selected.

## Generated artifacts

The source run contains the generated matched bundle:

`results/offline_ph_td3_training_20260713_204554/deployment_bundle/`

The same four matched model files were copied into the BioSMB `models` folder.
Verified SHA-256 values are:

- actor manifest: `070179921655aed8939933ceb582432faf734114e7c6752b3e7eaac14e37bb75`
- actor weights: `687131b5578750103f6dfe93731009c1eb7ab49e792db9f1e0dcd531662c0a88`
- training checkpoint: `b2298ab8120ccaa190109d386baa4ed297342d0954aeb2577baca6443bee73ae`
- training config: `c61f15870bc0aad197a8962571b8e4f97a8cd50f3424082f8aba22ec3789e594`

Disposable test-result folders were removed after verification.

## Verification commands and results

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m py_compile `
  run_offline_ph_td3_training.py `
  helpers/td3_deployment_export.py `
  Biosmb-run-online/Biosmb-run-online/main.py `
  Biosmb-run-online/Biosmb-run-online/custom_td3/agent.py `
  Biosmb-run-online/Biosmb-run-online/custom_td3/contracts.py `
  Biosmb-run-online/Biosmb-run-online/custom_td3/online_training.py `
  Biosmb-run-online/Biosmb-run-online/custom_td3/reward.py
```

Result: passed.

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m pytest `
  -p no:cacheprovider `
  tests/test_offline_ph_rl.py `
  tests/test_biosmb_additive_td3.py `
  tests/test_biosmb_td3_training_fidelity.py -q
```

Result: `50 passed in 4.83s`.

`git diff --check` passed. Docker Compose validation could not be rerun because
Docker is not installed on this development computer.

## Known limitations and next steps

- The installed model is simulation-trained and has not controlled the live
  BioSMB system.
- The newest checkpoint's frozen 25-target grid has pH MAE `0.011105`, maximum
  absolute error `0.032116`, and mean buffer flow `10.184659 mL/min`.
- The preceding `20260713_191125` checkpoint was better on the same grid: MAE
  `0.005471`, maximum absolute error `0.017666`, and mean buffer flow
  `5.015525 mL/min`. The newest model was installed because it was explicitly
  selected, not because it won this comparison.
- The model was created and locally tested with Python 3.13.7; the Docker image
  uses Python 3.11. A container build and model-only startup preflight remain
  required on a Docker-capable computer.
- The first lab run should be supervised and should verify pump mapping,
  measured flow readback, safety shutdown, MongoDB reward logging, and online
  checkpoint creation before extended operation.
