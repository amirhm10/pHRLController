---
name: optimization-modeling
description: Formulate and audit optimization problems before solver tuning. Use for LP, QP, convex optimization, nonlinear programming, MILP, MINLP, generalized disjunctions, complementarity, parameter estimation, optimal control, DAE-constrained optimization, robust or stochastic optimization, and multiobjective design. Define variables, units, objective, constraints, bounds, assumptions, degrees of freedom, convexity, and discretization. Separate formulation errors from solver errors.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Optimization Modeling

## Purpose

Translate the scientific or engineering decision into a mathematically correct optimization problem. Validate formulation structure before selecting or tuning a solver.

## Required formulation

State:

\[
\begin{aligned}
\min_x\quad & f(x;\theta) \\
\text{subject to}\quad
& g(x;\theta)=0,\\
& h(x;\theta)\le 0,\\
& \underline{x}\le x\le\overline{x},\\
& x_i\in\mathbb{Z}\quad i\in\mathcal{I},
\end{aligned}
\]

using only the parts that apply.

Define:

- decision variables
- fixed parameters
- uncertain quantities
- units and scaling
- objective meaning
- equality and inequality constraints
- bounds
- discrete choices
- initial and terminal conditions
- time grid or collocation scheme
- slack variables and penalties

## Workflow

### 1. Classify the problem

Identify:

- LP
- QP
- convex nonlinear program
- smooth nonconvex NLP
- MILP
- MINLP
- generalized disjunctive program
- complementarity or equilibrium-constrained problem
- least squares or parameter estimation
- dynamic optimization or optimal control
- robust optimization
- stochastic program
- chance-constrained problem
- multiobjective problem
- bilevel problem

See [problem-classification.md](references/problem-classification.md).

### 2. Check degrees of freedom

- count independent variables and equations
- identify fixed variables and specifications
- identify redundant or dependent constraints
- verify that the physical model is neither under- nor over-specified
- distinguish free design variables from states determined by equations

### 3. Audit objective

Check:

- physical or economic interpretation
- units
- magnitude of terms
- sign and direction
- unintended incentives
- normalization
- nonsmooth components
- penalties versus hard requirements
- whether the objective duplicates constraints
- multiobjective weighting or Pareto interpretation

### 4. Audit constraints

Check:

- direction
- units
- domains
- logical completeness
- bounds
- feasibility
- time indexing
- terminal conditions
- complementarity
- big-M constants
- slack semantics
- uncertainty handling
- physical conservation

### 5. Assess mathematical structure

Determine:

- convexity
- differentiability
- sparsity
- separability
- symmetry
- bilinear or multilinear terms
- discontinuities
- integer structure
- possible relaxations
- multiple local optima
- unbounded directions

### 6. Check scaling

Choose variable, residual, and objective scales before solver tuning. Prefer dimensionless or order-one formulations when physically meaningful.

### 7. Validate feasibility

Before optimizing:

- evaluate constraints at a known physical point
- solve a feasibility problem if needed
- remove or isolate the objective
- inspect violations by constraint family
- distinguish impossible specifications from poor initial guesses

### 8. Dynamic optimization

For optimal control, define:

- dynamics
- discretization
- path constraints
- control parameterization
- initial condition
- terminal cost and constraints
- move rate
- prediction and control horizons
- continuity constraints
- algebraic consistency

Read [dynamic-optimization.md](references/dynamic-optimization.md).

### 9. Uncertainty

If uncertainty matters, state whether the formulation is:

- nominal
- scenario based
- robust
- stochastic
- chance constrained
- distributionally robust
- risk sensitive

Do not call a nominal safety margin robust optimization.

### 10. Hand off to solver engineering

Only after the formulation is characterized should `solver-engineering` select algorithms, initialization, derivative methods, and tolerances.

## Validation output

- problem class
- variable and constraint map
- degrees of freedom
- objective audit
- feasibility status
- convexity and differentiability
- scaling plan
- expected solution multiplicity
- recommended solver class
- remaining formulation risks

## Gotchas

- A large penalty does not reproduce a hard constraint reliably.
- Incorrect big-M values can invalidate or weaken a model.
- A soft constraint can hide physical infeasibility.
- A zero-dimensional degree-of-freedom count does not guarantee equation independence.
- Discretization can change feasibility and stability properties.
- A feasible relaxed problem does not prove integer feasibility.
