# Review BioSMB TD3 Integration And Add Roadmap

## Objective

Perform a read-only review of the added `Biosmb-interact` and
`Biosmb-run-online` code, compare their interfaces with the current pH TD3
method, and create an evidence-backed implementation and deployment roadmap.

This task intentionally did not implement controller logic, modify hardware
code, load a model into a runtime, or issue any BioSMB command.

## Files Changed

- `reports/biosmb_online_td3_integration_roadmap.md`
- `change-reports/20260709_173322_biosmb_td3_integration_roadmap.md`

The added `Biosmb-interact/` and `Biosmb-run-online/` directories were reviewed
but not modified or staged. Existing unrelated worktree deletions were also
left untouched.

## Method And Review Summary

- Inspected all source, configuration, dependency, and container files in both
  added BioSMB directories.
- Inspected the supplied SAC checkpoint as a ZIP archive without deserializing
  or executing it.
- Reconstructed the existing SAC state/action contract and the current TD3
  state/action contract mathematically.
- Compared online acquisition, target handling, safety checks, command writes,
  timing, lifecycle, logging, and container behavior with the project
  conventions for `PH_2`, acid, acetate, and water.
- Reviewed the TD3 environment, agent, runner, reports, and both the 200000-step
  and completed 500000-step result artifacts.
- Confirmed that the completed 500000-step result saved no checkpoint, used a
  single deterministic evaluation target, had evaluation MAE 0.02477 pH, mean
  action saturation 15.23 percent, and maximum one-step buffer-pump changes of
  9 mL/min.
- Identified critical blockers, including the invalid online control-mode
  string, physical pump-mapping conflict, silent five-dimensional state
  semantic mismatch, incompatible action definitions, missing deployable TD3
  artifact, and missing validated dynamic plant.
- Defined a staged architecture with read-only acquisition, a frozen actor,
  exact action mapping, independent safety supervision, single command
  ownership, readback verification, and a fault-latched finite state machine.
- Defined phased gates from physical commissioning and dynamic identification
  through shadow mode, operator-approved actions, and guarded closed-loop
  sessions.
- Connected the roadmap to the original TD3 paper, the standard fixed-dataset
  definition of offline RL, and the runtime-assurance architecture pattern.

## Generated Artifacts

- `reports/biosmb_online_td3_integration_roadmap.md`

No figures, result tables, model files, raw data, or hardware logs were created
or changed.

## Verification Commands And Results

Checked all local Markdown links in the new report:

```powershell
python -c "from pathlib import Path; import re; p=Path(r'reports/biosmb_online_td3_integration_roadmap.md'); s=p.read_text(encoding='utf-8'); links=re.findall(r'\[[^\]]*\]\(([^)]+)\)',s); missing=[]; base=p.parent; [(missing.append(x) if not (base/x.split('#')[0]).resolve().exists() else None) for x in links if not re.match(r'^[a-z]+://',x)]; print(missing)"
```

Result: all 21 local links resolved.

Checked the new report for unexpected control characters:

```powershell
python -c "from pathlib import Path; s=Path(r'reports/biosmb_online_td3_integration_roadmap.md').read_text(encoding='utf-8'); print([(i,ord(c)) for i,c in enumerate(s) if ord(c)<32 and c not in '\n\t\r'])"
```

Result: no unexpected control characters were found.

Recomputed the final 500000-step TD3 evaluation tail from the saved trajectory:

```powershell
& 'C:\Users\HAMEDI\miniconda3\envs\rl\python.exe' -c "import pandas as pd; p=r'results\offline_ph_td3_training_20260709_030431\tables\trajectory.csv'; d=pd.read_csv(p); e=d[d['is_test']]; print(e.tail(50).ph_error.abs().mean(), (e.ph_error.abs()<=0.02).mean())"
```

Result: tail-50 MAE `0.0246843 pH` and fraction inside `0.02 pH` equal to
`0.0`.

Final repository checks are recorded in the task handoff after the report and
change report are staged.

## Known Limitations And Next Steps

- This is a static code and artifact review. No live endpoint was contacted.
- The physical pump, valve, outlet, MFCS mass, pressure, and fallback mappings
  remain operator-confirmation blockers.
- The current method and result-analysis reports predate the completed
  500000-step run and should be updated in a separate work item.
- The next experiment remains the supervised open-loop dynamic identification
  experiment, not active RL control.
- The roadmap's numerical policy gates are proposed promotion criteria. Final
  active-control limits must be approved from laboratory dynamics, sensor
  repeatability, process requirements, and hardware safety evidence.
