# Activate BioSMB online TD3 training

## Objective

Connect the existing custom TD3 learning components to the BioSMB deployment
loop so completed laboratory transitions can use active exploration, the exact
offline shaped reward, a 10000-transition replay buffer, batch size 64, online
actor/critic updates, detailed logging, and complete checkpoint saving.

## Files changed

- `Biosmb-run-online/Biosmb-run-online/main.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/online_training.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/agent.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/replay_buffer.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/__init__.py`
- `Biosmb-run-online/Biosmb-run-online/custom_td3/README.md`
- `Biosmb-run-online/Biosmb-run-online/models/td3_online_training_config.json`
- `Biosmb-run-online/Biosmb-run-online/models/README.md`
- `tests/test_biosmb_td3_training_fidelity.py`
- `tests/test_biosmb_additive_td3.py`
- `reports/biosmb_custom_td3_active_path_report.md`
- `reports/biosmb_online_td3_integration_roadmap.md`

## Implementation summary

- Added `BioSMBOnlineTD3Trainer` as the small connection between `main.py` and
  the existing custom TD3 agent, reward, and replay code.
- Verified at startup that the training-checkpoint actor matches the deployed
  actor on all saved golden cases.
- Continued Gaussian action exploration from standard deviation 0.02 to 0.01
  over 5000 online actions.
- Set batch size to 64 and replay capacity to 10000.
- Kept the existing mixed replay composition of 50 percent prioritized, 20
  percent recent, and 30 percent uniform samples.
- Requested one TD3 gradient update per completed control transition after the
  replay buffer reaches 64 samples.
- Used `custom_td3/reward.py::compute_ph_reward`, which is the copied active
  `relative_band_offset` shaped reward from the latest offline run.
- Computed reward from the target, measured `PH_2` after the hold interval, the
  action actually executed, the previous validated command, and the commanded
  buffer-flow movement.
- Stored the exact logged reward in replay to prevent training/logging mismatch.
- Logged the scalar reward, full reward breakdown, exploration noise, replay
  size, batch size, actor/critic losses, update counters, and checkpoint status.
- Kept the last validated command as the fallback instead of converting an
  imperfect measured readback into a future pump command.
- Added complete online-resume checkpoints containing actor, critics, target
  networks, optimizers, replay contents, counters, and random states.
- Saved periodically every 10 completed control transitions and again at
  controlled program exit.

## Mathematical method

For each completed transition, the loop stores

```text
(state, executed normalized action, shaped reward, next state, done=False)
```

The active reward is the existing relative-band-offset reward with nonzero pH
tracking, absolute-error, normalized buffer-sum movement, and near-setpoint
bonus terms. The one-step TD3 target remains

```text
reward + gamma * (1 - done) * min(target_Q1, target_Q2)
```

with gamma 0.97, delayed actor updates, target-policy smoothing standard
deviation 0.2, smoothing clip 0.5, and soft-update coefficient 0.005.

## Generated artifacts

No laboratory result data or figures were generated. Temporary test
checkpoints were removed automatically.

## Verification

The following checks passed:

- Python compilation of the edited main and custom TD3 modules.
- JSON parsing and direct confirmation of batch size 64, replay capacity 10000,
  one update per transition, and a 10-transition checkpoint interval.
- Training-checkpoint actor parity with the deployed actor.
- A focused 64-transition online test that produced a finite shaped reward and
  completed the first critic and delayed actor update.
- Complete checkpoint save and restoration of replay, optimizer state,
  counters, and random state.
- Deployment-log construction with the same reward used for training.
- `git diff --check`.
- All 23 BioSMB TD3 unit tests:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m unittest tests.test_biosmb_td3_training_fidelity tests.test_biosmb_additive_td3 -v
```

Result: `Ran 23 tests ... OK`.

## Known limitations and next steps

- The starting actor remains simulation-trained and not laboratory validated.
- With a 60-second decision interval and an empty replay buffer, the first
  online update occurs after approximately 64 completed minutes of control.
- The live BioSMB, Redis, MongoDB, MFCS, and OPC-UA services were not connected
  during verification.
- The existing Docker restart policy, model-volume behavior, target validation,
  physical pump mapping, and meaning of the BioSMB `FLOW` readback still require
  review before unattended operation.
- Online checkpoint files use Python pickle and must only be loaded from trusted
  local storage.
