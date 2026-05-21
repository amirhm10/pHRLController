# Codex Context for pHRLController

This repository is the starting codebase for the pH control project.

## Current scope

Focus only on the pH process model and basic simulations for now. Do not add MPC or RL until the steady-state model is checked against data.

Current implemented models:

1. `simulation/simple_buffer_model.py`
   - Henderson-Hasselbalch model.
   - Main equation: `pH = pKa + log10(FA/FH)`.

2. `simulation/equilibrium_buffer_model.py`
   - Charge-balance equilibrium model.
   - Solves `f(H) = H + C_Na - C_T Ka/(Ka + H) - Kw/H = 0`.

3. `run_initial_simulation.py`
   - Runs target pH sweeps.
   - Saves plots and a CSV table under `outputs/`.

## Coding style

- Keep code compact and readable.
- Use PEP 8 spacing.
- Do not vertically align assignments with extra spaces.
- Keep model files separated from plotting and report files.
- Prefer clear variable names like `acid_flow`, `acetate_flow`, and `water_flow` in code.
- Use `FH`, `FA`, and `FW` only in figures or compact printed output.

## Chemistry conventions

- `acid_flow` means acetic acid flowrate.
- `acetate_flow` means sodium acetate flowrate.
- `water_flow` means Arium water flowrate.
- Stock concentrations are currently 100 mM for both acetic acid and sodium acetate.
- Pump bounds are currently 1-10 mL/min for all streams.
- The useful first pH range is about 3.76-5.76.

## Near-term tasks

Good next tasks:

1. Add unit checks for the two pH models.
2. Add a data loader once lab data are available.
3. Fit effective `pKa` and pH bias from data.
4. Add first-order-plus-delay dynamics.
5. Add a simple feedback controller.

Avoid adding RL until the model-based baseline is working.
