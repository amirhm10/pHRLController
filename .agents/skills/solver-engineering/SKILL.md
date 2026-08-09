---
name: solver-engineering
description: Select, configure, diagnose, and verify numerical solvers for optimization and dynamic models. Use for IPOPT, HiGHS, OSQP, SCIP, CasADi, Pyomo, CVXPY, SciPy optimizers, linear algebra failures, scaling, initialization, derivative checks, infeasibility, warm starts, convergence status, KKT residuals, and local-versus-global interpretation. Start from problem structure and formulation; do not treat an 'optimal' status as sufficient validation.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Solver Engineering

## Purpose

Determine whether a numerical problem is being solved by an appropriate algorithm and whether the returned result is trustworthy. Separate formulation, scaling, derivative, initialization, and algorithm failures.

## Entry requirements

Before tuning options, obtain:

- problem class
- variable and constraint sizes
- convexity or nonconvexity
- differentiability
- bounds
- sparsity
- initial point
- solver and version
- termination status
- relevant log
- residuals
- scaling information

If the formulation is unclear, activate `optimization-modeling`.

## Solver selection

Use structure, not familiarity.

- LP or MILP: start with a linear or mixed-integer solver such as HiGHS or another available solver matched to the formulation.
- Convex QP: consider OSQP, HiGHS, or another appropriate convex QP solver.
- Smooth NLP: consider IPOPT or another smooth constrained NLP solver.
- Dynamic NLP: use a modeling and differentiation layer such as CasADi or Pyomo with a suitable NLP solver.
- Convex modeled problem: use a disciplined convex modeling system and compatible solver.
- MINLP or GDP: use a method that matches integer and nonlinear structure, and state local versus global behavior.
- Nonlinear least squares: use a least-squares method when residual structure matters.

See [solver-map.md](references/solver-map.md).

## Diagnostic workflow

### 1. Reproduce the status

Record the exact command, options, model version, initial point, and log. Do not diagnose from a one-line paraphrase if the log is available.

### 2. Check formulation symptoms

Look for:

- inconsistent bounds
- missing variables or equations
- unbounded directions
- impossible specifications
- wrong signs
- poor big-M values
- nonsmooth operations passed to a smooth solver
- inactive or missing constraints
- hidden integer variables
- NaNs or invalid property evaluations

### 3. Check scaling

Inspect orders of magnitude for:

- variables
- equality residuals
- inequality residuals
- objective terms
- Jacobian entries
- Hessian entries

Scale by physical characteristic values where possible. Avoid arbitrary scaling that changes the intended weighting.

Read [scaling-infeasibility.md](references/scaling-infeasibility.md).

### 4. Check initialization

- evaluate all functions at the initial point
- identify domain violations
- initialize physical states consistently
- stage difficult unit models
- use continuation or homotopy
- solve a feasibility problem
- warm start from a nearby case
- verify variable ordering and dual compatibility

### 5. Check derivatives

- compare analytic or AD derivatives with finite differences
- inspect sparsity and rank
- find discontinuities, clipping, branching, or lookup-table artifacts
- test several finite-difference steps
- check Hessian strategy and symmetry

Read [derivative-checking.md](references/derivative-checking.md).

### 6. Interpret termination

Report:

- status
- objective
- maximum equality residual
- maximum inequality violation
- dual residual
- complementarity
- iteration count
- solve time
- active bounds
- optimality gap for integer problems
- local or global interpretation

A converged nonconvex NLP is generally a local result unless a global method or proof establishes more.

### 7. Cross-check

When important:

- retry from multiple initial points
- solve a simplified problem
- compare another solver class
- perturb scaling
- verify the returned point independently
- replay the solution in the physical model
- test warm-start consistency

### 8. Hand back to the domain

Solver feasibility is not the same as physical validity, control stability, safety, or statistical evidence. Ask the relevant specialist to interpret the result.

## Common output

- problem and solver summary
- failure classification
- evidence from logs and residuals
- recommended changes in priority order
- verification plan
- conclusion limits

## Gotchas

- Increasing iteration limits rarely fixes bad derivatives or infeasibility.
- Tight tolerances on poorly scaled models can make performance worse.
- "Restoration failed" is a symptom, not a unique cause.
- Warm starts can be harmful when the active set or model structure changes.
- A solver can return a numerically feasible but physically meaningless point.
- Different solvers may use different feasibility and optimality definitions.
