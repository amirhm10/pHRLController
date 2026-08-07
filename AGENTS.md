# AGENTS.md

## Project

This repository is the working codebase for the pH modeling project. The current process is an inline acetate buffer mixing system using:

- acetic acid, 100 mM
- sodium acetate, 100 mM
- Arium ultrapure water

The three inlet flows are currently treated as pump flowrates in mL/min. The immediate objective is to build and validate first-principles models that predict the reliable measured outlet pH, `PH_2`, from the inlet flows.

## Current scope

The project is in first-principles modeling and lab-data validation mode.

Do not add MPC, RL, feedback control, reward functions, policies, or controller logic yet. Static chemistry models have already shown important mismatch against lab data, and the next safe direction is dynamic model identification.

Current modeling conclusion:

- The lab CSV should be treated as dynamic time-series data, not purely steady-state data.
- Steady-state chemistry models are baselines only.
- The next model should add calibration, explicit delay, mixing/residence-time dynamics, and pH sensor response before any controller work.

## Scientific conventions

- `acid_flow` means acetic acid flowrate.
- `acetate_flow` means sodium acetate flowrate.
- `water_flow` means Arium water flowrate.
- Current stock concentrations are 100 mM for both acetic acid and sodium acetate.
- Current nominal pump bounds are 1-10 mL/min for all three streams.
- Expected useful acetate-buffer pH range is about 3.76-5.76.
- Water changes dilution, buffer strength, total flowrate, residence time, delay, and measurement sensitivity.
- Water should not directly change the ideal Henderson-Hasselbalch ratio when acid and acetate stock concentrations are equal.

Lab CSV mapping:

- `observation.biosmb-sensors.PH_2` is the only reliable pH measurement.
- `observation.biosmb-sensors.PH_1` was disconnected and must not be used for metrics.
- `observation.biosmb-flows[0]` is acetic acid.
- `observation.biosmb-flows[1]` is sodium acetate.
- `observation.biosmb-flows[2]` is Arium water.
- Do not use `target_ph` for model-validation metrics unless explicitly studying controller behavior.
- Preprocessing flags low-information flat-pH trials by default and excludes them from `valid_for_model` when `PH_2` is nearly flat while the acid/acetate chemistry input changes strongly. The current rule is at least 5 trial samples, `trial_ph_range <= 0.05`, and `trial_log10_flow_ratio_range >= 0.5`.

## Repository layout

```text
simulation/                 pH process model classes
helpers/                    data loading, validation, metrics, and plotting utilities
analysis/                   reusable analysis/report export scripts
reports/                    project reports and first-report context
change-reports/             per-task change reports
Data/                       lab data files, raw files must not be edited
results/                    timestamped generated figures and tables, ignored by git
run_initial_simulation.py   initial target-sweep simulation runner
run_first_principles_data_comparison.py
run_equilibrium_charge_balance_data_comparison.py
requirements.txt            Python dependencies
CODEX_CONTEXT.md            extra project context for Codex
```

## Research and Engineering Skill Routing

Skills supplement, but do not replace, this file. Repository-specific instructions in `AGENTS.md` and verified repository files override generic skill assumptions. This repository does not use `.agents/project-profiles/`; derive paths, variables, units, environments, and execution restrictions from this file and verified repository content.

When the user explicitly names a skill, read its `SKILL.md` completely and follow it. When a task clearly matches a skill description, invoke that skill automatically. Use the smallest sufficient set, normally one to three skills at a time; do not load or invoke every skill for every task. Use `research-result-loop` as the compatibility entrypoint for broad, multidisciplinary research-result analysis, and `research-orchestrator` when a task spans several disciplines or has several plausible failure mechanisms. For focused work, invoke the relevant specialist directly.

| Task or trigger | Skill path |
|---|---|
| Broad multidisciplinary result analysis (compatibility entrypoint) | `.agents/skills/research-result-loop/SKILL.md` |
| Cross-disciplinary planning, failure-mechanism triage, and synthesis | `.agents/skills/research-orchestrator/SKILL.md` |
| Literature, citations, source verification, and state of the art | `.agents/skills/literature-evidence-research/SKILL.md` |
| Experiment design, data integrity, metrics, uncertainty, and comparisons | `.agents/skills/experiment-and-statistics/SKILL.md` |
| Mathematical derivation, proofs, assumptions, conditioning, and verification | `.agents/skills/mathematical-reasoning-verification/SKILL.md` |
| Optimization objectives, variables, constraints, feasibility, and formulation | `.agents/skills/optimization-modeling/SKILL.md` |
| Solver selection, scaling, derivatives, initialization, infeasibility, and status | `.agents/skills/solver-engineering/SKILL.md` |
| Machine learning, including PCA, PLS, deep networks, soft sensors, and OOD behavior | `.agents/skills/machine-learning-research/SKILL.md` |
| Reinforcement learning, environment semantics, rewards, replay, and evaluation | `.agents/skills/reinforcement-learning-research/SKILL.md` |
| System identification, observers, MPC, target selection, and closed-loop analysis | `.agents/skills/control-mpc-research/SKILL.md` |
| Safe learning, executed-action analysis, Lyapunov/barrier methods, and certification claims | `.agents/skills/safe-learning-certification/SKILL.md` |
| Material/energy balances, units, thermodynamics, transport, and process plausibility | `.agents/skills/chemical-engineering-foundations/SKILL.md` |
| Aspen Plus/Dynamics/polymer cases, mappings, convergence, and safe automation | `.agents/skills/aspen-process-simulation/SKILL.md` |
| Distillation, VLE, MESH equations, stages, hydraulics, and column dynamics | `.agents/skills/distillation-separations/SKILL.md` |
| CSTRs, kinetics, reactor balances, multiplicity, stiffness, and reaction engineering | `.agents/skills/reaction-engineering-cstr/SKILL.md` |
| Polymerization kinetics, moments, molecular properties, rheology, and grade transitions | `.agents/skills/polymerization-process-engineering/SKILL.md` |
| pH, aqueous equilibria, buffers, electrolytes, mixing, and sensor behavior | `.agents/skills/ph-aqueous-systems/SKILL.md` |
| Process hazards, operating envelopes, abnormal scenarios, safeguards, and operability | `.agents/skills/process-safety-operability/SKILL.md` |
| Scientific Python architecture, interfaces, configuration, notebooks, and maintainability | `.agents/skills/scientific-software-engineering/SKILL.md` |
| Scientific and numerical unit, invariant, integration, simulator, ML, and RL tests | `.agents/skills/scientific-software-testing/SKILL.md` |
| Reports, figures, tables, citations, provenance, and reproducibility | `.agents/skills/research-reporting-reproducibility/SKILL.md` |

Sequence related skills only when needed: validate provenance and metrics before interpreting results; formulate optimization problems before solver tuning; pair ML, RL, or control analysis with the relevant physical-domain specialist when process physics is causal; and use reporting after the evidence-owning specialist has validated the conclusions. Skill activation does not authorize out-of-scope controller work, notebook rewrites, Aspen execution, regeneration or overwriting of artifacts, environment changes, commits, or modification of user-owned files; preserve all corresponding rules below.

## Current models and runners

Core configuration:

- `simulation/config.py`
  - Central defaults for `pKa`, `Kw`, stock concentrations, pump bounds, default water flow, default buffer-flow sum, and target clipping.

Current model-validation models:

- `simulation/henderson_hasselbalch_model.py`
  - Generic Henderson-Hasselbalch model.
  - Relation: `pH = pKa + log10((base_stock * base_flow) / (acid_stock * acid_flow))`.

- `simulation/equilibrium_charge_balance_model.py`
  - Generic acetate equilibrium charge-balance model.
  - Solves `f(H) = H + C_Na - C_T Ka / (Ka + H) - Kw / H = 0`, then `pH = -log10(H)`.

Legacy-compatible models:

- `simulation/simple_buffer_model.py`
  - Older Henderson-Hasselbalch model with target-pH-to-flow allocation.
  - Keep for `run_initial_simulation.py` and historical reports.

- `simulation/equilibrium_buffer_model.py`
  - Older charge-balance model used by the initial simulation workflow.
  - Keep for backward compatibility.

Current runners:

- `run_first_principles_data_comparison.py`
  - Runs Henderson-Hasselbalch lab validation against `PH_2`.

- `run_equilibrium_charge_balance_data_comparison.py`
  - Runs equilibrium charge-balance lab validation against `PH_2`.

- `run_initial_simulation.py`
  - Runs the original target-pH sweep and saves timestamped results.

## Standard modeling workflow

Use this pattern for new modeling work:

1. Put model logic in `simulation/`.
2. Put lab-data loading and preprocessing in `helpers/lab_data.py` or a focused helper.
3. Put model-specific prediction, residual, metric, affine-diagnostic, and lag-scan logic in `helpers/`.
4. Put model-specific plotting in `helpers/`.
5. Keep root runner files as orchestration only.
6. Save tables and figures under timestamped `results/<method>_<YYYYMMDD_HHMMSS>/` folders.
7. Stamp figures with method name and run time.
8. Write reports that explain objective, equations, step-by-step method, figures, observations, conclusions, and next actions.

Expected validation artifacts for each model:

```text
results/<method>_<YYYYMMDD_HHMMSS>/tables/preprocessed_lab_data.csv
results/<method>_<YYYYMMDD_HHMMSS>/tables/*model_comparison.csv
results/<method>_<YYYYMMDD_HHMMSS>/tables/overall_metrics.csv
results/<method>_<YYYYMMDD_HHMMSS>/tables/metrics_by_trial.csv
results/<method>_<YYYYMMDD_HHMMSS>/tables/lag_scan.csv
results/<method>_<YYYYMMDD_HHMMSS>/tables/affine_diagnostic.csv
results/<method>_<YYYYMMDD_HHMMSS>/figures/*.png
```

For failed or inadequate models, reports must include:

- quantitative failure evidence,
- figures supporting the failure,
- a clear statement of what the model can and cannot be used for,
- comparison against previous baselines when available,
- the next safe modeling step.

Do not claim that a model is good because correlation is high. Check mean error, MAE, RMSE, maximum absolute error, residual structure, affine diagnostic behavior, and lag diagnostics.

## Reports

Project context:

- `reports/overview.md`
- `reports/first_reports/`
- `reports/first_principles_model_validation.md`
- `reports/lab_rl_controller_data_analysis.md`
- `reports/henderson_hasselbalch_model_failure_report.md`

Report style:

- Use clear scientific writing.
- Include equations where the model is mathematical.
- Use KaTeX-safe notation in Markdown reports. For starred optima, write `x^{*}` instead of `x^\*` because KaTeX treats `\*` as an undefined command.
- Include generated figures with relative links.
- Include tables for metrics and comparisons.
- Separate what was tested, what was observed, what it means, and what remains uncertain.
- Do not hide model failure. Poor results are useful evidence.
- Do not edit raw lab data to make a report work.

## Running commands

Preferred Python interpreter for this workspace:

```text
C:\Users\hamediaa\.conda\envs\rl-env\python.exe
```

Use direct commands when `conda` is not available on `PATH`.

Compile current model-validation runners:

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' -m py_compile run_first_principles_data_comparison.py run_equilibrium_charge_balance_data_comparison.py
```

Run Henderson-Hasselbalch lab validation:

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_first_principles_data_comparison.py
```

Run equilibrium charge-balance lab validation:

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_equilibrium_charge_balance_data_comparison.py
```

Run the initial target sweep:

```powershell
& 'C:\Users\hamediaa\.conda\envs\rl-env\python.exe' run_initial_simulation.py
```

## Coding style

- Use Python with compact, readable, PEP 8 style.
- Keep model logic separate from plotting, report generation, and root-runner orchestration.
- Use clear variable names such as `acid_flow`, `acetate_flow`, and `water_flow`.
- Use `FH`, `FA`, and `FW` only for compact figures, tables, equations, or printed output.
- Do not vertically align assignments with extra spaces.
- Do not add unnecessary abstractions.
- Keep changes small, traceable, and testable.
- Prefer reusable scripts over notebooks for analysis that produces figures or reports.

## Change reports and commits

Every completed work item should end with a local change report and a local git commit.

Use this folder:

```text
change-reports/
```

Use this filename pattern:

```text
change-reports/YYYYMMDD_HHMMSS_short_task_name.md
```

Each change report should include:

- objective,
- files changed,
- method or implementation summary,
- generated artifacts,
- verification commands and results,
- known limitations or next steps.

Commit workflow:

1. Inspect `git status --short`.
2. Stage only files that belong to the completed task.
3. Create a concise local commit.
4. Do not include unrelated dirty files unless the user explicitly asks.
5. Do not amend commits unless the user explicitly asks.

Example commit message:

```text
Add equilibrium charge-balance validation workflow
```

## GitHub remote policy

The configured remote is:

```text
origin https://github.com/amirhm10/pHRLController.git
```

Do not push automatically.

Only push to GitHub when the user explicitly asks to push. Before pushing:

1. Run `git status`.
2. Summarize what branch and commits will be pushed.
3. Push only the requested branch and remote.

## Good next tasks

1. Treat the existing lab CSV as dynamic time-series data.
2. Add a static calibration workflow for effective `pKa`, pH bias, and affine compression.
3. Add a dynamic first-principles wrapper around static chemistry.
4. Estimate delay, mixing/residence-time dynamics, and pH sensor response from designed or existing time-series data.
5. Add feedback control only after the dynamic model predicts `PH_2` reliably.

## Avoid for now

- Do not implement RL yet.
- Do not implement MPC yet.
- Do not add controller logic yet.
- Do not use `PH_1` for metrics.
- Do not use `target_ph` for model-validation metrics unless explicitly requested.
- Do not edit raw CSV files.
- Do not remove reports, because they are used as scientific context.
