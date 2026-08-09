# Lyapunov and Barrier Audit

## Lyapunov

Define:

- equilibrium
- \(V(x)\)
- region \(\Omega\)
- closed-loop map
- implemented action
- decrease condition
- disturbances and error

A typical discrete condition is

\[
V(x^+) - V(x)
\le -\alpha(\|x\|)+\varepsilon.
\]

State what \(\varepsilon\) means.

## Control barrier function

For safe set

\[
\mathcal C = \{x:h(x)\ge 0\},
\]

a continuous-time condition may use

\[
\dot h(x,u) \ge -\alpha(h(x)).
\]

A discrete-time implementation requires an appropriate discrete condition or discretization analysis.

## Audit

- relative degree
- input bounds
- feasibility
- model uncertainty
- sampling
- measurement noise
- actuator dynamics
- conflicting constraints
- fallback
- numerical tolerances

## Empirical check

Plot or compute:

- \(V\)
- decrease residual
- barrier residual
- intervention
- constraint margin
- projection size
- violation

An empirical plot supplements but does not replace proof assumptions.
