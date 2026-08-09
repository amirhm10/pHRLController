---
name: ph-aqueous-systems
description: Analyze aqueous chemistry and pH systems. Use for acid-base equilibria, buffers, polyprotic species, water autodissociation, electroneutrality, alkalinity, activities, ionic strength, electrolyte models, titration, precipitation coupling, pH neutralization reactors, acid or base dosing, mixing, sensor calibration and delay, nonlinear gain near equivalence, pH control, and pH ML or RL models. Distinguish chemistry, transport, measurement, actuator, model, and controller causes.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# pH and Aqueous Systems

## Purpose

Model pH from species, activities, conservation, charge balance, mixing, and measurement behavior. Avoid treating pH as a generic linear output.

## 1. Define the aqueous system

State:

- species
- strong and weak acids and bases
- polyprotic systems
- buffers
- salts
- solvent
- temperature
- pressure when relevant
- phases
- precipitation or gas exchange
- feed concentrations and flows
- reactor volume
- measurement location
- dosing streams

## 2. Define equilibrium and activity

For acid dissociation,

\[
K_a =
\frac{a_{\mathrm H^+}a_{\mathrm A^-}}
{a_{\mathrm{HA}}},
\]

and

\[
K_w =
a_{\mathrm H^+}a_{\mathrm{OH^-}},
\qquad
\mathrm{pH} = -\log_{10}a_{\mathrm H^+}.
\]

State when activity is approximated by concentration and why.

Read [aqueous-equilibria.md](references/aqueous-equilibria.md).

## 3. Enforce balances

Use as applicable:

- component or analytical concentration balances
- elemental balances
- charge balance
- alkalinity
- water balance
- phase-equilibrium constraints
- precipitation constraints

A generic electroneutrality condition is

\[
\sum_i z_i c_i = 0.
\]

## 4. Choose an electrolyte model

Consider:

- ideal dilute approximation
- Debye-Huckel family
- extended activity models
- SIT
- Pitzer
- simulator-specific electrolyte packages

Match the model to ionic strength, species, and data. Read [electrolyte-models.md](references/electrolyte-models.md).

## 5. Model dynamics and mixing

Include:

- inlet and outlet species balances
- volume
- residence time
- acid and base addition
- mixing
- sensor location
- transport delay
- equilibrium or kinetic assumption
- temperature
- gas exchange
- precipitation or dissolution if relevant

## 6. Audit measurement

Check:

- measured channel
- calibration
- slope and offset
- reference electrode
- temperature compensation
- sample conditioning
- delay
- filtering
- noise
- drift
- saturation
- missing data

Do not confuse pH, hydrogen-ion concentration, voltage, or a derived analyzer output.

## 7. Audit control or learning

- acid and base action mapping
- flow units
- actuator bounds and rate limits
- simultaneous acid and base use
- nonlinear gain
- buffer region
- equivalence region
- reward symmetry on logarithmic pH scale
- observation Markov property
- sensor delay
- safety and dosing limits
- fallback

Read [ph-control.md](references/ph-control.md).

## 8. Validate

- charge balance
- species balance
- nonnegative concentrations
- pH range
- limiting strong-acid and strong-base cases
- titration curve
- buffer capacity
- equilibrium residuals
- sensitivity to activity model
- dynamic mass balance
- measurement plausibility

## Output

- species and assumptions
- equilibrium and balance formulation
- activity-model choice
- dynamic and measurement model
- control or learning implications
- validation and uncertainty
- next experiment

## Gotchas

- Henderson-Hasselbalch is not universally valid.
- pH is logarithmic, so symmetric pH errors are not symmetric hydrogen-ion errors.
- Buffer capacity changes dramatically across the operating range.
- Sensor delay can dominate reactor dynamics.
- Random row splits can leak titration trajectories.
- A controller can waste chemicals by dosing acid and base simultaneously.
