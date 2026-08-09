---
name: process-safety-operability
description: Analyze chemical-process safety and operability at a research and engineering-support level. Use for safe operating envelopes, abnormal scenarios, runaway, utility loss, high or low inventory, pressure excursions, equipment and sensor failures, trips, interlocks, startup, shutdown, relief-study inputs, dynamic safety simulations, HAZOP-style deviation reasoning, and interaction between optimization, control, RL, and safeguards. Do not claim regulatory compliance or replace a qualified process-hazard analysis.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Process Safety and Operability

## Purpose

Identify hazards, abnormal scenarios, safeguards, safe operating limits, and evidence gaps. Integrate process physics, dynamics, control, optimization, and learning behavior without overstating certification or compliance.

## Scope boundary

This skill supports research, modeling, scenario design, and technical review. It does not replace:

- a formal process hazard analysis
- relief-device design or certification
- regulatory compliance review
- site operating procedures
- licensed professional judgment
- emergency response planning

Escalate high-consequence conclusions to qualified personnel.

## 1. Define the hazard

State:

- material and energy inventory
- hazardous properties
- initiating event
- consequence
- affected equipment and people
- time scale
- detection
- protective layers
- safe limits
- uncertainty

## 2. Define the operating envelope

Include:

- temperature
- pressure
- level
- flow
- composition
- reaction rate
- heat-removal margin
- hydraulic margin
- utility availability
- actuator capability
- equipment limits
- model-validity region

Distinguish normal, alarm, trip, design, and damage limits.

Read [operating-envelope.md](references/operating-envelope.md).

## 3. Generate scenarios

Use deviation prompts such as:

- more
- less
- none
- reverse
- other than
- early
- late

Apply them to feed, cooling, heating, pressure, level, mixing, measurement, control, communication, and utilities.

Read [hazop-scenarios.md](references/hazop-scenarios.md).

## 4. Audit safeguards

For each safeguard:

- hazard addressed
- sensing
- logic
- final element
- independence
- response time
- failure modes
- testability
- bypass or maintenance state
- interaction with basic control or learning system

Do not count the same mechanism as multiple independent layers.

## 5. Audit dynamics

Check:

- time to consequence
- detection and actuation delay
- inventory accumulation
- runaway acceleration
- relief or vent assumptions
- controller saturation
- utility restoration
- startup and shutdown
- fallback controller
- simulator events

Read [dynamic-safety.md](references/dynamic-safety.md).

## 6. Audit optimization and learning

- hard constraints versus penalties
- unsafe reward tradeoffs
- model uncertainty
- exploration
- fallback
- solver failure
- invalid sensor data
- action rate
- safe-set coverage
- authority release
- operator override

Safety limits must be represented in the executed system, not only in training.

## 7. Evidence and claim level

Report:

- scenario coverage
- model fidelity
- empirical violations
- margins
- intervention
- assumptions
- unmodeled hazards
- uncertainty
- required expert review

## Output

- hazard and envelope
- scenarios
- safeguards
- dynamic response
- control or learning interactions
- evidence and limitations
- prioritized recommendations
- escalation items

## Gotchas

- A successful nominal simulation says little about abnormal operation.
- Average performance is not a safety metric.
- Control and trip layers may share sensors or actuators and therefore not be independent.
- A digital safeguard can fail through stale data, mapping errors, or communication loss.
- A simulator may omit relief, two-phase flow, decomposition, or equipment damage.
- "No violation observed" is not a certified safe operating limit.
