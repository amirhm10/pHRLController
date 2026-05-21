# First pH Process Reports

These reports are copied/summarized from the Obsidian vault notes so that Codex can understand the pH project directly from this repository.

## Included reports

1. `01_process_description.md`
2. `02_simplest_model_first_try.md`
3. `03_equilibrium_model_charge_balance.md`
4. `04_previous_siso_ph_model_implementation.md`

## Main project idea

The current pH project is an inline acetate buffer preparation process. The first useful modeling path is:

```text
flowrates -> mixed concentrations -> pH prediction -> feedback/control later
```

The first two steady-state models are already implemented in the `simulation/` directory.
