# Aspen Plus Audit

## Setup

- product and version
- unit set
- components
- property method
- databank parameters
- flowsheet
- specifications
- convergence settings

## Property method

Document why the method fits:

- hydrocarbon or gas system
- polar non-electrolyte
- strongly nonideal liquid
- electrolyte
- polymer
- high pressure
- association

## Convergence sequence

1. Solve simple feed and property calculations.
2. Initialize individual units.
3. Temporarily break difficult recycles.
4. Add recycles with deliberate tear streams.
5. Activate design specifications one at a time.
6. Inspect residuals and bound activity.
7. Restore full model.
8. validate balances and sensitivities.

## Result audit

- stream tables
- phase fractions
- heat duties
- pressure drops
- unit-operation performance
- convergence messages
- warnings
- balance closure
- property-domain warnings
