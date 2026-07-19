# Add BioSMB target scheduling and frozen action modes

## Objective

Add user-selectable fixed and scheduled pH targets to the BioSMB online runner,
allow the custom TD3 actor to run without online learning in deterministic or
small Gaussian-noise mode, preserve the existing lab-facing communication and
safety functions, and restore the previously working extended dependency list.

## Files changed

- `Biosmb-run-online/Biosmb-run-online/main.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/runtime_modes.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/__init__.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/README.md`
- `Biosmb-run-online/Biosmb-run-online/models/README.md`
- `Biosmb-run-online/Biosmb-run-online/requirements.txt`
- `Biosmb-run-online/Biosmb-run-online/dockerfile`
- `Biosmb-run-online/Biosmb-run-online/TD3_LAB_HANDOFF_REPORT.md`
- `tests/test_biosmb_runtime_modes.py`
- `tests/test_biosmb_additive_td3.py`
- `change-reports/20260719_113040_biosmb_runtime_modes.md`

## Method and implementation summary

The configuration block in `main.py` now exposes:

- `target_ph_mode = "fixed"`, with `"scheduled"` and `"redis"` alternatives
- fixed target pH
- scheduled minimum and maximum pH
- scheduled setpoint count
- maximum completed steps per target
- required consecutive in-tolerance steps
- pH tolerance
- `online_training_enabled`
- deterministic or Gaussian frozen-action mode
- frozen Gaussian standard deviation and seed

The default remains `active_control`, but online learning is disabled and the
frozen actor is deterministic. Every changed logical area in `main.py` is marked
with the existing `# I changed this line:` explanation style.

The pure `ScheduledSetpointManager` generates evenly spaced targets and visits
them in ping-pong order. After each completed 60-second controller interval, it
changes target when either the maximum hold length is reached or the configured
number of consecutive `PH_2` measurements is inside tolerance. A miss resets
the consecutive counter. Warm-up and one-second safety observations do not
increment the schedule.

For a transition generated under target `target_ph`, reward continues to use
that target. If the schedule changes after the measurement, `next_state` uses
`next_target_ph`, and the following controller action uses the same value. This
keeps the stored TD3 transition consistent with the state seen at the next
decision.

When online training is disabled, the online trainer is not loaded. Frozen
deterministic and frozen Gaussian modes therefore do not store replay, perform
gradient updates, or save online checkpoints. Frozen Gaussian noise is added in
normalized actor coordinates, clipped to `[-1, 1]`, seeded once per run, and
logged together with clean, sampled, unclipped, and selected actions.

Startup now validates target mode, action mode, the `suggest_only` and online
training combination, configured target values against the deployed actor
manifest, and frozen-noise settings.

The 46-line `requirements.txt` is exactly equal to the earlier working content
from commit `d5e17e5`. Because that list pins Torch `2.11.0`, the Dockerfile no
longer preinstalls a separate Torch `2.8.0`. It installs the restored environment
once and retains `pip check`.

The BioSMB data collection, OPC and MFCS calls, Redis observation use, MongoDB
connections, pump mapping, action-to-flow conversion, command validation, mass
safety checks, and shutdown implementation were not changed.

## Generated artifacts

- New pure runtime helper
- New hardware-free runtime-mode test suite
- Updated lab handoff and package documentation
- This change report

No model weights, training checkpoints, online checkpoints, lab data, figures,
or result folders were created or modified.

## Verification commands and results

Python compilation:

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile `
  Biosmb-run-online/Biosmb-run-online/main.py `
  Biosmb-run-online/Biosmb-run-online/custom_td3/runtime_modes.py `
  Biosmb-run-online/Biosmb-run-online/custom_td3/__init__.py `
  tests/test_biosmb_runtime_modes.py `
  tests/test_biosmb_additive_td3.py
```

Result: passed.

Runtime-mode and TD3 fidelity tests:

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m pytest `
  -p no:cacheprovider `
  tests/test_biosmb_runtime_modes.py `
  tests/test_biosmb_td3_training_fidelity.py -q
```

Result: `24 passed in 2.10s`.

The tests cover target generation, ping-pong order, exact maximum-step changes,
consecutive-step changes, counter reset, simultaneous trigger reporting,
manifest target bounds, deterministic actions, seeded Gaussian actions,
normalized clipping, default mode selection, correct old-target reward and
new-target next-state use, and rejection of online training in `suggest_only`.

Historical requirements comparison:

```powershell
$reqPath = 'Biosmb-run-online/Biosmb-run-online/requirements.txt'
$oldReq = git show "d5e17e5:$reqPath"
$newReq = Get-Content -LiteralPath $reqPath
Compare-Object -ReferenceObject $oldReq -DifferenceObject $newReq
```

Result: no differences, 46 lines.

`git diff --check` passed. Its only output was the repository's existing
LF-to-CRLF warning behavior.

## Known limitations and next steps

- The current `rl-env` does not contain Gymnasium or Redis. The existing
  additive suite could not collect because Gymnasium is missing, and a direct
  `main.py` import could not run because Redis is missing. Both packages are in
  the restored extended requirements.
- The restored extended requirements were not installed during this task.
- Docker is not available on this development computer. The image was not built
  and the restored environment has not passed an in-container `pip check`.
- The restored environment pins Torch `2.11.0` and NumPy `2.4.4`, while the
  selected actor export records Torch `2.8.0` and NumPy `2.3.1`. The container
  must pass the actor golden cases before lab use.
- No live OPC UA, Redis, MongoDB, MFCS, sensor, or pump test was performed.
- The frozen Gaussian standard deviation is in normalized actor coordinates and
  has not been demonstrated safe on the physical system.
- Commissioning should proceed through fixed deterministic suggest-only review,
  supervised fixed deterministic active control, scheduled deterministic
  control, separately authorized frozen noise, and finally separately
  authorized online learning.
