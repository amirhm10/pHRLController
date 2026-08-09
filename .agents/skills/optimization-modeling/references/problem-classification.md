# Optimization Problem Classification

| Structure | Key features | Typical concerns |
|---|---|---|
| LP | linear objective and constraints | scaling, degeneracy, unboundedness |
| QP | quadratic objective, linear constraints | convexity of Hessian |
| Convex NLP | convex objective and feasible set | disciplined formulation, numerical scale |
| Nonconvex NLP | nonlinear equalities or nonconvex terms | local optima, initialization |
| MILP | linear model with integer variables | formulation strength, big-M, gap |
| MINLP | integer and nonlinear structure | global versus local method, relaxations |
| GDP | disjunctions and logic | reformulation validity |
| Complementarity | orthogonality or equilibrium | stationarity concept, regularization |
| Dynamic optimization | ODE or DAE constraints | discretization, initialization, stiffness |
| Robust optimization | bounded uncertainty | uncertainty set and conservatism |
| Stochastic programming | scenarios or distributions | sampling, nonanticipativity |
| Chance constrained | probabilistic constraints | distribution assumptions |
| Bilevel | nested decisions | reformulation and stationarity assumptions |

## Convexity audit

Check:

- objective curvature
- inequality direction and curvature
- affine equalities
- variable domains
- composition rules
- Hessian or known convex atoms
- hidden nonconvexity from products, ratios, exponentials, and discrete logic

Do not label a problem convex because the solver accepted it.
