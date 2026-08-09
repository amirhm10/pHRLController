# Gates, Projections, and Fallbacks

## Action projection

Define the projection objective and constraints, for example

\[
u_{\mathrm{proj}}
=
\arg\min_u \|u-u_{\mathrm{cand}}\|_W^2
\quad
\text{subject to safety conditions}.
\]

Record solver status and fallback if infeasible.

## Supervisor gate

Define the exact acceptance rule and score semantics. Check:

- score calibration
- comparison action
- margin
- tie handling
- stale critic or model
- action representation
- source logging
- release schedule

## Diagnostics

- candidate count
- accepted count
- projected count
- fallback count
- projection norm
- accepted-state distribution
- rejected-state distribution
- violation after each source
- task metric by source
- state-dependent conservatism

## Failure patterns

- gate copies nominal behavior
- gate accepts high-score but poor-realized actions
- projection satisfies geometry but not candidate quality
- fallback hides infeasible targets
- release schedule creates a delayed shock
- replay stores proposals while plant executes fallbacks
