---
name: control-mpc-research
description: Analyze dynamical systems, system identification, observers, offset-free control, target selection, and model predictive control. Use for state-space or input-output models, scaling, estimation, steady-state optimization, QP or NLP MPC, input and output constraints, move suppression, feasibility, recursive feasibility, robust or stochastic MPC, economic MPC, nonlinear MPC, computational timing, and closed-loop comparison. Separate plant physics, model quality, target feasibility, optimizer behavior, and RL supervisory effects.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Control and MPC Research

## Purpose

Reconstruct and evaluate the closed-loop control architecture from plant through estimator, target selector, optimizer, actuator, and logger. Determine whether observed behavior comes from plant physics, model error, estimation, optimization, constraints, supervisory learning, or fallback.

## 1. Define the system

State:

- physical plant
- control-oriented model
- state \(x\)
- output \(y\)
- manipulated input \(u\)
- disturbance \(d\)
- setpoint \(r\)
- sample time
- units
- physical and scaled coordinates
- input, rate, state, and output constraints

Do not assume the identified model and nonlinear plant use the same coordinates or time step.

## 2. Reconstruct the execution path

Trace:

`plant measurement -> scaling -> estimator -> disturbance estimate -> target selector -> MPC model and constraints -> candidate input -> RL or safety modification -> executed input -> plant -> logger`.

Identify the authoritative implementation, including notebook-local functions when relevant.

## 3. Audit the model

For identified or reduced models:

- data and excitation
- preprocessing
- delays
- order
- scaling
- fit and residuals
- train and validation regimes
- stability
- controllability and observability
- uncertainty
- operating-region validity

Read [identification-estimation.md](references/identification-estimation.md).

## 4. Audit estimator and offset-free structure

Check:

- observer equations
- augmented disturbance state
- gain and poles
- detectability
- measurement mapping
- initialization
- update ordering
- disturbance interpretation
- whether target selection uses the same model and disturbance estimate

Read [offset-free-mpc.md](references/offset-free-mpc.md).

## 5. Audit target selection

Distinguish:

- raw setpoint
- admissible steady target
- steady state and input
- target slack
- target feasibility
- regularization
- disturbance compensation

Check whether apparent tracking improvement comes from changing the target rather than improving closed-loop behavior.

## 6. Audit MPC formulation

Define:

\[
\min_{\Delta U}
\sum_{i=1}^{N_p}
\|y_{k+i}-r_{k+i}\|_Q^2
+
\sum_{i=0}^{N_c-1}
\|\Delta u_{k+i}\|_R^2
+
\text{slack penalties},
\]

with dynamics and constraints.

Verify:

- \(N_p\), \(N_c\), and decision interval
- absolute input versus increment
- terminal treatment
- move blocking
- warm start
- soft constraints
- slack units and penalties
- solver status
- fallback
- first-move extraction
- model update

## 7. Analyze feasibility and stability

Separate:

- initial feasibility
- recursive feasibility
- target feasibility
- solver convergence
- constraint satisfaction
- terminal ingredients
- fallback feasibility
- empirical stability
- theoretical stability

Use `mathematical-reasoning-verification` and `safe-learning-certification` for strong guarantees.

## 8. Analyze closed-loop results

Report in physical units:

- IAE, ISE, RMSE
- steady offset
- settling and overshoot
- input movement
- rate activity
- saturation
- constraint violations
- target mismatch
- estimator error
- solver failures and time
- fallback or intervention
- per-regime performance

Separate transient and near-setpoint behavior.

## 9. Robust, stochastic, nonlinear, and economic variants

Use [advanced-mpc.md](references/advanced-mpc.md) when the method departs from nominal linear tracking MPC.

State exactly what uncertainty, nonlinearity, risk, or economic objective is represented.

## 10. Compare fairly

Keep plant, scenario, constraints, sample time, model version, target definition, and evaluation windows fixed unless they are the changed factor.

## Gotchas

- Good model fit does not imply good closed-loop predictions.
- Offset-free disturbance estimates can absorb model bias and change target feasibility.
- A target selector can make tracking look easier by moving the target.
- A solver fallback can hide infeasibility.
- Changing MPC weights changes the evaluation objective if metrics are not independent.
- A controller may be stable locally but violate constraints during setpoint changes.
- A small average error can hide actuator saturation or unsafe transients.
