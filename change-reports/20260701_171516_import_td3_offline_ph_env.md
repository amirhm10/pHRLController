# Import TD3 Core And Add Offline pH Environment

## Objective

Import the TD3 core from the local RL-assisted MPC repository and add an
offline Gymnasium-style pH environment for future simulation-only online
learning experiments.

This task intentionally does not add BioSMB, OPC emulator, valve, hardware,
MPC, or live controller code.

## Files Changed

- `TD3Agent/agent.py`
- `TD3Agent/actor.py`
- `TD3Agent/critic.py`
- `TD3Agent/replay_buffer.py`
- `TD3Agent/__init__.py`
- `utils/helpers_net.py`
- `utils/nstep.py`
- `utils/nstep_targets.py`
- `utils/sequence_sampling.py`
- `utils/__init__.py`
- `simulation/ph_environment.py`
- `tests/test_offline_ph_rl.py`
- `requirements.txt`
- `change-reports/20260701_171516_import_td3_offline_ph_env.md`

## Method And Implementation Summary

- Copied only the standard TD3 implementation and minimal utility dependencies
  from:

```text
C:\Users\HAMEDI\OneDrive - McMaster University\PythonProjects\RL_assisted_MPC
```

- Excluded MPC runners, Markov/residual/weight/horizon code,
  supervisor-gated variants, SAC, DQN, `BasicFunctions/td3_functions.py`, and
  generated artifacts.
- Added `PHEnvironment`, an offline Gymnasium-style environment whose action is
  a normalized direct command for acid, acetate, and water flows.
- Kept the chemistry core as the accepted ideal Henderson-Hasselbalch model:

$$ pH = pK_a + \log_{10}\left(\frac{C_A F_A}{C_H F_H}\right). $$

- Water is included in the action and observation for actuator compatibility,
  but it does not directly change the ideal Henderson-Hasselbalch pH when the
  acid and acetate stock concentrations are equal.
- The reward is a diagnostic simulation reward based on pH tracking error,
  flow movement, and distance from default flows. It is not a validated
  controller objective.

## Generated Artifacts

No timestamped results, figures, or lab-data artifacts were generated.

Python bytecode cache files were produced by the smoke test but are ignored by
git and were not staged.

## Verification Commands And Results

Compiled the new files with bytecode redirected to the temp directory to avoid
the existing OneDrive `__pycache__` permission issue:

```powershell
$env:PYTHONPYCACHEPREFIX = Join-Path $env:TEMP 'pHRL_pycache'
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -m py_compile simulation\ph_environment.py tests\test_offline_ph_rl.py TD3Agent\agent.py TD3Agent\actor.py TD3Agent\critic.py TD3Agent\replay_buffer.py utils\helpers_net.py utils\nstep.py utils\nstep_targets.py utils\sequence_sampling.py
Remove-Item Env:\PYTHONPYCACHEPREFIX
```

Result: passed.

Ran the direct smoke test:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' tests\test_offline_ph_rl.py
```

Result:

```text
offline pH RL smoke tests passed
```

Checked dependency availability in the `rl` environment:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -c "import importlib.util as u; mods=['torch','gymnasium','numpy','pandas','scipy','matplotlib']; print({m: bool(u.find_spec(m)) for m in mods})"
```

Result: all required packages were available.

## Known Limitations Or Next Steps

- The environment is static and ideal. It does not include delay, residence
  time, pH probe dynamics, calibration drift, BioSMB hardware, or MPC.
- The reward is only a starting simulation reward for smoke testing TD3.
- The existing unrelated worktree deletion of
  `Data/dsp_db.biosmb-rl-controller-treated-dataset.csv` was not touched or
  staged.
- Next step: add a small offline training runner only after deciding whether
  the pH task should use direct flow actions, ratio/scale actions, or a
  model-based allocator baseline.
