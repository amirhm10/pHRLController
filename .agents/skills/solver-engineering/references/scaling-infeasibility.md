# Scaling and Infeasibility

## Scaling report

Record ranges:

- variables: minimum and maximum characteristic magnitude
- equality residuals
- inequality residuals
- objective terms
- Jacobian row and column norms
- Hessian diagonal or spectral information

Aim for meaningful order-one values when possible.

## Feasibility-first procedure

1. Evaluate constraints at the initial point.
2. Group violations by physical or model family.
3. Remove the objective or use a feasibility objective.
4. Relax only diagnostic constraints with explicit slacks.
5. Inspect required slack magnitudes.
6. Restore constraints one family at a time.
7. Determine whether the original specification is physically attainable.

## Distinguish

- physical infeasibility
- algebraic inconsistency
- bound inconsistency
- discrete infeasibility
- property-domain failure
- numerical failure
- poor initial guess

## Warning

Do not keep diagnostic slacks in the final formulation without defining their scientific meaning and penalty.
