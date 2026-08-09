---
name: mathematical-reasoning-verification
description: Derive and verify mathematical models, equations, assumptions, proofs, approximations, stability arguments, conditioning, and numerical checks. Use for linear algebra, calculus, probability, ODE or DAE systems, dynamical systems, optimization theory, gradients, Jacobians, Lyapunov analysis, dimensional consistency, or counterexample search. State domains and assumptions, test limiting cases, and distinguish theorem, derivation, approximation, heuristic, and numerical observation.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Mathematical Reasoning and Verification

## Purpose

Produce mathematics that is explicit, checkable, and correctly scoped. The goal is not more notation. The goal is to prevent hidden assumptions, sign errors, dimensional inconsistency, invalid generalization, and numerically fragile conclusions.

## Modes

- formulation: define variables, spaces, equations, and assumptions
- derivation: develop a result step by step
- proof audit: inspect logical validity and missing conditions
- numerical verification: compare analytic, symbolic, automatic-differentiation, and finite-difference results
- stability audit: verify equilibrium, invariance, and decrease conditions
- approximation audit: quantify neglected terms and validity region
- counterexample search: test universal or overly broad claims

## Required workflow

### 1. Define objects

State:

- variable domains and dimensions
- units when physical quantities are involved
- index ranges
- functions and mappings
- regularity assumptions
- probability spaces or distributions
- initial and boundary conditions
- equilibrium or reference point
- coordinate system

Do not use the same symbol for physical and scaled variables.

### 2. Classify the statement

Label it as:

- definition
- identity
- theorem
- derivation under assumptions
- approximation
- numerical observation
- empirical correlation
- heuristic
- conjecture

Do not present an empirical pattern as a theorem.

### 3. Derive step by step

- show transformations that change the meaning
- identify where each assumption enters
- state sign and transpose conventions
- preserve dimensions
- distinguish continuous and discrete time
- distinguish local and global claims
- distinguish expectation, sample average, and one realization

### 4. Check dimensions and units

Every additive term must have compatible units. For dimensionless scaled models, record the scaling map and how physical constraints transform.

### 5. Test special and limiting cases

Examples:

- zero disturbance
- zero residual action
- no reaction
- ideal mixture
- linear limit
- deterministic limit
- zero or infinite penalty
- small time-step limit
- boundary of the feasible set
- singular or repeated eigenvalue
- one-component or one-state case

### 6. Search for counterexamples

Probe:

- boundaries
- singular matrices
- nonconvex regions
- nonsmooth clipping or projection
- degenerate constraints
- alternative initial conditions
- hidden partial observability
- cases where denominators vanish
- cases where an implication is only one-way

### 7. Verify derivatives and algebra

When code is available:

- compare analytic or AD gradients with finite differences
- check Jacobian sparsity and shape
- test Hessian symmetry where expected
- use symbolic simplification only as support, not as a substitute for assumptions
- choose perturbation sizes based on scale and conditioning

See [numerical-verification.md](references/numerical-verification.md).

### 8. Assess conditioning

Check:

- condition numbers
- rank deficiency
- near collinearity
- eigenvalue sensitivity
- scale separation
- stiffness
- cancellation
- identifiability

A numerically unstable computation can produce a misleading result even when the algebra is correct.

### 9. Bound the conclusion

State:

- where the result holds
- assumptions required
- whether it is local, regional, or global
- exact versus approximate status
- numerical tolerance
- unresolved conditions

## Stability work

For stability claims:

- define equilibrium and closed-loop map
- use the implemented action, after clipping, projection, optimization, and fallback
- specify the region
- verify positive definiteness or appropriate comparison bounds
- verify decrease or invariance
- account for disturbances and model error
- separate empirical decay from a theoretical guarantee

Read [stability-claims.md](references/stability-claims.md).

## Collaborate with

- `chemical-engineering-foundations` for physical meaning
- `optimization-modeling` for formulation validity
- `solver-engineering` for numerical solution
- `control-mpc-research` for closed-loop interpretation
- `safe-learning-certification` for guarantee strength
- `experiment-and-statistics` for empirical evidence

## Output

- definitions and assumptions
- derivation or proof
- checks and counterexamples
- numerical verification
- conclusion scope
- unresolved issues

## Gotchas

- Eigenvalues of an approximate model do not automatically establish plant stability.
- A small residual may be caused by scaling.
- Positive sampled values do not prove positive definiteness.
- A Lyapunov decrease checked on actor proposals does not certify executed actions.
- Interchanging limits, expectations, derivatives, or integrals requires conditions.
- Symbolic software can return expressions valid only on implicit branches or domains.
