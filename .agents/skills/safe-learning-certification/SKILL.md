---
name: safe-learning-certification
description: Analyze safety constraints, safe sets, Lyapunov and barrier methods, shields, projections, supervisor gates, fallback controllers, constrained RL, safe policy improvement, risk measures, and safety claims. Use when a method is called safe, stable, certified, constrained, shielded, filtered, or recovery-based. Evaluate the executed closed-loop action, intervention behavior, model uncertainty, and guarantee level. Distinguish empirical no-violation evidence from numerical certificates and theoretical guarantees.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Safe Learning and Certification

## Purpose

Determine what safety requirement is being enforced, by which mechanism, under what assumptions, and with what evidence. Prevent empirical success from being mislabeled as a formal guarantee.

## 1. Define safety

State:

- hazard or unacceptable event
- state, input, output, or cumulative cost constraint
- safe set
- constraint units
- time horizon
- disturbance and uncertainty assumptions
- required confidence or guarantee
- fallback behavior

For constrained RL, distinguish reward and cost:

\[
\max_\pi J_R(\pi)
\quad
\text{subject to}
\quad
J_{C_j}(\pi)\le d_j.
\]

A shaped scalar reward is not automatically a safety constraint.

## 2. Identify the safety mechanism

Examples:

- hard physical bounds
- MPC constraints
- terminal invariant set
- action clipping
- projection
- control barrier function
- Lyapunov filter
- supervisor gate
- model predictive safety filter
- recovery policy
- fallback controller
- probation or release schedule
- robust uncertainty margin

State where the mechanism sits in the execution path.

## 3. Trace the implemented action

Use:

`actor or optimizer proposal -> scaling -> clipping -> projection -> gate -> fallback or supervisor -> executed action -> plant`.

A certificate must refer to the action actually executed.

## 4. Define the claim level

Use [guarantee-ladder.md](references/guarantee-ladder.md). Do not use "guaranteed safe" without assumptions and a proof or valid certificate.

## 5. Audit mathematical conditions

Depending on the method, check:

- safe-set definition
- invariance
- Lyapunov positivity and decrease
- barrier condition
- feasibility
- recursive feasibility
- model error
- estimator error
- discretization
- input and rate limits
- uncertainty bounds
- terminal condition
- fallback safety
- intervention delay

Read [barrier-lyapunov.md](references/barrier-lyapunov.md).

## 6. Audit gate or projection behavior

Measure:

- proposal frequency
- acceptance
- rejection
- projection magnitude
- fallback
- intervention by state region
- early-release and tail behavior
- safety violations after acceptance
- conservative rejection
- controller-source-conditioned performance
- realized outcome after each decision

Read [gates-projections.md](references/gates-projections.md).

## 7. Test failure scenarios

Include:

- model mismatch
- unseen initial states
- disturbances
- sensor noise or delay
- actuator saturation
- solver failure
- invalid policy output
- estimator bias
- rapid target change
- fallback activation
- simulator or communication failure

## 8. Report safety separately from performance

At minimum:

- task performance
- safety cost
- violation count
- maximum violation
- integrated violation
- intervention and fallback
- worst scenario
- guarantee level
- assumptions

A safe method that never allows learning authority may not answer the intended research question.

## 9. Decide

State:

- safety requirement
- mechanism
- evidence
- guarantee level
- failure modes
- conservatism
- unresolved assumptions
- next validation or certificate step

## Gotchas

- Magnitude clipping is not a quality filter.
- A projection can be small but directionally harmful.
- A critic score is not a safety certificate unless calibrated and bounded for the purpose.
- Fallback frequency can make a learning controller appear safe while making it irrelevant.
- No violations in one simulation is level-1 empirical evidence, not a guarantee.
- A continuous-time barrier condition may not survive discretization without analysis.
