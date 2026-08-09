---
name: scientific-software-testing
description: Design and implement tests for scientific, numerical, simulator-coupled, ML, RL, optimization, control, and notebook software. Use for unit tests, invariants, property-based tests, metamorphic tests, numerical regression, derivative checks, integration and end-to-end tests, notebook smoke tests, simulator contract tests, solver tests, stochastic ML or RL tests, CI strategy, and regression tests for discovered defects. Choose physically and numerically justified tolerances; do not test stochastic learning by exact curve equality.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Scientific Software Testing

## Purpose

Create tests that detect scientific and implementation errors even when an exact output oracle is unavailable. Combine software assertions with physical invariants, numerical convergence, statistical behavior, and interface contracts.

## Test strategy

Use the smallest level that can detect the failure.

1. unit tests
2. invariant tests
3. property-based tests
4. metamorphic tests
5. numerical regression
6. integration tests
7. notebook and simulator contract tests
8. stochastic ML and RL tests
9. end-to-end scientific acceptance tests

Read [test-pyramid.md](references/test-pyramid.md).

## 1. Define the test contract

For each behavior:

- scientific or software requirement
- input domain
- expected property
- tolerance
- failure message
- cost and execution class
- dependencies
- deterministic or stochastic status

## 2. Unit tests

Test deterministic local behavior:

- scaling and inverse scaling
- units and conversions
- matrix construction
- action mapping
- reward terms
- constraints
- kinetics
- thermodynamic helpers
- logging transforms
- schema validation

## 3. Invariant tests

Examples:

\[
\sum_i x_i = 1,
\qquad
x_i\ge 0,
\qquad
T>0,
\qquad
P>0.
\]

Also test:

- material and charge balance
- nonnegative holdup
- valid action bounds
- symmetric covariance or Hessian
- positive semidefinite penalty matrices
- finite losses and rewards
- polymer moment relationships
- zero residual reproduces nominal behavior

## 4. Property-based tests

Generate broad cases:

- compositions on a simplex
- edge actions
- variable sequence lengths
- missing data
- extreme but valid flows
- near-singular matrices
- multiple seeds
- pH near equivalence
- solver bounds

Use constrained strategies so generated cases are scientifically meaningful.

## 5. Metamorphic tests

When exact outputs are unknown, test transformations:

- unit conversion preserves physical result
- equivalent label permutation permutes outputs
- zero disturbance recovers nominal case
- zero RL residual recovers MPC
- adding a zero-flow stream changes nothing
- time-step refinement converges
- repeated serialization preserves configuration
- scaling and inverse scaling round trip

Read [numerical-metamorphic.md](references/numerical-metamorphic.md).

## 6. Numerical regression

Use trusted small cases and justified tolerances:

\[
|a-b|
\le
\mathrm{atol}
+
\mathrm{rtol}|b|.
\]

Do not increase tolerances until a test passes without understanding numerical and physical scale.

## 7. Integration tests

Test interfaces:

- plant to estimator
- estimator to target selector
- target selector to MPC
- controller to safety layer
- safety layer to environment
- environment to replay
- simulator export to analysis
- config to runner
- result bundle to figures

## 8. Notebook and simulator tests

- validate cell order and required symbols
- provide cheap smoke mode
- avoid full training or live Aspen by default
- mock or contract-test external systems
- mark expensive tests
- preserve original simulator files
- verify mappings and schemas offline

## 9. Solver tests

Include:

- known feasible problem
- known infeasible problem
- active-bound case
- poorly scaled case
- derivative check
- warm-start case
- failure and fallback
- independent residual verification

## 10. ML and RL tests

Do not assert exact learning curves.

Test:

- split and preprocessing isolation
- deterministic components under fixed seed
- finite gradients and losses
- output shapes and bounds
- replay transitions
- termination and truncation
- checkpoint round trip
- evaluation mode
- aggregate behavior on a small controlled task
- no train-test leakage

Read [simulator-ml-rl-testing.md](references/simulator-ml-rl-testing.md).

## 11. End-to-end acceptance

Validate:

`configuration -> execution -> saved bundle -> metrics -> figure -> report claim`.

This should be small, reproducible, and marked separately from unit tests.

## 12. Bug policy

Every verified defect should receive a regression test when practical. The test should fail before the fix and pass after it.

## Output

- risk-based test plan
- tests added or recommended
- execution classes
- tolerances and rationale
- results
- uncovered risks
- files changed and verification

## Gotchas

- Exact floating-point equality is rarely appropriate.
- Snapshot tests can preserve a wrong scientific result.
- Mocks can pass while the real simulator mapping is wrong.
- Fixed seeds do not guarantee determinism across hardware and libraries.
- A test that only checks "no exception" is weak.
- Expensive end-to-end tests do not replace fast unit and invariant tests.
