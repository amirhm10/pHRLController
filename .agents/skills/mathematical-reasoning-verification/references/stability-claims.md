# Stability Claim Audit

## Required objects

- state or error \(x\)
- equilibrium \(x^\star\)
- closed-loop map \(x^+=F(x)\) or \(\dot{x}=F(x)\)
- implemented action \(u_{\mathrm{exec}}\)
- candidate Lyapunov function \(V\)
- region \(\Omega\)
- disturbances and model error

## Typical local discrete-time conditions

\[
\underline{\alpha}\|x-x^\star\|^2
\le V(x)
\le
\overline{\alpha}\|x-x^\star\|^2,
\]

and

\[
V(F(x))-V(x)
\le
-\alpha\|x-x^\star\|^2
+
\varepsilon(x),
\qquad x\in\Omega.
\]

Clarify whether \(\varepsilon\) is zero, bounded, state dependent, or empirical.

## Check

- equilibrium consistency
- positive definiteness
- decrease condition
- invariance of \(\Omega\)
- feasibility under constraints
- behavior of fallback
- model mismatch
- disturbances
- sampling and discretization
- estimator dynamics
- target changes

## Permitted conclusion levels

- observed decay in specified trajectories
- numerical decrease over a sampled region
- local guarantee under assumptions
- robust or input-to-state claim under stated bounds

Do not skip directly from observed decay to a global guarantee.
