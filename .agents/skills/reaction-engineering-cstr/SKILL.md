---
name: reaction-engineering-cstr
description: Analyze reaction engineering and reactor dynamics with a strong CSTR focus. Use for stoichiometry, kinetic mechanisms, Arrhenius rates, conversion and selectivity, reactor material and energy balances, residence time, catalyst effects, heat and mass transfer, multiplicity, ignition and extinction, thermal runaway, stiff integration, kinetic parameter estimation, model reduction, and reactor control interactions. Distinguish kinetic, transport, thermal, numerical, estimator, and controller causes.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Reaction Engineering and CSTR

## Purpose

Construct and validate reactor models from stoichiometry, kinetics, conservation laws, heat and mass transfer, and operating conditions. Determine whether behavior is chemical, transport-limited, thermally driven, numerically induced, or control related.

## 1. Define the reaction system

State:

- species
- reactions
- stoichiometric matrix
- phases
- catalyst
- rate basis
- reactor type and volume
- feed and outlet
- pressure
- temperature
- heat exchange
- mixing assumption
- residence time
- operating mode

## 2. Audit kinetics

For each reaction:

- rate expression
- units
- concentration, activity, or partial-pressure basis
- Arrhenius parameters
- reversible or irreversible treatment
- equilibrium limitation
- inhibition
- catalyst deactivation
- fitted range
- identifiability

Read [kinetics-identifiability.md](references/kinetics-identifiability.md).

## 3. Write balances

For constant-volume CSTR component \(i\),

\[
\frac{dC_i}{dt}
=
\frac{F}{V}(C_{i,\mathrm{in}}-C_i)
+
\sum_r \nu_{ir}r_r.
\]

A representative energy balance is

\[
\rho C_p V \frac{dT}{dt}
=
F\rho C_p(T_{\mathrm{in}}-T)
-
V\sum_r \Delta H_r r_r
-
UA(T-T_c).
\]

State the heat-of-reaction sign convention and any variable-density or variable-volume terms.

Read [cstr-models.md](references/cstr-models.md).

## 4. Analyze steady states and multiplicity

- solve all physically relevant steady states
- check domains and bounds
- compute or estimate local stability
- identify ignition and extinction
- trace solution branches when parameters vary
- distinguish unstable solutions from solver failures
- check heat-generation and heat-removal curves

## 5. Analyze time scales and stiffness

Compare:

- reaction
- residence
- mixing
- heat transfer
- jacket
- sensor
- actuator
- controller

Use an appropriate integrator and test tolerance sensitivity. Read [thermal-stiffness.md](references/thermal-stiffness.md).

## 6. Audit transport and mixing

Check whether the model assumptions support:

- perfect mixing
- negligible gradients
- kinetic control
- heat-transfer coefficient
- mass-transfer rate
- catalyst effectiveness
- phase equilibrium
- constant physical properties

## 7. Audit parameter estimation

- excitation and data range
- measurement uncertainty
- parameter correlations
- structural and practical identifiability
- bounds
- prior information
- residuals
- validation data
- extrapolation

## 8. Connect to control or learning

When a controller or agent is present:

- map manipulated variables to physical effects
- check actuator and utility limits
- verify model operating region
- distinguish model mismatch from unmeasured disturbances
- inspect whether rewards trade conversion against temperature or safety
- test around multiple steady states
- include runaway and recovery scenarios

## 9. Validate

- species and elemental balances
- energy balance
- nonnegative concentrations
- physical temperatures and flows
- steady-state residuals
- trajectory convergence with tolerance refinement
- known limiting cases
- sensitivity to kinetics and heat transfer

## Output

- reaction and reactor definition
- balances and kinetics
- steady states and stability
- time-scale and stiffness analysis
- parameter and transport uncertainty
- implications for control or optimization
- next experiment

## Gotchas

- Celsius in an Arrhenius expression is a severe error.
- A negative heat of reaction can be used with opposite sign conventions; state the convention.
- A solver returning one steady state does not prove uniqueness.
- A local linear model can fail across ignition or extinction branches.
- An apparent controller instability can be integration instability.
- Conversion alone can hide poor selectivity or unsafe temperature.
