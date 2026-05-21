# AGENTS.md

## Project

This repository is the starter codebase for the pH control project. The current process is an inline acetate buffer mixing system using:

- acetic acid, 100 mM
- sodium acetate, 100 mM
- Arium ultrapure water

Each flowrate is currently assumed to be in the range 1-10 mL/min. The first objective is to model and later control the outlet pH for user-defined pH targets.

## Current scope

Focus on the pH process model and basic simulations first. Do not add MPC or RL until the steady-state models are checked against lab data.

Currently implemented models:

1. `simulation/simple_buffer_model.py`
   - Henderson-Hasselbalch model.
   - Main relation: `pH = pKa + log10(FA/FH)`.

2. `simulation/equilibrium_buffer_model.py`
   - Charge-balance equilibrium model.
   - Solves `f(H) = H + C_Na - C_T Ka/(Ka + H) - Kw/H = 0`.

3. `run_initial_simulation.py`
   - Runs target pH sweeps.
   - Saves figures and tables under `outputs/`.

## Repository layout

```text
simulation/          pH process models
helpers/             plotting and experiment-grid utilities
reports/             project notes and copied first reports
run_initial_simulation.py  first runnable script
CODEX_CONTEXT.md     extra context for Codex
```

## Coding style

- Use Python with compact, readable, PEP 8 style.
- Do not vertically align assignments with extra spaces.
- Keep model logic separate from plotting and report generation.
- Use clear code variable names such as `acid_flow`, `acetate_flow`, and `water_flow`.
- Use `FH`, `FA`, and `FW` only for compact figures, tables, or printed output.
- Do not add unnecessary abstractions.
- Keep changes small and explain them clearly.

## Scientific conventions

- `acid_flow` means acetic acid flowrate.
- `acetate_flow` means sodium acetate flowrate.
- `water_flow` means Arium water flowrate.
- Current stock concentrations are 100 mM for both acetic acid and sodium acetate.
- Current pump bounds are 1-10 mL/min for all three streams.
- Expected useful pH range is about 3.76-5.76.

## Good next tasks

1. Verify `run_initial_simulation.py` runs without errors.
2. Add simple tests for the two pH models.
3. Add a data-loading structure for future lab data.
4. Add fitting for effective `pKa` and pH bias once data are available.
5. Add a first-order-plus-delay dynamic layer after steady-state behavior is checked.
6. Add feedback control after the model/data comparison is reliable.

## Avoid for now

- Do not implement RL yet.
- Do not implement MPC yet.
- Do not redesign the repository structure unless necessary.
- Do not remove the reports, because they are used as context for Codex.
