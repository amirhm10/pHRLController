# Numerical Verification

## Gradient check

For an analytic or AD gradient \(g\) and central finite-difference estimate \(g_{\mathrm{FD}}\), report

\[
\epsilon_g =
\frac{\|g-g_{\mathrm{FD}}\|_2}
{1+\|g_{\mathrm{FD}}\|_2}.
\]

Also inspect componentwise errors. A single relative number can hide a wrong small component.

## Step-size sweep

Use several perturbation scales. The expected pattern is:

- large step: truncation error
- intermediate step: best agreement
- very small step: roundoff and cancellation

## Jacobian check

Verify:

- shape
- ordering of variables and residuals
- sparsity
- rank
- directional derivative agreement

## Matrix checks

Depending on the claim:

- symmetry
- positive definiteness or semidefiniteness
- eigenvalue location
- singular values
- condition number
- controllability or observability rank
- residual of a linear solve

## ODE and DAE checks

- refine time step or tolerance
- compare explicit and implicit methods for suspected stiffness
- check conserved quantities
- check algebraic residuals
- verify event timing
- test sensitivity to initial consistency

Numerical agreement is evidence, not a proof. State tolerances and tested region.
