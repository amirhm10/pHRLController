# pHRLController

Starter codebase for the pH control project.

The current lab system is an inline acetate buffer mixing process with three inlet streams:

- acetic acid, 100 mM
- sodium acetate, 100 mM
- Arium ultrapure water

Each pump is assumed to operate from 1 to 10 mL/min. The first objective is to predict and track a user-defined outlet pH. The code currently contains only steady-state simulation models, not MPC or RL.

## Repository structure

```text
pHRLController/
├── run_initial_simulation.py
├── simulation/
│   ├── config.py
│   ├── simple_buffer_model.py
│   └── equilibrium_buffer_model.py
├── helpers/
│   ├── experiment_grid.py
│   └── plotting.py
└── reports/
    ├── overview.md
    └── first_reports/
```

## Models included

### 1. Simple buffer model

Uses Henderson-Hasselbalch:

```text
pH = pKa + log10(F_A/F_H)
```

where `F_A` is sodium acetate flow and `F_H` is acetic acid flow.

### 2. Equilibrium charge-balance model

Solves:

```text
f(H) = H + C_Na - C_T Ka/(Ka + H) - Kw/H = 0
```

then returns:

```text
pH = -log10(H)
```

## Quick start

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the first simulation sweep:

```bash
python run_initial_simulation.py
```

This creates a timestamped result folder using the active method name, for example:

```text
results/equilibrium_charge_balance_YYYYMMDD_HHMMSS/
```

The saved plots are stamped with the method and run time. The result folder contains:

```text
figures/target_ph_sweep.png
figures/flow_allocation.png
figures/model_difference.png
figures/ratio_map.png
tables/initial_ph_sweep.csv
```

## Current scope

This codebase is intentionally simple. It does not yet include:

- dynamic mixing or tubing delay,
- pH probe dynamics,
- pump dynamics,
- feedback control,
- MPC,
- RL.

Those should be added after the steady-state model and lab data are checked.
