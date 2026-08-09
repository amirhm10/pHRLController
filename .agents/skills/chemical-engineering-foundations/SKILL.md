---
name: chemical-engineering-foundations
description: Analyze chemical-process systems using conservation laws, units, thermodynamics, phase and reaction equilibrium, transport, residence time, and physical plausibility. Use for material or energy balances, property-method selection, reaction stoichiometry, heat and mass transfer, process data reconciliation, steady-state or dynamic models, and physical validation of simulations or learned models. Route detailed columns, reactors, polymers, pH, Aspen, control, or safety work to the matching specialist.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Chemical Engineering Foundations

## Purpose

Provide the shared physical and chemical reasoning layer for process systems. Start from conservation laws, units, constitutive relationships, and operating assumptions before interpreting control, ML, RL, optimization, or simulator results.

## 1. Define the system boundary

State:

- equipment and control volume
- phases
- components and species
- inlet and outlet streams
- reactions
- heat and work interactions
- accumulation
- steady or dynamic assumption
- spatial lumping
- reference states
- units and basis

## 2. Write conservation laws

For component \(i\),

\[
\frac{dn_i}{dt}
=
\sum_{\ell\in\mathcal I} F_\ell z_{i,\ell}
-
\sum_{\ell\in\mathcal O} F_\ell z_{i,\ell}
+
\sum_r \nu_{ir}R_r.
\]

Also check:

- total mass
- elemental balances
- energy
- charge
- momentum or pressure-flow relationships when relevant

Do not add incompatible molar and mass quantities.

## 3. Audit units and scaling

- declare basis
- convert units explicitly
- distinguish standard and actual volumetric flow
- distinguish mass and molar concentration
- record temperature scale
- distinguish gauge and absolute pressure
- map physical to normalized variables
- check every additive term dimensionally

Read [balances-units.md](references/balances-units.md).

## 4. Audit thermodynamics

Identify:

- phases
- property method
- activity or fugacity convention
- reference state
- pressure and temperature range
- nonideality
- electrolyte or polymer treatment
- missing parameters
- phase stability
- heat-capacity and enthalpy basis

Read [thermodynamics.md](references/thermodynamics.md).

## 5. Audit reaction and transport

Check:

- stoichiometry
- rate basis
- kinetic versus equilibrium assumption
- temperature dependence
- catalyst basis
- heat of reaction
- mass-transfer limitation
- heat-transfer limitation
- mixing assumption
- residence time
- axial or radial gradients
- dimensionless groups where useful

Read [transport-reaction.md](references/transport-reaction.md).

## 6. Check physical plausibility

Examples:

- compositions sum to one
- concentrations and holdups are nonnegative
- temperature and pressure are within model domains
- flows obey equipment direction and capacity
- balances close within tolerance
- steady-state derivatives are near zero
- property values are finite and plausible
- learned predictions obey physical bounds
- controller actions do not imply impossible duties or flows

## 7. Separate model levels

Distinguish:

- first-principles plant
- high-fidelity simulator
- reduced nonlinear model
- linearized model
- identified model
- surrogate or neural model
- estimator model
- controller model

A conclusion valid for one level does not automatically transfer to another.

## 8. Quantify residuals

Compute balance or constitutive residuals using documented scaling. Report both absolute physical residuals and normalized residuals when useful.

## 9. Hand off

- Aspen implementation: `aspen-process-simulation`
- columns: `distillation-separations`
- CSTR and reactions: `reaction-engineering-cstr`
- polymers: `polymerization-process-engineering`
- aqueous chemistry: `ph-aqueous-systems`
- hazards: `process-safety-operability`
- control: `control-mpc-research`
- data models: `machine-learning-research`

## Output

- system boundary and assumptions
- balances and constitutive laws
- unit and property-method audit
- physical-residual checks
- implausibilities or missing physics
- implications for the requested decision
- remaining uncertainty

## Gotchas

- A numerically converged flowsheet can violate the intended physical basis.
- Mole fraction, mass fraction, and concentration are not interchangeable.
- Volumetric flow depends on state and reference conditions.
- A property method valid for hydrocarbons may be invalid for electrolytes or polymers.
- Scaling can make a large physical balance error look numerically small.
- A steady-state model cannot explain inventory transients without added holdup.
