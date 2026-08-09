---
name: aspen-process-simulation
description: Inspect, design, troubleshoot, and document Aspen Plus, Aspen Plus Dynamics, and Aspen polymer simulation workflows. Use for property methods, components, flowsheets, recycles, design specifications, column or reactor blocks, convergence, initialization, steady-to-dynamic conversion, variable and stream mappings, exported results, snapshots, and safe automation. Preserve original files and require explicit permission before opening or running expensive or externally connected simulations.
license: MIT
compatibility: Offline inspection is portable. Live execution requires a licensed Aspen installation and project-approved simulator access.
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Aspen Process Simulation

## Purpose

Reason about Aspen as a modeling and execution environment. Separate physical-model validity, flowsheet specification, numerical convergence, dynamic initialization, variable mapping, and automation.

This skill can inspect files, exports, code, and documentation without executing Aspen. Live simulator execution requires explicit permission and a valid environment.

## Default safety boundary

Before execution or modification:

- identify product and version
- identify exact file and simulation case
- preserve the original
- create or use a safe copy or snapshot
- state intended changes
- verify external connections
- obtain authorization for expensive or live runs

Do not open a large Aspen Dynamics plant merely for a generic smoke test.

## 1. Establish provenance

Record:

- Aspen Plus, Aspen Plus Dynamics, or polymer extension
- version
- file type and path
- simulation or snapshot
- component list
- property method
- unit set
- scenario
- export timestamp
- automation interface, if any

## 2. Audit components and properties

Check:

- component identity
- conventional, nonconventional, pseudocomponent, electrolyte, or polymer species
- missing parameters
- property-method suitability
- phase expectations
- pressure and temperature range
- binary interaction data
- electrolyte chemistry
- polymer characterization
- consistency between steady and dynamic models

Read [aspen-plus.md](references/aspen-plus.md).

## 3. Audit flowsheet specification

- stream definitions
- block models
- degrees of freedom
- design specifications
- calculators and scripts
- recycles and tear streams
- unit and basis consistency
- bounds and guesses
- inactive or stale blocks
- property-domain failures

## 4. Diagnose convergence

Classify failure as:

- physical infeasibility
- property-method or property-data problem
- incorrect specification
- recycle or tear convergence
- bad initialization
- unit-operation failure
- numerical scaling
- design-spec conflict
- automation or file-state problem

Use staged convergence. Do not randomly change many tolerances at once.

## 5. Audit dynamic conversion

Check:

- valid steady-state initialization
- equipment holdup
- pressure-flow relationships
- valve sizing and position
- controller direction and initial output
- level and pressure loops
- actuator and sensor dynamics
- time units
- initial inventories
- event and disturbance mapping
- startup, shutdown, and failure logic

Read [aspen-dynamics.md](references/aspen-dynamics.md).

## 6. Verify mappings

For every exported or automated variable, record:

- Aspen object or path
- stream, block, stage, or tray
- variable name
- units
- read or write direction
- expected range
- sampling behavior
- physical meaning
- repository-side name and index

Never infer a tray, stream, or sensor mapping from array position alone.

## 7. Audit automation

When code controls Aspen:

- identify COM or other interface
- confirm process ownership
- handle timeouts
- check run status
- avoid orphan processes
- validate write permissions
- read back changed values
- record simulator messages
- restore a known state on failure
- save to a new file
- avoid parallel access to one case unless supported

Read [aspen-automation.md](references/aspen-automation.md).

## 8. Validate results

A converged case still needs:

- material and energy balance
- phase plausibility
- unit-operation performance
- equipment limits
- comparison with trusted data
- sensitivity to specifications
- consistency with exported values
- dynamic steady-state hold test

## Output

- simulator provenance
- model and mapping audit
- convergence or initialization diagnosis
- physical-validity checks
- recommended changes
- safe execution or verification plan
- files changed, only if authorized

## Gotchas

- A steady-state case can converge while the dynamic model is not initialized consistently.
- Aspen variable labels and automation paths may differ.
- Cached or exported values may not correspond to the active snapshot.
- Changing a property method can invalidate tuned controllers and identified models.
- A design specification can hide an impossible unconstrained operating point.
- Saving over the only working `.dynf`, `.bkp`, or project file destroys provenance.
