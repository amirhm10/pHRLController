# Derivative Checking

## Directional check

For direction \(d\),

\[
\frac{F(x+\epsilon d)-F(x-\epsilon d)}{2\epsilon}
\approx J(x)d.
\]

Use several normalized directions and step sizes.

## Component check

Inspect absolute and relative errors. Relative error is unstable near zero, so use a mixed criterion.

## Common causes of mismatch

- wrong variable ordering
- stale cached values
- inconsistent scaling
- clipping or `max` operations
- conditional branches
- lookup tables
- nondifferentiable penalties
- unit conversions applied on only one path
- incorrect transpose
- finite-difference step outside a valid domain
- stateful simulator calls

## Hessian checks

- symmetry
- directional second derivative
- positive semidefiniteness when convexity is claimed
- consistency of exact and quasi-Newton modes

Do not disable derivative checking merely because the model is large. Sample variables or directions when a full check is expensive.
