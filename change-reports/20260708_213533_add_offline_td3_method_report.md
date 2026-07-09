# Add offline pH TD3 method report

## Objective

Start a comprehensive offline pH TD3 method report that documents the current simulation environment, manipulated inputs and outputs, RL state/action definitions, TD3 agent architecture, reward function, and fixed parameters.

## Files changed

- `reports/offline_ph_td3_method_report.md`

## Method or implementation summary

- Added a new report rather than overwriting the existing result-analysis report.
- Documented the ideal Henderson-Hasselbalch environment used by `simulation/ph_environment.py`.
- Defined the physical pump variables and clarified that the active RL action is one normalized acid/acetate ratio action.
- Documented the observation vector:

  ```text
  [current_ph, target_ph, current_ph - target_ph, normalized_ratio_action, step_fraction]
  ```

- Documented the TD3 actor and critic network dimensions:
  - actor: `5 -> 64 -> 64 -> 1`
  - twin critic branches: `6 -> 64 -> 64 -> 1`
- Documented the current runner defaults for rollout length, exploration, replay buffer, optimizer, TD3 target updates, and setpoint scheduling.
- Wrote the current `relative_band_offset` reward mathematically and tabulated its parameters.
- Tabulated fixed process and environment parameters, including the distinction between the process-config `default_buffer_flow_sum = 10.0` and the current runner `fixed_buffer_flow_sum = 15.0`.

## Generated artifacts

- `reports/offline_ph_td3_method_report.md`

No figures or raw data files were generated or edited.

## Verification commands and results

```powershell
git diff --check -- reports/offline_ph_td3_method_report.md
```

Result: no whitespace errors were reported. Because the report file was new and unstaged at the time, `git diff` had no content output.

```powershell
(Get-Content reports\offline_ph_td3_method_report.md).Count
```

Result: `609` lines.

## Known limitations or next steps

- This is the first method-focused draft only.
- It does not yet include plots from a full 100000-step run.
- The next report additions should include generated figures, per-setpoint average rewards, last-five-setpoint tracking, and frozen-policy evaluation over the reachable pH range.
