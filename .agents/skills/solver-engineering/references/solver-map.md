# Solver Map

| Problem | Typical starting point | Verify |
|---|---|---|
| LP | HiGHS or another LP solver | primal and dual feasibility |
| MILP | HiGHS, SCIP, or available MILP solver | gap, nodes, formulation strength |
| Convex QP | OSQP, HiGHS, or compatible QP solver | convexity, primal and dual residual |
| Smooth NLP | IPOPT or compatible NLP solver | derivatives, scaling, local result |
| Dynamic NLP | CasADi or Pyomo model plus NLP solver | discretization, consistency, sparsity |
| Convex symbolic model | CVXPY with compatible solver | DCP compliance and solver status |
| MINLP | SCIP, decomposition, or MINLP framework | relaxations, local versus global |
| Nonlinear least squares | specialized least-squares solver | residual structure and identifiability |
| Unconstrained smooth | SciPy or specialized method | gradients and conditioning |

This is a default map, not a guarantee. Availability, licensing, problem size, sparsity, warm-start needs, and robustness can change the choice.

## Selection questions

- Are all functions smooth?
- Is the problem convex?
- Are there integers or disjunctions?
- Is the Hessian positive semidefinite?
- Is the model sparse?
- Are repeated warm starts important?
- Is a global guarantee required?
- Are derivatives available?
- Is the problem small enough for dense methods?
