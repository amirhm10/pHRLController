# Thermal Multiplicity and Stiffness

## Multiplicity

Compare heat generation and heat removal as functions of temperature. Identify intersections and local slope behavior.

## Local stability

Linearize only after confirming the correct steady-state branch and coordinate system.

## Stiffness symptoms

- widely separated reaction and thermal time scales
- explicit integrator instability
- tiny adaptive steps
- sensitivity to tolerance
- fast radical or intermediate species
- algebraic equilibrium coupled to slow inventories

## Numerical checks

- compare explicit and implicit methods
- refine tolerances
- check conservation
- verify event timing
- inspect negative concentration handling
- avoid clipping that hides integration failure

## Control implications

- sample faster than relevant unstable or fast modes
- respect heat-removal limits
- test recovery
- avoid exploration near runaway without a validated safety layer
