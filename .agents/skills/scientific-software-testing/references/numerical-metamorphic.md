# Numerical and Metamorphic Testing

## Tolerance design

Base tolerance on:

- units
- magnitude
- conditioning
- algorithm
- discretization error
- solver tolerance
- platform variation
- scientific significance

Use both absolute and relative tolerance.

## Convergence tests

For grid or time-step refinement:

- compute solutions at several resolutions
- compare a common physical quantity
- estimate convergence behavior
- ensure the reference is sufficiently resolved
- avoid using the same flawed implementation as the oracle

## Metamorphic examples

- unit conversion
- coordinate round trip
- permutation symmetry
- mass or charge conservation
- zero-input limit
- no-reaction limit
- nominal-controller limit
- duplicate zero stream
- reordered independent batch
- positive scaling of a mathematically equivalent objective, with awareness that solver numerics can change

## Differential testing

Compare:

- two independent implementations
- two solvers
- analytic and numerical derivative
- reduced and high-fidelity model in a shared regime
